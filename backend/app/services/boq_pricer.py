"""
Batch BOQ material pricing pipeline.

Takes extracted BOQ items (materials), searches marketplace providers for
real-time pricing, ranks results, and persists price comparisons back to
the database.

Design decisions:
- Fully synchronous: designed to run inside ProcessPoolExecutor (same as
  boq_processor.py) to avoid event-loop conflicts.
- Two-tier pricing: Supabase `materials` cache (7-day TTL) → live Apify scrape.
- Decimal arithmetic for all money calculations to avoid float rounding.
- normalize_material_name is duplicated from boq_processor.py to avoid
  circular imports and give this module ownership of the function.
"""

from __future__ import annotations

import hashlib
import re
import structlog
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Callable, Optional

from app.integrations.marketplace import (
    MarketplaceProvider,
    MarketplaceResult,
    MarketplaceSource,
    MaterialPriceMatch,
)

logger = structlog.get_logger()


def _tokenize(text: str) -> list[str]:
    """
    Lowercase word tokens split on any non-alphanumeric boundary.

    Marketplace titles are punctuation-heavy ("Granit-Lantai", "kaca|awning",
    "PVC, 4 inch"); plain str.split() only breaks on whitespace, which would
    fuse "granit" into "granit-lantai" and hide it from whole-word matching,
    falsely rejecting good matches. Splitting on \\W keeps dimensions intact
    ("60x60" stays one token) while separating punctuation-joined words.
    """
    return re.findall(r"\w+", (text or "").lower())


def _match_confidence(query: str, product_name: str) -> float:
    """Word-overlap confidence: fraction of query words present in the product name."""
    search_words = set(_tokenize(query))
    product_words = set(_tokenize(product_name))
    if not search_words:
        return 0.0
    return len(search_words & product_words) / len(search_words)


def _head_noun_present(query: str, product_name: str) -> bool:
    """
    True if the query's head noun (first token of length >= 3) appears as a whole
    word in the product name. Indonesian BoQ material descriptions lead with the
    material noun (granit, batu, atap, pipa, rangka, keramik, kusen...), so a
    match whose product name lacks that noun is almost always wrong. When the
    query has no token of length >= 3, the gate passes (cannot judge).
    """
    head = next((w for w in _tokenize(query) if len(w) >= 3), None)
    if head is None:
        return True
    return head in set(_tokenize(product_name))


def _evaluate_match(
    query: str,
    product_name: str,
    market_price: Decimal,
    contractor_price: Decimal,
    is_owner_supply: bool,
    min_confidence: float,
    max_price_ratio: float,
) -> tuple[float, Optional[str], Optional[str]]:
    """
    Returns (confidence, rejection_reason, rejection_detail).
    rejection_reason is None when the match is accepted.

    Gate order: head-noun -> confidence floor -> imitation -> price band.
    The price-band gate is skipped for owner-supply items (their contractor
    price is a labor rate, not a material price).
    """
    confidence = _match_confidence(query, product_name)
    pname = (product_name or "").lower()
    qlow = query.lower()

    if not _head_noun_present(query, product_name):
        return confidence, "head_noun_missing", None
    if confidence < min_confidence:
        return confidence, "low_confidence", None
    for token in IMITATION_TOKENS:
        if token in pname and token not in qlow:
            return confidence, "imitation_product", token
    if not is_owner_supply and contractor_price > 0 and market_price > 0:
        ratio = float(market_price / contractor_price)
        if ratio > max_price_ratio or ratio < 1.0 / max_price_ratio:
            return confidence, "price_out_of_band", None
    return confidence, None, None


CACHE_TTL_DAYS = 7
CACHE_STATS_PRICE_BAND = 4.0  # Intra-scrape outlier filter (candidate vs best price). Distinct from boq_match_max_price_ratio, which compares market vs contractor price.

# Products that IMITATE construction materials (stickers, wallpaper, vinyl
# decals) match material queries by word overlap but are the wrong category.
# A match whose product name contains one of these tokens is rejected unless
# the query itself asked for it.
IMITATION_TOKENS = [
    "stiker",
    "sticker",
    "wallpaper",
    "wallpeper",   # common misspelling in listings
    "decal",
    "tempel dinding",
    "imitasi",
]


# =============================================================================
# Material Name Normalization
# =============================================================================


def normalize_material_name(description: str) -> str:
    """
    Normalize a material description for marketplace search.

    Strips Indonesian construction prefixes (Pas., Pek., Instalasi),
    owner-supply notes, room/floor location specifiers, and collapses
    whitespace.

    Args:
        description: Raw material description from BOQ.

    Returns:
        Cleaned, lowercased search query string.
    """
    prefixes_to_remove = [
        r"^pas\.\s*",
        r"^pas\s+",
        r"^instalasi\s+",
        r"^pek\.\s*",
        r"^pek\s+",
    ]

    result = description.lower()
    for prefix in prefixes_to_remove:
        result = re.sub(prefix, "", result, flags=re.IGNORECASE)

    # Remove owner supply / existing notes (with or without parentheses)
    result = re.sub(r"\([^)]*suply\s*by\s*owner[^)]*\)", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\([^)]*supply\s*by\s*owner[^)]*\)", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\(?use\s*existing\)?", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\([^)]*existing[^)]*\)", "", result, flags=re.IGNORECASE)

    # Remove location/room specifiers
    result = re.sub(r"master\s*bed\s*room", "", result, flags=re.IGNORECASE)
    result = re.sub(r"master\s*bathroom", "", result, flags=re.IGNORECASE)
    result = re.sub(r"living\s*dining\s*kitchen", "", result, flags=re.IGNORECASE)
    result = re.sub(r"lantai\s*(?!\d+x\d)(?!\d+\s*x\s*\d)\d+", "", result, flags=re.IGNORECASE)
    result = re.sub(r"area\s+\w+", "", result, flags=re.IGNORECASE)

    # Clean up
    result = re.sub(r"\s+", " ", result).strip()

    return result


# Brand markers in Indonesian BoQs ("granit ex Roman" = "Roman brand or
# equivalent"). The strip removes the marker and following alpha words but
# stops at dimension-like tokens (60x60, 9mm), which stay in the query.
_BRAND_STRIP_RE = re.compile(
    r"\b(?:ex|eks|setara|merk|merek)\b\.?\s+(?:[a-z]+\b\s*)*",
    re.IGNORECASE,
)


def build_search_query(description: str) -> str:
    """
    Build a marketplace search query from a raw BoQ description.

    Wraps normalize_material_name, then strips brand suffixes so polluted
    queries stop dragging irrelevant products into the candidate pool.

    Args:
        description: Raw material description from the BOQ.

    Returns:
        Cleaned, lowercased search query string.
    """
    query = normalize_material_name(description)
    query = _BRAND_STRIP_RE.sub(" ", query)
    return re.sub(r"\s+", " ", query).strip()


def canonicalize_for_cache(normalized_name: str) -> str:
    """
    Canonicalize a normalized material name for cache key lookup.

    The materials table uses `normalized_name` with sorted words so that
    "granit dinding 60x60" and "dinding granit 60x60" map to the same entry.

    Args:
        normalized_name: Output from normalize_material_name().

    Returns:
        Lowercased, alphabetically sorted words joined by space.
    """
    words = normalized_name.lower().split()
    return " ".join(sorted(words))


def simplify_query(query: str) -> str:
    """
    Broaden a search query for the one-round fallback retry.

    Indonesian material queries lead with the material noun, so broadening
    drops trailing qualifiers and never the head: >3 tokens keeps the first
    three ('keramik dinding kolam renang ex romance' → 'keramik dinding
    kolam'); 2-3 tokens drop the last token ('granit dinding' → 'granit').
    Returns '' when nothing can be dropped (single token), signalling the
    caller to skip the retry. Note: a single-token retry neutralizes the
    confidence gate (any product containing the token scores 1.0) — the
    head-noun, imitation, and price-band gates remain the effective filters.
    """
    words = query.split()
    if len(words) > 3:
        return " ".join(words[:3])
    if len(words) >= 2:
        return " ".join(words[:-1])
    return ""


# =============================================================================
# Cache Layer (Supabase `materials` table)
# =============================================================================


def _lookup_cache(
    supabase_client,
    cache_keys: list[str],
) -> dict[str, dict]:
    """
    Batch-query the materials table for cached price entries.

    Uses a single `.in_()` query for efficiency. Only returns entries
    where `price_updated_at` is within the TTL window and `price_median`
    is set.

    Args:
        supabase_client: Supabase client instance.
        cache_keys: List of canonicalized material names.

    Returns:
        Dict mapping cache_key → materials row dict (only fresh hits).
    """
    if not cache_keys:
        return {}

    try:
        result = (
            supabase_client.table("materials")
            .select("*")
            .in_("normalized_name", cache_keys)
            .execute()
        )
    except Exception:
        logger.warning("boq_cache_lookup_failed", exc_info=True)
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS)
    hits: dict[str, dict] = {}

    for row in (result.data or []):
        updated_at = row.get("price_updated_at")
        if not updated_at or not row.get("price_median"):
            continue

        # Parse ISO timestamp
        if isinstance(updated_at, str):
            try:
                updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue

        if updated_at >= cutoff:
            key = row.get("normalized_name", "")
            hits[key] = row

    logger.info("boq_cache_lookup", keys_queried=len(cache_keys), hits=len(hits))
    return hits


def _no_result_match(query: str, from_cache: bool) -> MaterialPriceMatch:
    """A match with no marketplace result (nothing found, or gated out)."""
    return MaterialPriceMatch(
        search_query=query,
        result=None,
        match_confidence=0.0,
        market_unit_price=None,
        market_total=None,
        price_difference=None,
        price_difference_pct=None,
        from_cache=from_cache,
    )


def _build_match_from_cache(
    item: dict,
    query: str,
    cache_row: dict,
    max_price_ratio: float = 5.0,
    min_confidence: float = 0.3,
) -> MaterialPriceMatch:
    """
    Build a MaterialPriceMatch from a cached materials table row.

    Uses price_median as the market unit price for comparison.

    Applies the full quality gate (head-noun, confidence, imitation, price band)
    via _evaluate_match — identical to the scrape path. The product name is read
    from cached_product_name (written at scrape time) falling back to name_id /
    name_en / query. Confidence is computed from the real product name, not a
    fixed 0.85, so cache and scrape judge matches by the same criteria.

    For owner-supply items the price-band gate is SKIPPED entirely.  The
    contractor price is an installation labor rate; comparing it to a material
    purchase price is invalid (a correct material price can easily be >5×
    the install rate).  market_unit_price / market_total are still set so the
    caller can use them as shopping-list estimates.  price_difference and
    price_difference_pct are set to None — that comparison is meaningless.

    Args:
        item: BOQ item dict (must have 'contractor_unit_price', 'quantity',
              and optionally 'is_owner_supply').
        query: Normalized search query.
        cache_row: Row from the materials table.
        max_price_ratio: Maximum ratio between market and contractor prices
            (ignored for owner-supply items).
        min_confidence: Minimum word-overlap confidence required to accept match.

    Returns:
        MaterialPriceMatch with from_cache=True.
    """
    market_price = Decimal(str(cache_row.get("price_median", 0) or 0))
    contractor_price = Decimal(str(item.get("contractor_unit_price", 0) or 0))
    quantity = Decimal(str(item.get("quantity", 0) or 0))
    is_owner_supply = bool(item.get("is_owner_supply"))

    product_name = (
        cache_row.get("cached_product_name")
        or cache_row.get("name_id")
        or cache_row.get("name_en")
        or query
    )

    confidence, rejection, rejection_token = _evaluate_match(
        query, product_name, market_price, contractor_price,
        is_owner_supply, min_confidence, max_price_ratio,
    )

    if rejection is not None:
        log_kwargs: dict = dict(
            query=query,
            reason=rejection,
            confidence=round(confidence, 2),
            market_price=int(market_price),
            contractor_price=int(contractor_price),
            source="cache",
        )
        if rejection_token is not None:
            log_kwargs["imitation_token"] = rejection_token
        logger.info("boq_match_rejected", **log_kwargs)
        return _no_result_match(query, from_cache=True)

    market_total = market_price * quantity

    # Owner-supply items: suppress price_difference fields — comparing a
    # material market price to an installation labor rate is meaningless.
    if is_owner_supply:
        diff: Optional[Decimal] = None
        diff_pct: Optional[float] = None
    elif contractor_price > 0:
        diff = contractor_price - market_price
        diff_pct = round(float(diff / contractor_price * 100), 2)
    else:
        diff = Decimal("0")
        diff_pct = 0.0

    return MaterialPriceMatch(
        search_query=query,
        result=MarketplaceResult(
            product_name=product_name,
            price_idr=int(market_price),
            url=cache_row.get("tokopedia_affiliate_url") or "",
            seller="",
            seller_location=cache_row.get("seller_location") or "",
            rating=cache_row.get("rating_avg"),
            sold_count=cache_row.get("count_sold_total"),
            best_seller_score=0.0,
            source=MarketplaceSource.CACHED,
        ),
        match_confidence=min(confidence, 1.0),
        market_unit_price=market_price,
        market_total=market_total,
        price_difference=diff,
        price_difference_pct=diff_pct,
        from_cache=True,
    )


def _cache_material_code(cache_key: str) -> str:
    """
    Generate a deterministic material_code (<= 20 chars) for scraped cache rows.

    Args:
        cache_key: Canonicalized cache key (normalized_name).

    Returns:
        Code like 'BOQ' + 16 hex chars, stable for the same cache key.
    """
    digest = hashlib.sha1(cache_key.encode("utf-8")).hexdigest()[:16].upper()
    return f"BOQ{digest}"


def _write_cache(
    supabase_client,
    query: str,
    cache_key: str,
    best_product: dict,
    all_candidates: list[dict],
    unit: str | None = None,
) -> None:
    """
    Write scraped pricing data into the materials table for future cache hits.

    All cached statistics (prices, ratings, sold counts) are computed only from
    candidates whose price lies within a sanity band around the best product's
    price: [best_price / CACHE_STATS_PRICE_BAND, best_price * CACHE_STATS_PRICE_BAND].
    This filters outliers (e.g., bulk packs, mismatched products) that would
    otherwise corrupt median/min/max/avg, rating, and sold-count aggregates.

    Write strategy (materials has NOT NULL columns a blind upsert can't satisfy,
    and a unique index on LOWER(name_id) that an upsert can't arbitrate):
      1. Update the existing cache row matched by normalized_name.
      2. Adopt a seeded row whose name_id matches the query (sets its
         normalized_name so future lookups hit it directly).
      3. Insert a new row with a generated material_code and required fields.

    Args:
        supabase_client: Supabase client instance.
        query: The normalized search query.
        cache_key: Canonicalized cache key (normalized_name).
        best_product: Best-ranked product dict from the scrape.
        all_candidates: All candidate product dicts for price statistics.
        unit: BOQ item unit, used only when inserting a new row.
    """
    if not best_product or not all_candidates:
        return

    prices = [c.get("price_idr", 0) for c in all_candidates if c.get("price_idr")]
    if not prices:
        return

    # Restrict ALL cached statistics to candidates priced near the best match —
    # one mismatched product must not corrupt median, ratings, or sold counts.
    best_price = best_product.get("price_idr", 0) or 0
    if best_price > 0:
        in_band = [
            c for c in all_candidates
            if c.get("price_idr")
            and best_price / CACHE_STATS_PRICE_BAND
                <= c["price_idr"]
                <= best_price * CACHE_STATS_PRICE_BAND
        ]
    else:
        in_band = [c for c in all_candidates if c.get("price_idr")]
    if not in_band:
        return

    prices = [c["price_idr"] for c in in_band]

    prices_sorted = sorted(prices)
    n = len(prices_sorted)
    price_median = prices_sorted[n // 2] if n % 2 == 1 else (prices_sorted[n // 2 - 1] + prices_sorted[n // 2]) / 2

    ratings = [c.get("rating") for c in in_band if c.get("rating") is not None]
    sold_counts = [c.get("sold_count", 0) or c.get("sold", 0) or 0 for c in in_band]

    price_fields = {
        "tokopedia_search": query,
        "price_min": min(prices),
        "price_max": max(prices),
        "price_avg": sum(prices) / n,
        "price_median": price_median,
        "price_sample_size": n,
        "price_updated_at": datetime.now(timezone.utc).isoformat(),
        "seller_location": best_product.get("location") or best_product.get("seller_location") or "",
        "rating_avg": sum(ratings) / len(ratings) if ratings else None,
        "rating_sample_size": len(ratings),
        "count_sold_total": sum(sold_counts),
        "tokopedia_affiliate_url": best_product.get("url") or best_product.get("link") or "",
        "cached_product_name": best_product.get("name") or best_product.get("title") or "",
    }

    try:
        # 1. Existing cache row for this normalized name
        result = (
            supabase_client.table("materials")
            .update(price_fields)
            .eq("normalized_name", cache_key)
            .execute()
        )
        if result.data:
            return

        # 2. Seeded row matching the query by name — adopt it into the cache
        result = (
            supabase_client.table("materials")
            .update({**price_fields, "normalized_name": cache_key})
            .ilike("name_id", query)
            .is_("normalized_name", "null")
            .execute()
        )
        if result.data:
            return

        # 3. New cache row (materials requires code/name/category/unit)
        supabase_client.table("materials").insert({
            **price_fields,
            "normalized_name": cache_key,
            "material_code": _cache_material_code(cache_key),
            "name_id": query[:200],
            "name_en": query[:200],
            "category": "boq_scraped",
            "unit": (unit or "unit")[:50],
        }).execute()
    except Exception:
        # Cache write failure is non-critical — log and continue
        logger.warning("boq_cache_write_failed", cache_key=cache_key, exc_info=True)


# =============================================================================
# Batch Pricing Pipeline
# =============================================================================


def batch_price_materials(
    items: list[dict],
    provider: MarketplaceProvider,
    supabase_client,
    max_lookups: int = 20,
    progress_callback: Optional[Callable[[int], None]] = None,
    min_confidence: float = 0.3,
    max_price_ratio: float = 5.0,
) -> list[tuple[dict, MaterialPriceMatch]]:
    """
    Main pipeline entry point. Runs fully synchronously.

    Steps:
      1. Normalize material names into search queries.
      2. Skip items whose normalized query is < 3 characters.
      3. Prioritize owner_supply items first, then others.
      4. Cap at max_lookups.
      5. Check Supabase materials cache for fresh prices.
      6. Scrape marketplace only for cache misses.
      7. Write scrape results back to cache.
      8. For each result: rank candidates, pick best, calculate delta.
      9. Apply quality gate: reject matches below min_confidence or outside
         the price-sanity band [contractor/max_price_ratio, contractor*max_price_ratio].

    Args:
        items: BOQ item rows (dicts with at minimum 'description').
        provider: Marketplace provider instance.
        supabase_client: Supabase client for cache lookups/writes.
        max_lookups: Maximum number of items to price in one run.
        progress_callback: Optional callback receiving progress percentage (40-85 range).
        min_confidence: Minimum word-overlap confidence to accept a scrape match.
        max_price_ratio: Maximum ratio between market and contractor unit prices.

    Returns:
        List of (item, MaterialPriceMatch) pairs, one per processed item,
        so callers never have to reconstruct which match belongs to which item.
    """
    # --- Prepare priceable items ---
    priceable: list[dict] = []
    for item in items:
        query = normalize_material_name(item.get("description", ""))
        if len(query) < 3:
            continue
        cache_key = canonicalize_for_cache(query)
        priceable.append({**item, "_search_query": query, "_cache_key": cache_key})

    # --- Prioritize owner_supply items ---
    priceable.sort(key=lambda x: (not x.get("is_owner_supply", False)))

    # --- Cap at max_lookups ---
    priceable = priceable[:max_lookups]

    total = len(priceable)
    if total == 0:
        return []

    # --- Check cache ---
    cache_keys = [item["_cache_key"] for item in priceable]
    cache_hits = _lookup_cache(supabase_client, cache_keys)

    # Split into cached and uncached
    cached_items: list[tuple[int, dict]] = []  # (index, item)
    uncached_items: list[tuple[int, dict]] = []  # (index, item)

    for i, item in enumerate(priceable):
        if item["_cache_key"] in cache_hits:
            cached_items.append((i, item))
        else:
            uncached_items.append((i, item))

    logger.info(
        "boq_pricing_batch_start",
        total_items=total,
        cache_hits=len(cached_items),
        cache_misses=len(uncached_items),
    )

    # --- Build matches array (will be filled in order) ---
    matches: list[MaterialPriceMatch | None] = [None] * total

    # --- Process cache hits (instant, 40% → 55%) ---
    for idx, (i, item) in enumerate(cached_items):
        cache_row = cache_hits[item["_cache_key"]]
        matches[i] = _build_match_from_cache(item, item["_search_query"], cache_row, max_price_ratio=max_price_ratio, min_confidence=min_confidence)

        if progress_callback and total > 0:
            # Cache hits use the 40-55% range
            pct = 40 + int(15 * (idx + 1) / max(len(cached_items), 1))
            progress_callback(pct)

    # --- Scrape marketplace for cache misses (55% → 85%) ---
    if uncached_items:
        uncached_queries = [item["_search_query"] for _, item in uncached_items]

        # batch_progress maps actor-chunk completion onto the 55-80 window.
        # After all chunks complete, per-item processing covers 80-85.
        n_uncached = max(len(uncached_items), 1)

        def _on_batch_progress(done: int, total_chunks: int) -> None:
            if progress_callback and total > 0:
                pct = 55 + int(25 * done / max(total_chunks, 1))
                progress_callback(min(pct, 80))

        raw_results = provider.batch_search_sync(
            uncached_queries,
            limit_per_query=10,
            batch_progress=_on_batch_progress,
        )

        # First pass: build matches, track which items need a fallback retry
        fallback_needed: list[tuple[int, dict, str, str]] = []  # (matches-index, item, simplified_query, reason)

        for idx, (i, item) in enumerate(uncached_items):
            query = item["_search_query"]
            candidates = raw_results.get(query, [])

            ranked = provider.rank_results(candidates) if candidates else []
            match, accepted = _walk_candidates(
                item, query, ranked,
                min_confidence=min_confidence, max_price_ratio=max_price_ratio,
            )
            matches[i] = match

            # Only cache accepted matches — cache truth follows gate truth
            if accepted is not None and match.result is not None:
                _write_cache(
                    supabase_client,
                    query,
                    item["_cache_key"],
                    accepted.product,
                    candidates,
                    unit=item.get("unit"),
                )

            # Track items with no accepted match for fallback retry (zero
            # candidates, or all candidates gate-rejected)
            if matches[i].result is None:
                simplified = simplify_query(query)
                if simplified:
                    reason = "no_candidates" if not candidates else "all_rejected"
                    fallback_needed.append((i, item, simplified, reason))

            if progress_callback and total > 0:
                # Per-item post-processing uses the 80-85% range
                pct = 80 + int(5 * (idx + 1) / n_uncached)
                progress_callback(min(pct, 85))

        # One-round query-simplification fallback for zero-candidate and
        # all-rejected items
        if fallback_needed:
            reason_counts: dict[str, int] = {}
            for _, _, _, reason in fallback_needed:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            logger.info(
                "boq_query_fallback",
                count=len(fallback_needed),
                reasons=reason_counts,
            )
            simplified_queries = [sq for _, _, sq, _ in fallback_needed]
            fallback_results = provider.batch_search_sync(simplified_queries, limit_per_query=10)

            for i, item, simplified, _reason in fallback_needed:
                candidates = fallback_results.get(simplified, [])

                ranked = provider.rank_results(candidates) if candidates else []
                # Match against the simplified query so confidence is computed
                # against the words we actually searched.
                match, accepted = _walk_candidates(
                    item, simplified, ranked,
                    min_confidence=min_confidence, max_price_ratio=max_price_ratio,
                )
                matches[i] = match

                # Only cache accepted matches — cache truth follows gate truth
                if accepted is not None and match.result is not None:
                    simplified_cache_key = canonicalize_for_cache(simplified)
                    _write_cache(
                        supabase_client,
                        simplified,
                        simplified_cache_key,
                        accepted.product,
                        candidates,
                        unit=item.get("unit"),
                    )
    else:
        # All from cache — jump to 85%
        if progress_callback:
            progress_callback(85)

    # Pair each item with its match; drop None entries (shouldn't happen, but safety)
    pairs = [
        (item, match)
        for item, match in zip(priceable, matches)
        if match is not None
    ]

    logger.info(
        "boq_pricing_batch_complete",
        priced=sum(1 for _, m in pairs if m.result),
        from_cache=sum(1 for _, m in pairs if m.from_cache),
        total=total,
    )
    return pairs


# =============================================================================
# Match Building
# =============================================================================


def _build_match_from_scrape(
    item: dict,
    query: str,
    best,
    min_confidence: float = 0.3,
    max_price_ratio: float = 5.0,
) -> MaterialPriceMatch:
    """
    Build a MaterialPriceMatch from a BOQ item and a ranking result.

    Applies a quality gate before building the match.  For non-owner-supply
    items the gate has three parts:
      1. Confidence gate: word-overlap between query and product name must be
         >= min_confidence (default 0.3). A pool fitting matching vacuum storage
         bags scores 0.0 and is rejected.
      2. Imitation-product filter: reject sticker/wallpaper/decal products
         matching real construction-material queries.
      3. Price-sanity band: when a contractor price is available, the market
         price must lie within [contractor/max_price_ratio, contractor*max_price_ratio].
         Matches outside this band (e.g. -12,100% price differences) are rejected.

    For owner-supply items the price-band gate (step 3) is SKIPPED.  The
    contractor price on these lines is an installation labor rate; comparing it
    to a material purchase price is invalid — a correct material price can
    easily exceed the band.  The confidence and imitation gates still apply.
    price_difference and price_difference_pct are set to None for owner-supply
    matches because comparing a material market price to a labor rate is
    meaningless; market_unit_price and market_total are still populated so the
    caller can use them as shopping-list estimates.

    Rejected matches are returned as no-result matches (search_query kept,
    all pricing fields None, match_confidence=0.0) so they are recorded but
    do not contribute to market totals or summary statistics.

    Args:
        item: BOQ item dict (must have 'contractor_unit_price', 'quantity',
              and optionally 'is_owner_supply').
        query: Normalized search query used.
        best: A BestSellerScore object (with .product dict and .total_score),
              or None if no results found.
        min_confidence: Minimum word-overlap confidence required to accept match.
        max_price_ratio: Maximum ratio between market and contractor prices
            (ignored for owner-supply items).

    Returns:
        MaterialPriceMatch with computed pricing deltas and confidence,
        or a no-result match if the quality gate rejects the candidate.
    """
    if best is None:
        return _no_result_match(query, from_cache=False)

    # Extract from BestSellerScore
    product = best.product
    market_price = Decimal(str(product.get("price_idr", 0)))
    contractor_price = Decimal(str(item.get("contractor_unit_price", 0) or 0))
    quantity = Decimal(str(item.get("quantity", 0) or 0))
    is_owner_supply = bool(item.get("is_owner_supply"))

    product_name = product.get("name") or product.get("title") or ""

    confidence, rejection, rejection_token = _evaluate_match(
        query, product_name, market_price, contractor_price,
        is_owner_supply, min_confidence, max_price_ratio,
    )

    if rejection is not None:
        log_kwargs: dict = dict(
            query=query,
            reason=rejection,
            confidence=round(confidence, 2),
            market_price=int(market_price),
            contractor_price=int(contractor_price),
        )
        if rejection_token is not None:
            log_kwargs["imitation_token"] = rejection_token
        logger.info("boq_match_rejected", **log_kwargs)
        return _no_result_match(query, from_cache=False)

    market_total = market_price * quantity

    # Owner-supply items: suppress price_difference fields — comparing a
    # material market price to an installation labor rate is meaningless.
    if is_owner_supply:
        diff: Optional[Decimal] = None
        diff_pct: Optional[float] = None
    elif contractor_price > 0:
        diff = contractor_price - market_price
        diff_pct = round(float(diff / contractor_price * 100), 2)
    else:
        diff = Decimal("0")
        diff_pct = 0.0

    return MaterialPriceMatch(
        search_query=query,
        result=MarketplaceResult(
            product_name=product_name,
            price_idr=product.get("price_idr", 0),
            url=product.get("url") or product.get("link") or "",
            seller=product.get("shop") or product.get("seller") or "",
            seller_location=product.get("location") or product.get("seller_location") or "",
            rating=product.get("rating"),
            sold_count=product.get("sold_count") or product.get("sold"),
            best_seller_score=best.total_score,
            source=MarketplaceSource.TOKOPEDIA,
        ),
        match_confidence=min(confidence, 1.0),
        market_unit_price=market_price,
        market_total=market_total,
        price_difference=diff,
        price_difference_pct=diff_pct,
        from_cache=False,
    )


def _walk_candidates(
    item: dict,
    query: str,
    ranked: list,
    min_confidence: float = 0.3,
    max_price_ratio: float = 5.0,
) -> tuple[MaterialPriceMatch, Optional["BestSellerScore"]]:
    """
    Walk ranked candidates through the quality gate; first acceptance wins.

    rank_results orders by best-seller score (price/rating/sales), not by
    relevance to the query — the top-scored product is often a popular but
    wrong item while a true match sits lower. Judging every candidate with
    the unchanged _build_match_from_scrape gate recovers those matches
    without loosening the gate itself.

    Args:
        item: BOQ item dict (same contract as _build_match_from_scrape).
        query: Normalized search query.
        ranked: BestSellerScore list from provider.rank_results (may be empty).
        min_confidence: Passed through to the gate.
        max_price_ratio: Passed through to the gate.

    Returns:
        (match, accepted): the first accepted match and its candidate, or
        (no-result match, None) when no candidate passes the gate.
    """
    for rank, candidate in enumerate(ranked, start=1):
        match = _build_match_from_scrape(
            item, query, candidate,
            min_confidence=min_confidence, max_price_ratio=max_price_ratio,
        )
        if match.result is not None:
            logger.info(
                "boq_candidate_walk",
                query=query, candidates_evaluated=rank, accepted_rank=rank,
            )
            return match, candidate

    if ranked:
        logger.info(
            "boq_candidate_walk",
            query=query, candidates_evaluated=len(ranked), all_rejected=True,
        )
    return _no_result_match(query, from_cache=False), None


# =============================================================================
# Persistence
# =============================================================================


def persist_price_results(
    supabase_client,
    job_id: str,
    pairs: list[tuple[dict, MaterialPriceMatch]],
) -> None:
    """
    Write pricing results back to boq_items table rows.

    Each match is written to its paired item's row by the item's 'id'.

    Args:
        supabase_client: Supabase client instance.
        job_id: BOQ processing job ID (for logging context).
        pairs: (item, match) pairs from batch_price_materials. Items must
            contain an 'id' field.
    """
    for item, match in pairs:
        item_id = item.get("id")
        if not item_id:
            continue

        update_data: dict = {
            "search_query": match.search_query,
        }

        if match.result:
            update_data.update({
                "tokopedia_product_name": match.result.product_name,
                "tokopedia_price": float(match.result.price_idr),
                "tokopedia_url": match.result.url,
                "tokopedia_seller": match.result.seller,
                "tokopedia_seller_location": match.result.seller_location,
                "tokopedia_rating": match.result.rating,
                "tokopedia_sold_count": match.result.sold_count,
                "match_confidence": match.match_confidence,
                "market_unit_price": float(match.market_unit_price) if match.market_unit_price is not None else None,
                "market_total": float(match.market_total) if match.market_total is not None else None,
                "price_difference": float(match.price_difference) if match.price_difference is not None else None,
                "price_difference_percent": match.price_difference_pct,
            })

        supabase_client.table("boq_items").update(update_data).eq("id", item_id).execute()

    logger.info("boq_pricing_persisted", job_id=job_id, items_updated=len(pairs))
