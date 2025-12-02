"""
Worker deduplication service for merging duplicate profiles from multiple sources.

Handles:
- Phone number normalization (Indonesian formats)
- Business name fuzzy matching (typos, variations)
- Address similarity comparison
- Intelligent profile merging with source priority
"""

import re
from difflib import SequenceMatcher
from typing import Any

from app.services.trust_calculator import SourceTier


# Phone normalization patterns for Indonesia
INDONESIA_COUNTRY_CODE = "+62"
PHONE_PATTERNS = {
    # Match various Indonesian phone formats
    "mobile": re.compile(r"^(?:\+62|62|0)8[0-9]{8,11}$"),
    "landline": re.compile(r"^(?:\+62|62|0)(?:2[1-9]|3[1-9]|4[1-9]|5[1-9]|6[1-9])[0-9]{6,8}$"),
}


def normalize_phone_number(phone: str | None) -> str | None:
    """
    Normalize Indonesian phone number to consistent format.

    Handles formats:
    - +62812345678 (international)
    - 62812345678 (without +)
    - 0812345678 (local format)
    - +62 812 345 678 (with spaces)
    - +62-812-345-678 (with hyphens)
    - (0361) 234567 (landline with area code)

    Output format: +628123456789 (no spaces, international)

    Args:
        phone: Phone number string in any format

    Returns:
        Normalized phone number or None if invalid

    Examples:
        >>> normalize_phone_number("0812-345-678")
        '+62812345678'
        >>> normalize_phone_number("+62 812 345 678")
        '+62812345678'
        >>> normalize_phone_number("(0361) 234567")
        '+62361234567'
    """
    if not phone:
        return None

    # Remove all non-digit characters except leading +
    cleaned = re.sub(r"[^\d+]", "", phone)

    # Remove leading + temporarily for processing
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # Handle different formats
    if cleaned.startswith("62"):
        # Already has country code (with or without +)
        normalized = f"+{cleaned}"
    elif cleaned.startswith("0"):
        # Local format (0812... or 0361...)
        normalized = f"+62{cleaned[1:]}"
    elif cleaned.startswith("8"):
        # Mobile without leading 0 or country code
        normalized = f"+62{cleaned}"
    else:
        # Unknown format
        return None

    # Validate against known patterns
    for pattern in PHONE_PATTERNS.values():
        if pattern.match(normalized):
            return normalized

    return None


def normalize_business_name(name: str) -> str:
    """
    Normalize business name for comparison.

    Removes:
    - Common business suffixes (PT, CV, UD, Toko, Jasa)
    - Extra whitespace
    - Special characters
    - Case differences

    Args:
        name: Business name

    Returns:
        Normalized name for comparison

    Examples:
        >>> normalize_business_name("PT. Bali Pool Service")
        'bali pool service'
        >>> normalize_business_name("Pak Wayan's Pool & Spa")
        'pak wayan pool spa'
    """
    # Convert to lowercase
    normalized = name.lower()

    # Remove business entity types (Indonesian and English)
    entity_types = [
        r"\bpt\.?\b",  # Perseroan Terbatas
        r"\bcv\.?\b",  # Commanditaire Vennootschap
        r"\bud\.?\b",  # Usaha Dagang
        r"\btoko\b",  # Shop
        r"\bjasa\b",  # Service
        r"\bllc\.?\b",  # Limited Liability Company
        r"\binc\.?\b",  # Incorporated
        r"\bltd\.?\b",  # Limited
    ]
    for entity in entity_types:
        normalized = re.sub(entity, "", normalized)

    # Remove possessive forms
    normalized = re.sub(r"'s\b", "", normalized)

    # Remove special characters, keep only alphanumeric and spaces
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized)

    # Remove extra whitespace
    normalized = " ".join(normalized.split())

    return normalized.strip()


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two business names.

    Uses SequenceMatcher with normalized names for fuzzy matching.
    Handles common variations like typos, abbreviations, word order.

    Args:
        name1: First business name
        name2: Second business name

    Returns:
        Similarity score between 0.0 and 1.0

    Examples:
        >>> calculate_name_similarity("Bali Pool Service", "Bali Pool Services")
        0.96
        >>> calculate_name_similarity("Pak Wayan Pool", "Pak Wayan's Pools")
        0.91
    """
    norm1 = normalize_business_name(name1)
    norm2 = normalize_business_name(name2)

    # Exact match after normalization
    if norm1 == norm2:
        return 1.0

    # Sequence matching for fuzzy comparison
    return SequenceMatcher(None, norm1, norm2).ratio()


def are_workers_duplicates(
    worker1: dict[str, Any],
    worker2: dict[str, Any],
    name_threshold: float = 0.85,
    phone_match_required: bool = True,
) -> bool:
    """
    Determine if two worker profiles are duplicates.

    Matching criteria (in order of priority):
    1. Exact phone number match (highest confidence)
    2. High name similarity (>= threshold) + same location
    3. Same Google Maps place_id (if available)

    Args:
        worker1: First worker profile
        worker2: Second worker profile
        name_threshold: Minimum name similarity score (0.0-1.0)
        phone_match_required: If True, require phone match for duplicates

    Returns:
        True if workers are likely duplicates

    Examples:
        >>> are_workers_duplicates(
        ...     {"business_name": "Bali Pool Service", "phone": "+62812345678"},
        ...     {"business_name": "Bali Pool Services", "phone": "+62812345678"}
        ... )
        True
    """
    # Check 1: Phone number exact match (highest confidence)
    phone1 = normalize_phone_number(worker1.get("phone"))
    phone2 = normalize_phone_number(worker2.get("phone"))

    if phone1 and phone2 and phone1 == phone2:
        return True

    # If phone match is required but phones don't match, not duplicates
    if phone_match_required and phone1 and phone2:
        return False

    # Check 2: Google Maps place_id match (if available)
    place_id1 = worker1.get("gmaps_place_id")
    place_id2 = worker2.get("gmaps_place_id")

    if place_id1 and place_id2 and place_id1 == place_id2:
        return True

    # Check 3: High name similarity + location match
    name_similarity = calculate_name_similarity(
        worker1.get("business_name", ""),
        worker2.get("business_name", ""),
    )

    if name_similarity >= name_threshold:
        # Check if locations match (approximately)
        loc1 = worker1.get("location", "").lower()
        loc2 = worker2.get("location", "").lower()

        # Simple location matching (same city/area)
        if loc1 and loc2:
            # Check if one location contains the other
            if loc1 in loc2 or loc2 in loc1:
                return True

    return False


def merge_worker_profiles(
    workers: list[dict[str, Any]],
    source_priority: dict[str, int] | None = None,
) -> dict[str, Any]:
    """
    Merge multiple duplicate worker profiles into a single comprehensive profile.

    Merge strategy:
    1. Prefer data from higher-priority sources (Google Maps > OLX)
    2. Aggregate reviews from all sources
    3. Take maximum values for numeric fields (rating, review_count)
    4. Combine specializations (unique)
    5. Keep most recent scrape data

    Args:
        workers: List of duplicate worker profiles to merge
        source_priority: Dict mapping source tier to priority (higher = better)
                        Default: {"platform": 4, "manual": 3, "google_maps": 2, "olx": 1}

    Returns:
        Merged worker profile with best data from all sources

    Examples:
        >>> workers = [
        ...     {"business_name": "Bali Pool", "source_tier": "google_maps", "gmaps_rating": 4.8},
        ...     {"business_name": "Bali Pools", "source_tier": "olx", "olx_price_idr": 500000}
        ... ]
        >>> merged = merge_worker_profiles(workers)
        >>> merged["business_name"]
        'Bali Pool'  # From Google Maps (higher priority)
    """
    if not workers:
        return {}

    if len(workers) == 1:
        return workers[0]

    # Default source priority
    if source_priority is None:
        source_priority = {
            SourceTier.PLATFORM.value: 4,
            SourceTier.MANUAL_CURATED.value: 3,
            SourceTier.GOOGLE_MAPS.value: 2,
            SourceTier.OLX.value: 1,
        }

    # Sort workers by source priority (highest first)
    sorted_workers = sorted(
        workers,
        key=lambda w: source_priority.get(w.get("source_tier", ""), 0),
        reverse=True,
    )

    # Start with highest priority worker as base
    merged = sorted_workers[0].copy()

    # Aggregate data from all sources
    all_specializations = set()
    all_categories = set()
    max_rating = 0.0
    total_reviews = 0

    for worker in sorted_workers:
        # Aggregate specializations
        if worker.get("specializations"):
            all_specializations.update(worker["specializations"])

        # Aggregate categories
        if worker.get("gmaps_categories"):
            all_categories.update(worker["gmaps_categories"])

        # Take maximum rating
        rating = worker.get("gmaps_rating") or worker.get("olx_rating") or 0.0
        if rating > max_rating:
            max_rating = rating

        # Sum review counts
        total_reviews += worker.get("gmaps_review_count", 0)
        total_reviews += worker.get("olx_review_count", 0)

        # Fill in missing fields from lower priority sources
        for key, value in worker.items():
            if key not in merged or merged[key] is None:
                merged[key] = value

    # Update aggregated fields
    merged["specializations"] = list(all_specializations)
    merged["gmaps_categories"] = list(all_categories) if all_categories else merged.get("gmaps_categories")

    if max_rating > 0:
        merged["gmaps_rating"] = max_rating

    if total_reviews > 0:
        merged["gmaps_review_count"] = total_reviews

    # Mark as merged profile
    merged["is_merged"] = True
    merged["source_count"] = len(workers)
    merged["merged_sources"] = [w.get("source_tier") for w in workers]

    return merged


def deduplicate_workers(
    workers: list[dict[str, Any]],
    name_threshold: float = 0.85,
) -> list[dict[str, Any]]:
    """
    Deduplicate a list of worker profiles.

    Process:
    1. Group workers by normalized phone number
    2. Within each group, find similar names
    3. Merge duplicate profiles
    4. Return deduplicated list

    Args:
        workers: List of worker profiles (from scraping)
        name_threshold: Name similarity threshold for matching

    Returns:
        Deduplicated list of worker profiles

    Examples:
        >>> workers = [
        ...     {"business_name": "Bali Pool", "phone": "0812345678", "source_tier": "google_maps"},
        ...     {"business_name": "Bali Pool Service", "phone": "+62812345678", "source_tier": "olx"}
        ... ]
        >>> deduplicated = deduplicate_workers(workers)
        >>> len(deduplicated)
        1
    """
    if not workers:
        return []

    # Track processed workers and duplicates
    processed = set()
    duplicate_groups = []

    # Find duplicate groups
    for i, worker1 in enumerate(workers):
        if i in processed:
            continue

        # Start new group with this worker
        group = [worker1]
        processed.add(i)

        # Find all duplicates for this worker
        for j, worker2 in enumerate(workers):
            if j <= i or j in processed:
                continue

            if are_workers_duplicates(worker1, worker2, name_threshold):
                group.append(worker2)
                processed.add(j)

        duplicate_groups.append(group)

    # Merge each duplicate group
    deduplicated = []
    for group in duplicate_groups:
        if len(group) == 1:
            # No duplicates, keep as is
            deduplicated.append(group[0])
        else:
            # Merge duplicates
            merged = merge_worker_profiles(group)
            deduplicated.append(merged)

    return deduplicated
