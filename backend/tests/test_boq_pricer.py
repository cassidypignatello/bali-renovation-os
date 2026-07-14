"""
Tests for BOQ Batch Pricing Pipeline

Tests the normalize_material_name, _build_match_from_scrape,
batch_price_materials, and persist_price_results functions.
Uses mocks exclusively - no real API calls or Supabase writes.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest

from app.integrations.apify import BestSellerScore
from app.integrations.marketplace import (
    MarketplaceSource,
    MaterialPriceMatch,
)
from app.services.boq_pricer import (
    normalize_material_name,
    batch_price_materials,
    persist_price_results,
    _build_match_from_scrape,
    simplify_query,
    canonicalize_for_cache,
    IMITATION_TOKENS,
)


# =============================================================================
# normalize_material_name Tests
# =============================================================================


class TestNormalizeMaterialName:
    """Tests for normalize_material_name."""

    def test_strips_pas_dot_prefix(self):
        """Should remove 'pas.' prefix from descriptions."""
        result = normalize_material_name("Pas. Granit Dinding Premium")
        assert result == "granit dinding premium"

    def test_strips_pas_space_prefix(self):
        """Should remove 'pas ' prefix from descriptions."""
        assert "keramik dinding 25x40" == normalize_material_name("Pas Keramik Dinding 25x40")

    def test_strips_instalasi_prefix(self):
        """Should remove 'instalasi' prefix from descriptions."""
        assert "pipa pvc 4 inch" == normalize_material_name("Instalasi Pipa PVC 4 Inch")

    def test_strips_pek_dot_prefix(self):
        """Should remove 'pek.' prefix from descriptions."""
        assert "plester dinding" == normalize_material_name("Pek. Plester Dinding")

    def test_strips_pek_space_prefix(self):
        """Should remove 'pek ' prefix from descriptions."""
        assert "plester dinding" == normalize_material_name("Pek Plester Dinding")

    def test_removes_owner_supply_note_suply(self):
        """Should remove '(Suply By Owner)' notes."""
        result = normalize_material_name("Granit Lantai (Suply By Owner) 60x60")
        assert "suply" not in result.lower()
        assert "owner" not in result.lower()

    def test_removes_owner_supply_note_supply(self):
        """Should remove '(Supply By Owner)' notes."""
        result = normalize_material_name("Granit Lantai (Supply By Owner) 60x60")
        assert "supply" not in result.lower()
        assert "owner" not in result.lower()

    def test_removes_use_existing(self):
        """Should remove '(use existing)' notes."""
        result = normalize_material_name("Pintu (use existing) Kayu")
        assert "existing" not in result.lower()

    def test_removes_existing_parenthesized(self):
        """Should remove '(existing)' notes."""
        result = normalize_material_name("Kusen (existing) Aluminium")
        assert "existing" not in result.lower()

    def test_removes_master_bed_room(self):
        """Should remove 'master bed room' location specifier."""
        result = normalize_material_name("Granit Lantai Master Bed Room 60x60")
        assert "master" not in result.lower()
        assert "bed" not in result.lower()
        assert "room" not in result.lower()

    def test_removes_master_bathroom(self):
        """Should remove 'master bathroom' location specifier."""
        result = normalize_material_name("Keramik Master Bathroom 25x40")
        assert "master" not in result.lower()
        assert "bathroom" not in result.lower()

    def test_removes_living_dining_kitchen(self):
        """Should remove 'living dining kitchen' location specifier."""
        result = normalize_material_name("Granit Living Dining Kitchen 60x60")
        assert "living" not in result.lower()
        assert "dining" not in result.lower()
        assert "kitchen" not in result.lower()

    def test_removes_lantai_floor_number(self):
        """Should remove 'lantai N' floor number specifier."""
        result = normalize_material_name("Granit Lantai 2 Premium")
        # 'lantai 2' should be removed
        assert "lantai 2" not in result.lower()

    def test_keeps_dimension_after_lantai(self):
        """'Lantai 60x60' is a dimension token, not a floor number — must be preserved."""
        assert normalize_material_name("Granit Lantai 60x60") == "granit lantai 60x60"

    def test_still_strips_floor_numbers(self):
        """Floor specifiers like 'Lantai 2' without a dimension must still be removed."""
        result = normalize_material_name("Granit Lantai 2 Premium")
        assert "lantai 2" not in result
        assert "premium" in result

    def test_removes_area_specifier(self):
        """Should remove 'area <word>' specifier."""
        result = normalize_material_name("Cat Tembok Area Kamar")
        assert "area" not in result.lower()
        assert "kamar" not in result.lower()

    def test_collapses_whitespace(self):
        """Should collapse multiple spaces to single space."""
        result = normalize_material_name("Pas.  Granit   Lantai    60x60")
        assert "  " not in result

    def test_strips_leading_trailing_whitespace(self):
        """Should strip leading and trailing whitespace."""
        result = normalize_material_name("  Granit Dinding Premium  ")
        assert result == "granit dinding premium"

    def test_combined_normalization(self):
        """Should handle multiple normalization rules in one description."""
        result = normalize_material_name(
            "Pas. Granit Lantai (Suply By Owner) Master Bed Room 60x60"
        )
        # Should be left with essentially "granit 60x60" (lantai is kept unless part of floor specifier)
        assert "pas" not in result
        assert "suply" not in result
        assert "owner" not in result
        assert "master" not in result
        assert "bed" not in result
        assert "room" not in result

    def test_lowercases_result(self):
        """Should return lowercase result."""
        result = normalize_material_name("GRANIT LANTAI PREMIUM")
        assert result == "granit lantai premium"


class TestBuildSearchQueryBrandStrip:
    """Brand markers (ex/eks/setara/merk/merek) and trailing brand words are stripped."""

    def test_ex_brand_stripped_dimension_preserved(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Granit Ex Roman 60x60") == "granit 60x60"

    def test_setara_brand_stripped_to_end(self):
        from app.services.boq_pricer import build_search_query
        # Descriptor loss ('putih') is an accepted tradeoff — generalizes the
        # query, never touches the head noun.
        assert build_search_query("Cat Setara Jotun Putih") == "cat"

    def test_ex_with_dot_stripped(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Keramik Lantai Ex. Romance") == "keramik lantai"

    def test_merk_stripped(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Semen Merk Tiga Roda") == "semen"

    def test_no_marker_unchanged(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Granit Dinding 60x60") == "granit dinding 60x60"

    def test_ex_inside_word_not_stripped(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Kayu Expose 4x6") == "kayu expose 4x6"

    def test_normalization_still_applied(self):
        from app.services.boq_pricer import build_search_query
        assert build_search_query("Pas. Granit Ex Roman 60x60") == "granit 60x60"


class TestNormalizeShortQuerySkipped:
    """Tests that short queries (< 3 chars) are skipped in batch processing."""

    def test_normalize_returns_short_string(self):
        """When normalization produces < 3 chars, batch_price_materials skips the item."""
        # An item whose description normalizes to something < 3 chars
        short_item = {"id": "1", "description": "AB", "item_type": "material"}
        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {}
        mock_provider.rank_results.return_value = []

        result = batch_price_materials(
            items=[short_item],
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        # Should return empty list since the only item was skipped
        assert result == []
        # Provider should not have been called
        mock_provider.batch_search_sync.assert_not_called()

    def test_empty_description_skipped(self):
        """Items with empty descriptions are skipped."""
        empty_item = {"id": "2", "description": "", "item_type": "material"}
        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {}

        result = batch_price_materials(
            items=[empty_item],
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        assert result == []
        mock_provider.batch_search_sync.assert_not_called()


# =============================================================================
# _build_match_from_scrape Tests
# =============================================================================


def _make_best_seller_score(
    name: str = "Granit Lantai 60x60",
    price_idr: int = 150000,
    url: str = "https://tokopedia.com/product/123",
    seller: str = "Toko Bangunan",
    location: str = "Jakarta",
    rating: float = 4.5,
    sold_count: int = 200,
    total_score: float = 0.85,
) -> BestSellerScore:
    """Helper to create a BestSellerScore for testing."""
    return BestSellerScore(
        product={
            "name": name,
            "price_idr": price_idr,
            "url": url,
            "shop": seller,
            "location": location,
            "rating": rating,
            "sold_count": sold_count,
        },
        total_score=total_score,
        rating_score=0.4,
        sales_score=0.3,
        price_score=0.15,
    )


class TestBuildMatchFromScrapeWithResult:
    """Tests for _build_match_from_scrape when a BestSellerScore is provided."""

    def test_market_unit_price_from_product_price_idr(self):
        """Should set market_unit_price from product['price_idr']."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.market_unit_price == Decimal("150000")

    def test_market_total_calculation(self):
        """Should compute market_total = market_unit_price * quantity."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.market_total == Decimal("1500000")

    def test_price_difference_calculation(self):
        """Should compute price_difference = contractor_unit_price - market_unit_price."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.price_difference == Decimal("50000")

    def test_price_difference_pct_calculation(self):
        """Should compute price_difference_pct = (diff / contractor_price) * 100."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        # (200000 - 150000) / 200000 * 100 = 25.0
        assert match.price_difference_pct == 25.0

    def test_match_confidence_word_overlap(self):
        """Should compute match_confidence from word overlap between query and product name."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        # Product name has 2 of 3 query words ("granit", "lantai")
        best = _make_best_seller_score(name="Granit Lantai Premium Hitam")

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        # query words: {"granit", "lantai", "60x60"} (3 words)
        # product words: {"granit", "lantai", "premium", "hitam"} (4 words)
        # overlap: {"granit", "lantai"} = 2
        # confidence: 2/3 = 0.666...
        assert abs(match.match_confidence - (2 / 3)) < 0.01

    def test_result_has_marketplace_result(self):
        """Should populate the MarketplaceResult fields correctly."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 200000, "quantity": 10}
        best = _make_best_seller_score(
            name="Granit Lantai 60x60 Premium",
            price_idr=150000,
            url="https://tokopedia.com/product/123",
            seller="Toko Bangunan",
            location="Jakarta",
            rating=4.5,
            sold_count=200,
            total_score=0.85,
        )

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.result is not None
        assert match.result.product_name == "Granit Lantai 60x60 Premium"
        assert match.result.price_idr == 150000
        assert match.result.url == "https://tokopedia.com/product/123"
        assert match.result.seller == "Toko Bangunan"
        assert match.result.seller_location == "Jakarta"
        assert match.result.rating == 4.5
        assert match.result.sold_count == 200
        assert match.result.best_seller_score == 0.85
        assert match.result.source == MarketplaceSource.TOKOPEDIA

    def test_from_cache_is_false(self):
        """Should set from_cache=False for scrape results."""
        item = {"description": "Granit", "contractor_unit_price": 100000, "quantity": 1}
        best = _make_best_seller_score()

        match = _build_match_from_scrape(item, "granit", best)

        assert match.from_cache is False


class TestBuildMatchFromScrapeNoResult:
    """Tests for _build_match_from_scrape when best=None."""

    def test_result_is_none(self):
        """Should set result=None when no marketplace result found."""
        item = {"description": "Unknown Material", "contractor_unit_price": 100000, "quantity": 5}

        match = _build_match_from_scrape(item, "unknown material", None)

        assert match.result is None

    def test_pricing_fields_are_none(self):
        """Should set all pricing fields to None."""
        item = {"description": "Unknown Material", "contractor_unit_price": 100000, "quantity": 5}

        match = _build_match_from_scrape(item, "unknown material", None)

        assert match.market_unit_price is None
        assert match.market_total is None
        assert match.price_difference is None
        assert match.price_difference_pct is None

    def test_match_confidence_is_zero(self):
        """Should set match_confidence to 0.0 when no result."""
        item = {"description": "Unknown Material", "contractor_unit_price": 100000, "quantity": 5}

        match = _build_match_from_scrape(item, "unknown material", None)

        assert match.match_confidence == 0.0

    def test_search_query_preserved(self):
        """Should preserve the search query even with no result."""
        item = {"description": "Unknown Material", "contractor_unit_price": 100000, "quantity": 5}

        match = _build_match_from_scrape(item, "unknown material", None)

        assert match.search_query == "unknown material"

    def test_from_cache_is_false(self):
        """Should set from_cache=False."""
        item = {"description": "Unknown Material", "contractor_unit_price": 100000, "quantity": 5}

        match = _build_match_from_scrape(item, "unknown material", None)

        assert match.from_cache is False


class TestBuildMatchZeroContractorPrice:
    """Tests for _build_match_from_scrape when contractor_unit_price is 0."""

    def test_price_difference_pct_is_zero(self):
        """When contractor_unit_price is 0, price_difference_pct should be 0."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 0, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.price_difference_pct == 0.0

    def test_price_difference_is_zero(self):
        """When contractor_unit_price is 0, price_difference should be 0."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": 0, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.price_difference == Decimal("0")

    def test_none_contractor_price_treated_as_zero(self):
        """When contractor_unit_price is None, should be treated as 0."""
        item = {"description": "Granit Lantai 60x60", "contractor_unit_price": None, "quantity": 10}
        best = _make_best_seller_score(price_idr=150000)

        match = _build_match_from_scrape(item, "granit lantai 60x60", best)

        assert match.price_difference_pct == 0.0


# =============================================================================
# batch_price_materials Tests
# =============================================================================


class TestBatchPriceMaterialsCallsProvider:
    """Tests that batch_price_materials calls the provider correctly."""

    def test_calls_batch_search_sync_with_normalized_queries(self):
        """Should call provider.batch_search_sync with normalized material names."""
        items = [
            {"id": "1", "description": "Pas. Granit Dinding Premium", "contractor_unit_price": 200000, "quantity": 10},
            {"id": "2", "description": "Instalasi Pipa PVC 4 Inch", "contractor_unit_price": 50000, "quantity": 20},
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {
            "granit dinding premium": [{"name": "Granit Dinding Premium", "price_idr": 150000}],
            "pipa pvc 4 inch": [{"name": "Pipa PVC 4 inch", "price_idr": 30000}],
        }

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        mock_provider.rank_results.side_effect = mock_rank

        batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        mock_provider.batch_search_sync.assert_called_once()
        call_args = mock_provider.batch_search_sync.call_args
        queries = call_args[0][0]  # first positional arg
        assert "granit dinding premium" in queries
        assert "pipa pvc 4 inch" in queries

    def test_calls_rank_results_for_each_nonempty_result(self):
        """Should call provider.rank_results for items with candidates."""
        items = [
            {"id": "1", "description": "Granit Dinding Premium", "contractor_unit_price": 200000, "quantity": 10},
            {"id": "2", "description": "Unknown Material XYZ", "contractor_unit_price": 50000, "quantity": 5},
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {
            "granit dinding premium": [{"name": "Granit", "price_idr": 150000}],
            "unknown material xyz": [],  # No results
        }
        mock_provider.rank_results.return_value = [
            _make_best_seller_score(name="Granit", price_idr=150000),
        ]

        batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        # rank_results called once (for granit), not for empty results
        assert mock_provider.rank_results.call_count == 1

    def test_returns_item_match_pairs(self):
        """Should return (item, MaterialPriceMatch) pairs keyed to the source items."""
        items = [
            {"id": "1", "description": "Granit Dinding Premium", "contractor_unit_price": 200000, "quantity": 10},
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {
            "granit dinding premium": [{"name": "Granit Dinding Premium", "price_idr": 150000}],
        }
        mock_provider.rank_results.return_value = [
            _make_best_seller_score(name="Granit Dinding Premium", price_idr=150000),
        ]

        result = batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        assert len(result) == 1
        item, match = result[0]
        assert item["id"] == "1"
        assert isinstance(match, MaterialPriceMatch)


class TestBatchPriceMaterialsRespectsMaxLookups:
    """Tests that batch_price_materials respects the max_lookups parameter."""

    def test_only_processes_max_lookups_items(self):
        """With max_lookups=2 and 5 items, only 2 are sent to provider."""
        items = [
            {"id": str(i), "description": f"Material {i} Long Name", "contractor_unit_price": 100000, "quantity": 1}
            for i in range(5)
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {}
        mock_provider.rank_results.return_value = []

        result = batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=2,
        )

        # batch_search_sync should have been called with exactly 2 queries
        call_args = mock_provider.batch_search_sync.call_args
        queries = call_args[0][0]
        assert len(queries) == 2

    def test_returns_matches_only_for_processed_items(self):
        """Should return matches only for items that were processed."""
        items = [
            {"id": str(i), "description": f"Material {i} Long Name", "contractor_unit_price": 100000, "quantity": 1}
            for i in range(5)
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {
            f"material {i} long name": [] for i in range(5)
        }
        mock_provider.rank_results.return_value = []

        result = batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=2,
        )

        assert len(result) == 2


class TestBatchPriceMaterialsPrioritizesOwnerSupply:
    """Tests that batch_price_materials prioritizes owner_supply items."""

    def test_owner_supply_items_processed_first(self):
        """Owner supply items should come first in the lookup queue."""
        items = [
            {"id": "1", "description": "Regular Material ABC", "contractor_unit_price": 100000, "quantity": 1, "is_owner_supply": False},
            {"id": "2", "description": "Owner Supply Material DEF", "contractor_unit_price": 200000, "quantity": 1, "is_owner_supply": True},
            {"id": "3", "description": "Another Regular GHI", "contractor_unit_price": 150000, "quantity": 1, "is_owner_supply": False},
            {"id": "4", "description": "Another Owner Supply JKL", "contractor_unit_price": 250000, "quantity": 1, "is_owner_supply": True},
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {}
        mock_provider.rank_results.return_value = []

        batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=2,
        )

        # With max_lookups=2, only the 2 owner_supply items should be processed.
        # Inspect the FIRST call (original queries); a fallback second call may
        # also have fired for zero-candidate items.
        first_call_queries = mock_provider.batch_search_sync.call_args_list[0][0][0]
        assert len(first_call_queries) == 2
        # Both queries should be from owner_supply items
        assert "owner supply material def" in first_call_queries
        assert "another owner supply jkl" in first_call_queries

    def test_non_owner_supply_after_owner_supply(self):
        """When max_lookups allows, non-owner_supply items come after owner_supply."""
        items = [
            {"id": "1", "description": "Regular Material ABC", "contractor_unit_price": 100000, "quantity": 1, "is_owner_supply": False},
            {"id": "2", "description": "Owner Supply Material DEF", "contractor_unit_price": 200000, "quantity": 1, "is_owner_supply": True},
        ]

        mock_provider = MagicMock()
        mock_provider.batch_search_sync.return_value = {}
        mock_provider.rank_results.return_value = []

        batch_price_materials(
            items=items,
            provider=mock_provider,
            supabase_client=MagicMock(),
            max_lookups=10,
        )

        # Inspect the FIRST call (original queries); a fallback second call may
        # also have fired for zero-candidate items.
        first_call_queries = mock_provider.batch_search_sync.call_args_list[0][0][0]
        assert len(first_call_queries) == 2
        # Owner supply should be first
        assert first_call_queries[0] == "owner supply material def"
        assert first_call_queries[1] == "regular material abc"


# =============================================================================
# persist_price_results Tests
# =============================================================================


class TestPersistPriceResults:
    """Tests for persist_price_results."""

    def test_calls_update_for_each_item_with_result(self):
        """Should call supabase.table('boq_items').update(...) for each match."""
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()

        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock()

        items = [
            {"id": "item-1", "description": "Granit Lantai 60x60"},
            {"id": "item-2", "description": "Pipa PVC 4 inch"},
        ]

        match1 = MaterialPriceMatch(
            search_query="granit lantai 60x60",
            result=MagicMock(
                product_name="Granit Lantai Premium",
                price_idr=150000,
                url="https://tokopedia.com/p1",
                seller="Toko A",
                seller_location="Jakarta",
                rating=4.5,
                sold_count=200,
            ),
            match_confidence=0.8,
            market_unit_price=Decimal("150000"),
            market_total=Decimal("1500000"),
            price_difference=Decimal("50000"),
            price_difference_pct=25.0,
            from_cache=False,
        )

        match2 = MaterialPriceMatch(
            search_query="pipa pvc 4 inch",
            result=None,
            match_confidence=0.0,
            market_unit_price=None,
            market_total=None,
            price_difference=None,
            price_difference_pct=None,
            from_cache=False,
        )

        persist_price_results(
            supabase_client=mock_supabase,
            job_id="job-123",
            pairs=list(zip(items, [match1, match2])),
        )

        # Should have called table("boq_items") twice
        assert mock_supabase.table.call_count == 2
        mock_supabase.table.assert_called_with("boq_items")

    def test_update_includes_correct_fields_for_matched_result(self):
        """Should include all pricing fields when a marketplace result exists."""
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()

        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock()

        items = [{"id": "item-1", "description": "Granit Lantai 60x60"}]

        match = MaterialPriceMatch(
            search_query="granit lantai 60x60",
            result=MagicMock(
                product_name="Granit Lantai Premium",
                price_idr=150000,
                url="https://tokopedia.com/p1",
                seller="Toko A",
                seller_location="Jakarta",
                rating=4.5,
                sold_count=200,
            ),
            match_confidence=0.8,
            market_unit_price=Decimal("150000"),
            market_total=Decimal("1500000"),
            price_difference=Decimal("50000"),
            price_difference_pct=25.0,
            from_cache=False,
        )

        persist_price_results(
            supabase_client=mock_supabase,
            job_id="job-123",
            pairs=list(zip(items, [match])),
        )

        # Get the update data passed to .update()
        update_call = mock_table.update.call_args
        update_data = update_call[0][0]

        assert update_data["search_query"] == "granit lantai 60x60"
        assert update_data["tokopedia_product_name"] == "Granit Lantai Premium"
        assert update_data["tokopedia_price"] == 150000
        assert update_data["tokopedia_url"] == "https://tokopedia.com/p1"
        assert update_data["tokopedia_seller"] == "Toko A"
        assert update_data["tokopedia_seller_location"] == "Jakarta"
        assert update_data["tokopedia_rating"] == 4.5
        assert update_data["tokopedia_sold_count"] == 200
        assert update_data["match_confidence"] == 0.8
        assert update_data["market_unit_price"] == 150000.0
        assert update_data["market_total"] == 1500000.0
        assert update_data["price_difference"] == 50000.0
        assert update_data["price_difference_percent"] == 25.0

        # Should filter by item ID
        mock_update.eq.assert_called_with("id", "item-1")

    def test_update_for_no_result_only_has_search_query(self):
        """When no marketplace result, should only set search_query."""
        mock_supabase = MagicMock()
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()

        mock_supabase.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock()

        items = [{"id": "item-1", "description": "Unknown Material"}]

        match = MaterialPriceMatch(
            search_query="unknown material",
            result=None,
            match_confidence=0.0,
            market_unit_price=None,
            market_total=None,
            price_difference=None,
            price_difference_pct=None,
            from_cache=False,
        )

        persist_price_results(
            supabase_client=mock_supabase,
            job_id="job-123",
            pairs=list(zip(items, [match])),
        )

        update_call = mock_table.update.call_args
        update_data = update_call[0][0]

        assert update_data == {"search_query": "unknown material"}

    def test_skips_items_without_id(self):
        """Should skip items that have no 'id' field."""
        mock_supabase = MagicMock()

        items = [{"description": "No ID Material"}]  # No 'id' key

        match = MaterialPriceMatch(
            search_query="no id material",
            result=None,
            match_confidence=0.0,
            market_unit_price=None,
            market_total=None,
            price_difference=None,
            price_difference_pct=None,
            from_cache=False,
        )

        persist_price_results(
            supabase_client=mock_supabase,
            job_id="job-123",
            pairs=list(zip(items, [match])),
        )

        # Should not have called table() at all
        mock_supabase.table.assert_not_called()


# =============================================================================
# TestMatchQualityGate Tests
# =============================================================================


class TestMatchQualityGate:
    """Matches failing confidence or price-sanity checks become no-result matches."""

    def _run(self, items, products_by_query, **kwargs):
        provider = MagicMock()
        provider.batch_search_sync.return_value = products_by_query

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        provider.rank_results.side_effect = mock_rank
        return batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(), **kwargs
        )

    def test_rejects_low_confidence_match(self):
        """Zero word overlap between query and product name -> gated out."""
        items = [{"id": "1", "description": "Vacum Cover Kolam", "quantity": 1,
                  "contractor_unit_price": 120000}]
        products = {"vacum cover kolam": [
            {"name": "Plastik Penyimpanan Baju", "price_idr": 5500},
        ]}
        pairs = self._run(items, products)
        item, match = pairs[0]
        assert match.result is None
        assert match.match_confidence == 0.0
        assert match.market_unit_price is None

    def test_rejects_price_outside_sanity_band(self):
        """Market price >5x contractor price -> gated even with name overlap."""
        items = [{"id": "1", "description": "Batako Anak Tangga", "quantity": 1,
                  "contractor_unit_price": 105000}]
        products = {"batako anak tangga": [
            {"name": "Batako anak tangga premium", "price_idr": 4320000},
        ]}
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None

    def test_accepts_reasonable_match(self):
        # "Granit 60x60" normalizes to "granit 60x60" (no lantai/floor-number stripping)
        items = [{"id": "1", "description": "Granit 60x60", "quantity": 2,
                  "contractor_unit_price": 200000}]
        products = {"granit 60x60": [
            {"name": "Granit 60x60 Glossy", "price_idr": 150000},
        ]}
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is not None
        assert match.market_unit_price == Decimal("150000")

    def test_no_price_band_check_when_contractor_price_missing(self):
        """Without a contractor price there is no band; confidence alone decides."""
        # "Granit 60x60" normalizes to "granit 60x60" (no lantai/floor-number stripping)
        items = [{"id": "1", "description": "Granit 60x60", "quantity": 1,
                  "contractor_unit_price": 0}]
        products = {"granit 60x60": [
            {"name": "Granit 60x60 Glossy", "price_idr": 150000},
        ]}
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is not None

    def test_rejects_cached_price_outside_sanity_band(self):
        """A cached median far outside the contractor price band is gated out."""
        from datetime import datetime, timezone, timedelta

        items = [{"id": "1", "description": "Waterproofing Kolam", "quantity": 1,
                  "contractor_unit_price": 75000}]

        fresh_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        mock_sb = MagicMock()
        cache_result = MagicMock()
        cache_result.data = [{
            "normalized_name": "kolam waterproofing",
            "price_median": 2900000,  # ~39x contractor price
            "price_updated_at": fresh_time,
            "name_id": "Waterproofing Kolam",
        }]
        mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value = cache_result

        provider = MagicMock()
        pairs = batch_price_materials(
            items=items, provider=provider, supabase_client=mock_sb,
        )

        _, match = pairs[0]
        assert match.result is None
        assert match.from_cache is True
        assert match.market_unit_price is None
        # cache hit means no scrape should have happened
        provider.batch_search_sync.assert_not_called()


# =============================================================================
# F22: Imitation-Product Filter Tests
# =============================================================================


class TestImitationProductFilter:
    """
    Imitation/decor products (stickers, wallpaper, vinyl) must not match
    queries for real construction materials (F22 fix).
    """

    def _run(self, items, products_by_query, **kwargs):
        provider = MagicMock()
        provider.batch_search_sync.return_value = products_by_query

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        provider.rank_results.side_effect = mock_rank
        return batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(), **kwargs
        )

    def test_wallpaper_product_rejected_for_granit_dinding_query(self):
        """
        Production case: 'granit dinding' query should not match a PVC wallpaper
        sticker product even though every query word appears in the long title.
        """
        items = [{"id": "1", "description": "Granit Dinding Kolam Renang",
                  "contractor_unit_price": 180000, "quantity": 10}]
        products = {
            "granit dinding kolam renang": [
                {
                    "name": (
                        "280CM X 120CM MARBLE GRANIT GULUNG BESAR PVC "
                        "WALLPEPER DINDING VINY WALLPAPER STIKER DINDING"
                    ),
                    "price_idr": 185000,
                },
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Wallpaper sticker must not match a granit query"
        assert match.match_confidence == 0.0

    def test_legitimate_granit_product_not_rejected(self):
        """A real granite product must still be accepted for a granit query."""
        items = [{"id": "1", "description": "Granit Dinding 60x60",
                  "contractor_unit_price": 200000, "quantity": 5}]
        products = {
            "granit dinding 60x60": [
                {"name": "Granit Dinding 60x60 Polished Premium", "price_idr": 190000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is not None, "Real granit product must be accepted"
        assert match.market_unit_price is not None

    def test_wallpaper_product_accepted_for_wallpaper_query(self):
        """
        When the query itself contains 'wallpaper', a wallpaper product is
        NOT rejected — the buyer is actually pricing wallpaper.
        """
        items = [{"id": "1", "description": "Wallpaper Dinding Premium",
                  "contractor_unit_price": 150000, "quantity": 3}]
        products = {
            "wallpaper dinding premium": [
                {"name": "Wallpaper Dinding Premium Motif Bunga 10M", "price_idr": 140000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is not None, "Wallpaper product must be accepted when query requests wallpaper"

    def test_sticker_token_also_triggers_rejection(self):
        """Products containing 'stiker' (Indonesian spelling) are rejected for real material queries."""
        items = [{"id": "1", "description": "Batu Alam Dinding",
                  "contractor_unit_price": 250000, "quantity": 2}]
        products = {
            "batu alam dinding": [
                {"name": "Stiker Dinding Motif Batu Alam 3D", "price_idr": 240000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Stiker product must not match a real material query"

    def test_imitasi_token_triggers_rejection(self):
        """Products explicitly labelled 'imitasi' are rejected for real material queries."""
        items = [{"id": "1", "description": "Kayu Solid Lantai",
                  "contractor_unit_price": 300000, "quantity": 4}]
        products = {
            "kayu solid lantai": [
                {"name": "Kayu Imitasi Lantai Vinyl PVC", "price_idr": 290000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Imitasi product must not match a real material query"


# =============================================================================
# Head-Noun Gate Tests
# =============================================================================


class TestHeadNounGate:
    """
    The head noun (first query token of length >= 3) must appear in the product
    name. This catches incidental-word matches like 'atap kaca' → product 'Kanopi
    akrilik kaca' where only the incidental word 'kaca' overlapped.
    """

    def test_rejects_when_head_noun_absent_despite_above_threshold_confidence(self):
        """
        Production case: 'atap kaca topian' (glass canopy) matched
        'Void Kanopi Sliding akrilik kaca' at confidence 0.333 — 'atap' (the
        material noun) is not in the product name. The head-noun gate must catch
        this even though confidence 0.333 >= 0.3 floor.
        """
        item = {"id": "1", "description": "Atap Kaca Topian Pintu Dan Jendela",
                "contractor_unit_price": 500000, "quantity": 10}
        best = _make_best_seller_score(
            name="Void Kanopi Sliding akrilik kaca",
            price_idr=480000,
        )
        match = _build_match_from_scrape(item, "atap kaca topian", best,
                                         min_confidence=0.3, max_price_ratio=5.0)
        assert match.result is None, "head-noun 'atap' not in product → must be rejected"
        assert match.match_confidence == 0.0

    def test_accepts_when_head_noun_present(self):
        """query 'granit lantai 60x60' + product 'Granit Lantai 60x60 Glossy' → accepted, confidence 1.0."""
        item = {"id": "1", "description": "Granit Lantai 60x60",
                "contractor_unit_price": 200000, "quantity": 2}
        best = _make_best_seller_score(
            name="Granit Lantai 60x60 Glossy",
            price_idr=190000,
        )
        match = _build_match_from_scrape(item, "granit lantai 60x60", best,
                                         min_confidence=0.3, max_price_ratio=5.0)
        assert match.result is not None
        assert match.match_confidence == 1.0

    def test_gate_passes_when_no_token_of_length_3_or_more(self):
        """When the query has no token >= 3 chars, the gate cannot judge and must pass."""
        item = {"id": "1", "description": "AC",
                "contractor_unit_price": 100000, "quantity": 1}
        # Query "ac" has no token of len >= 3; head-noun gate must pass
        best = _make_best_seller_score(
            name="AC Split Unit",
            price_idr=95000,
        )
        match = _build_match_from_scrape(item, "ac", best,
                                         min_confidence=0.0, max_price_ratio=5.0)
        # Head-noun gate passes; match accepted (confidence 0.0 only matters against min_confidence=0.0)
        assert match.result is not None


# =============================================================================
# _walk_candidates Tests
# =============================================================================


class TestWalkCandidates:
    """_walk_candidates: first gate-passing candidate wins; none pass -> no-result."""

    def _item(self, **overrides):
        item = {"id": "1", "description": "Granit Dinding 60x60",
                "contractor_unit_price": 200000, "quantity": 10}
        item.update(overrides)
        return item

    def test_accepts_first_passing_candidate(self):
        from app.services.boq_pricer import _walk_candidates
        junk = _make_best_seller_score(name="Vacuum Storage Bag Jumbo", price_idr=150000)
        good = _make_best_seller_score(name="Granit Dinding 60x60 Glossy", price_idr=190000)

        match, accepted = _walk_candidates(self._item(), "granit dinding 60x60", [junk, good])

        assert match.result is not None
        assert match.result.product_name == "Granit Dinding 60x60 Glossy"
        assert accepted is good

    def test_all_rejected_returns_no_result_and_none(self):
        from app.services.boq_pricer import _walk_candidates
        junk1 = _make_best_seller_score(name="Vacuum Storage Bag Jumbo", price_idr=150000)
        junk2 = _make_best_seller_score(name="Kursi Plastik Serbaguna", price_idr=160000)

        match, accepted = _walk_candidates(self._item(), "granit dinding 60x60", [junk1, junk2])

        assert match.result is None
        assert match.match_confidence == 0.0
        assert accepted is None

    def test_empty_ranked_list_returns_no_result(self):
        from app.services.boq_pricer import _walk_candidates

        match, accepted = _walk_candidates(self._item(), "granit dinding 60x60", [])

        assert match.result is None
        assert accepted is None

    def test_candidate_beyond_rank_five_reachable(self):
        """Pins the truncation fix end-to-end: rank 7 of 7 must be reachable."""
        from app.services.boq_pricer import _walk_candidates
        junk = [
            _make_best_seller_score(name=f"Kursi Plastik Model {i}", price_idr=150000)
            for i in range(6)
        ]
        good = _make_best_seller_score(name="Granit Dinding 60x60 Polished", price_idr=190000)

        match, accepted = _walk_candidates(self._item(), "granit dinding 60x60", junk + [good])

        assert match.result is not None
        assert accepted is good


class TestCandidateWalkPipeline:
    """batch_price_materials must judge every ranked candidate, not just ranked[0]."""

    @staticmethod
    def _mock_rank(results):
        scored = []
        for r in results:
            s = MagicMock()
            s.product = r
            s.total_score = 0.8
            scored.append(s)
        return scored

    def _provider(self, results_by_query):
        provider = MagicMock()
        provider.batch_search_sync.return_value = results_by_query
        provider.rank_results.side_effect = self._mock_rank
        return provider

    def test_second_ranked_candidate_priced_when_top_is_junk(self):
        items = [{"id": "1", "description": "Granit Dinding 60x60",
                  "contractor_unit_price": 200000, "quantity": 10}]
        provider = self._provider({
            "granit dinding 60x60": [
                {"name": "Vacuum Storage Bag Jumbo", "price_idr": 150000},
                {"name": "Granit Dinding 60x60 Glossy", "price_idr": 190000},
            ]
        })

        pairs = batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(),
        )

        _, match = pairs[0]
        assert match.result is not None
        assert match.result.product_name == "Granit Dinding 60x60 Glossy"

    def test_cache_write_receives_accepted_candidate(self):
        items = [{"id": "1", "description": "Granit Dinding 60x60",
                  "contractor_unit_price": 200000, "quantity": 10}]
        provider = self._provider({
            "granit dinding 60x60": [
                {"name": "Vacuum Storage Bag Jumbo", "price_idr": 150000},
                {"name": "Granit Dinding 60x60 Glossy", "price_idr": 190000},
            ]
        })

        with patch("app.services.boq_pricer._write_cache") as mock_wc:
            batch_price_materials(
                items=items, provider=provider, supabase_client=MagicMock(),
            )

        assert mock_wc.call_count == 1
        best_product = mock_wc.call_args[0][3]
        assert best_product["name"] == "Granit Dinding 60x60 Glossy"

    def test_no_cache_write_when_all_candidates_rejected(self):
        items = [{"id": "1", "description": "Granit Dinding 60x60",
                  "contractor_unit_price": 200000, "quantity": 10}]
        provider = self._provider({
            "granit dinding 60x60": [
                {"name": "Vacuum Storage Bag Jumbo", "price_idr": 150000},
            ]
        })

        with patch("app.services.boq_pricer._write_cache") as mock_wc:
            pairs = batch_price_materials(
                items=items, provider=provider, supabase_client=MagicMock(),
            )

        mock_wc.assert_not_called()
        _, match = pairs[0]
        assert match.result is None


# =============================================================================
# F6: Query-Simplification Fallback Tests
# =============================================================================


class TestSimplifyQuery:
    """Unit tests for the simplify_query helper."""

    def test_long_query_truncated_to_three_words(self):
        assert simplify_query("keramik dinding kolam renang ex romance") == "keramik dinding kolam"

    def test_exactly_four_words_returns_three(self):
        assert simplify_query("granit dinding 60x60 premium") == "granit dinding 60x60"

    def test_three_word_query_drops_last_token(self):
        """2-3 token queries broaden by dropping the trailing qualifier (head noun kept)."""
        assert simplify_query("granit dinding 60x60") == "granit dinding"

    def test_two_word_query_drops_last_token(self):
        assert simplify_query("granit dinding") == "granit"

    def test_one_word_query_returns_empty(self):
        assert simplify_query("granit") == ""

    def test_five_word_query(self):
        assert simplify_query("keramik dinding kolam renang premium") == "keramik dinding kolam"


class TestQuerySimplificationFallback:
    """
    When the first scrape returns zero candidates for a query, a ONE-time
    retry is made with a simplified query — first 3 tokens, or last token
    dropped for 2-3-token queries (F6 fix + coverage retry).
    """

    def _make_provider(self, first_results: dict, second_results: dict) -> MagicMock:
        """Provider that returns first_results on call 1, second_results on call 2."""
        provider = MagicMock()
        provider.batch_search_sync.side_effect = [first_results, second_results]

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        provider.rank_results.side_effect = mock_rank
        return provider

    def test_five_word_query_retried_with_three_word_simplified(self):
        """A 5-word query that returns nothing is retried with its first 3 words."""
        items = [{"id": "1",
                  "description": "Keramik Dinding Kolam Renang Ex Romance",
                  "contractor_unit_price": 120000,
                  "quantity": 5}]

        first = {"keramik dinding kolam renang ex romance": []}
        second = {"keramik dinding kolam": [
            {"name": "Keramik Dinding Kolam Renang 25x40", "price_idr": 115000},
        ]}

        provider = self._make_provider(first, second)
        pairs = batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 2
        # Second call must use the simplified query
        second_call_queries = provider.batch_search_sync.call_args_list[1][0][0]
        assert second_call_queries == ["keramik dinding kolam"]

        _, match = pairs[0]
        assert match.result is not None
        assert match.search_query == "keramik dinding kolam"

    def test_one_word_query_not_retried(self):
        """A single-token query cannot be broadened — no retry."""
        items = [{"id": "1", "description": "Granit",
                  "contractor_unit_price": 200000, "quantity": 2}]

        first = {"granit": []}
        provider = MagicMock()
        provider.batch_search_sync.return_value = first
        provider.rank_results.return_value = []

        pairs = batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 1
        _, match = pairs[0]
        assert match.result is None

    def test_mixed_batch_one_ok_one_fallback(self):
        """
        In a batch: item A has results on first call, item B needs fallback.
        Both should be correctly matched.
        """
        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
            {"id": "2", "description": "Keramik Dinding Kolam Renang Premium",
             "contractor_unit_price": 90000, "quantity": 8},
        ]

        first = {
            "granit lantai 60x60": [
                {"name": "Granit Lantai 60x60 Glossy", "price_idr": 190000},
            ],
            "keramik dinding kolam renang premium": [],
        }
        second = {
            "keramik dinding kolam": [
                {"name": "Keramik Dinding Kolam 25x40", "price_idr": 85000},
            ],
        }

        provider = self._make_provider(first, second)
        pairs = batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 2

        results = {item["id"]: match for item, match in pairs}

        # Item 1 matched on first round
        assert results["1"].result is not None
        assert results["1"].market_unit_price == 190000 or \
               results["1"].market_unit_price == __import__("decimal").Decimal("190000")

        # Item 2 matched via fallback
        assert results["2"].result is not None
        assert results["2"].search_query == "keramik dinding kolam"

    def test_fallback_no_results_still_no_match(self):
        """If the retry also returns nothing, the item stays as a no-result match."""
        items = [{"id": "1", "description": "Material Langka Tidak Dijual Online",
                  "contractor_unit_price": 500000, "quantity": 1}]

        first = {"material langka tidak dijual online": []}
        second = {"material langka tidak": []}

        provider = self._make_provider(first, second)
        pairs = batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 2
        _, match = pairs[0]
        assert match.result is None


class TestRetryOnAllRejected:
    """Items whose candidates were ALL gate-rejected get the one-round simplified retry."""

    @staticmethod
    def _mock_rank(results):
        scored = []
        for r in results:
            s = MagicMock()
            s.product = r
            s.total_score = 0.8
            scored.append(s)
        return scored

    def _provider(self, first, second):
        provider = MagicMock()
        provider.batch_search_sync.side_effect = [first, second]
        provider.rank_results.side_effect = self._mock_rank
        return provider

    def test_all_rejected_item_retried_with_simplified_query(self):
        items = [{"id": "1", "description": "Granit Dinding Premium Import",
                  "contractor_unit_price": 200000, "quantity": 2}]
        first = {"granit dinding premium import": [
            {"name": "Kursi Plastik Serbaguna", "price_idr": 190000},
        ]}
        second = {"granit dinding premium": [
            {"name": "Granit Dinding Premium 60x60", "price_idr": 195000},
        ]}

        provider = self._provider(first, second)
        pairs = batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 2
        second_call_queries = provider.batch_search_sync.call_args_list[1][0][0]
        assert second_call_queries == ["granit dinding premium"]

        _, match = pairs[0]
        assert match.result is not None
        assert match.search_query == "granit dinding premium"

    def test_two_word_all_rejected_retried_with_head_noun(self):
        """The drop-last-token rule makes the retry fire even for short cleaned queries."""
        items = [{"id": "1", "description": "Granit Dinding",
                  "contractor_unit_price": 200000, "quantity": 2}]
        first = {"granit dinding": [
            {"name": "Kursi Plastik Serbaguna", "price_idr": 190000},
        ]}
        second = {"granit": [
            {"name": "Granit Alam 60x60", "price_idr": 195000},
        ]}

        provider = self._provider(first, second)
        pairs = batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(),
        )

        assert provider.batch_search_sync.call_count == 2
        assert provider.batch_search_sync.call_args_list[1][0][0] == ["granit"]
        _, match = pairs[0]
        assert match.result is not None

    def test_accepted_retry_cached_under_simplified_key(self):
        items = [{"id": "1", "description": "Granit Dinding",
                  "contractor_unit_price": 200000, "quantity": 2}]
        first = {"granit dinding": [
            {"name": "Kursi Plastik Serbaguna", "price_idr": 190000},
        ]}
        second = {"granit": [
            {"name": "Granit Alam 60x60", "price_idr": 195000},
        ]}

        provider = self._provider(first, second)
        with patch("app.services.boq_pricer._write_cache") as mock_wc:
            batch_price_materials(
                items=items, provider=provider, supabase_client=MagicMock(),
            )

        assert mock_wc.call_count == 1
        args = mock_wc.call_args[0]
        assert args[1] == "granit"                      # query written
        assert args[2] == canonicalize_for_cache("granit")  # cache key


# =============================================================================
# Owner-Supply Band-Gate Bypass Tests
# =============================================================================


class TestOwnerSupplyBandGateBypass:
    """
    Owner-supply items carry the contractor's INSTALLATION LABOR rate, not a
    material purchase price.  Comparing a material market price to a labor rate
    would always fail the price-band gate.  For owner-supply items the band gate
    must be SKIPPED; confidence and imitation gates still apply.
    """

    def _run(self, items, products_by_query, **kwargs):
        provider = MagicMock()
        provider.batch_search_sync.return_value = products_by_query

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        provider.rank_results.side_effect = mock_rank
        return batch_price_materials(
            items=items, provider=provider, supabase_client=MagicMock(), **kwargs
        )

    def test_owner_supply_scrape_accepted_despite_6x_ratio(self):
        """
        Owner-supply granit: contractor price = 110,000 (labor rate), market
        price = 660,000 (6× contractor).  The match MUST be accepted because the
        price-band gate is skipped for owner-supply items.
        price_difference and price_difference_pct must be None (comparison
        between material price and labor rate is meaningless).
        market_unit_price and market_total must still be set (shopping-list value).
        """
        items = [
            {
                "id": "1",
                "description": "Pas. Granit Dinding (Granit Suply By Owner)",
                "quantity": 10.0,
                "contractor_unit_price": 110000,
                "is_owner_supply": True,
            }
        ]
        products = {
            "granit dinding": [
                {"name": "Granit Dinding 60x60 Premium", "price_idr": 660000},
            ]
        }
        pairs = self._run(items, products)
        assert len(pairs) == 1
        _, match = pairs[0]

        # Band gate skipped → match accepted
        assert match.result is not None, "Owner-supply match must be accepted despite 6× ratio"
        # Shopping-list values must be set
        assert match.market_unit_price == Decimal("660000")
        assert match.market_total == Decimal("6600000")
        # Price difference fields must be None (labor vs material comparison)
        assert match.price_difference is None, "price_difference must be None for owner-supply"
        assert match.price_difference_pct is None, "price_difference_pct must be None for owner-supply"

    def test_non_owner_supply_6x_still_rejected(self):
        """
        A non-owner-supply item at 6× contractor price must still be rejected
        by the price-band gate.
        """
        items = [
            {
                "id": "1",
                "description": "Granit Dinding Premium",
                "quantity": 10.0,
                "contractor_unit_price": 110000,
                "is_owner_supply": False,
            }
        ]
        products = {
            "granit dinding premium": [
                {"name": "Granit Dinding Premium 60x60", "price_idr": 660000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Non-owner-supply 6× match must still be rejected"

    def test_owner_supply_cache_accepted_despite_6x_ratio(self):
        """
        Cache path: owner-supply item with a cached median 6× the contractor
        (labor) price must be accepted; price_difference/pct must be None.
        """
        from datetime import datetime, timezone, timedelta
        from app.services.boq_pricer import _build_match_from_cache

        item = {
            "id": "1",
            "description": "Pas. Granit Dinding (Granit Suply By Owner)",
            "quantity": 5.0,
            "contractor_unit_price": 110000,
            "is_owner_supply": True,
        }
        cache_row = {
            "normalized_name": "granit dinding",
            "price_median": 660000,  # 6× labor rate
            "name_id": "Granit Dinding 60x60",
            "price_updated_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        }

        match = _build_match_from_cache(item, "granit dinding", cache_row, max_price_ratio=5.0)

        assert match.result is not None, "Cache owner-supply match must be accepted despite 6× ratio"
        assert match.market_unit_price == Decimal("660000")
        assert match.market_total == Decimal("3300000")
        assert match.price_difference is None
        assert match.price_difference_pct is None

    def test_owner_supply_imitation_still_rejected(self):
        """
        Skipping the band gate must not disable the imitation-product filter.
        A wallpaper sticker returned for an owner-supply granit query must still
        be rejected.
        """
        items = [
            {
                "id": "1",
                "description": "Pas. Granit Dinding (Granit Suply By Owner)",
                "quantity": 5.0,
                "contractor_unit_price": 110000,
                "is_owner_supply": True,
            }
        ]
        products = {
            "granit dinding": [
                {
                    "name": "WALLPAPER Granit Dinding Sticker PVC",
                    "price_idr": 660000,
                },
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Imitation product must still be rejected for owner-supply items"

    def test_owner_supply_low_confidence_still_rejected(self):
        """
        Skipping the band gate must not disable the confidence gate.
        Zero word overlap for an owner-supply item must still be rejected.
        """
        items = [
            {
                "id": "1",
                "description": "Pas. Granit Dinding (Granit Suply By Owner)",
                "quantity": 5.0,
                "contractor_unit_price": 110000,
                "is_owner_supply": True,
            }
        ]
        products = {
            "granit dinding": [
                {"name": "Plastik Pembungkus Makanan", "price_idr": 110000},
            ]
        }
        pairs = self._run(items, products)
        _, match = pairs[0]
        assert match.result is None, "Low-confidence match must still be rejected for owner-supply"


# =============================================================================
# Scrape-Batch Progress Tests
# =============================================================================


class TestScrapeBatchProgress:
    """
    Tests that batch_price_materials maps chunk completion (via batch_progress)
    onto the 55-80 window, and per-item post-processing onto 80-85.
    """

    def _make_provider_with_batch_progress(self, results_by_query: dict) -> MagicMock:
        """
        Build a provider mock whose batch_search_sync invokes batch_progress
        to simulate real TokopediaProvider chunk behaviour.

        The side_effect intercepts the keyword-only batch_progress kwarg and
        calls it once with (1, 1) — simulating a single actor chunk completing.
        """
        provider = MagicMock()

        def batch_side_effect(queries, limit_per_query=10, *, batch_progress=None):
            if batch_progress is not None:
                batch_progress(1, 1)
            return results_by_query

        provider.batch_search_sync.side_effect = batch_side_effect

        def mock_rank(results):
            scored = []
            for r in results:
                s = MagicMock()
                s.product = r
                s.total_score = 0.8
                scored.append(s)
            return scored

        provider.rank_results.side_effect = mock_rank
        return provider

    def test_progress_values_within_40_85(self):
        """All emitted progress values must lie in the 40-85 range."""
        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
            {"id": "2", "description": "Pipa PVC 4 Inch",
             "contractor_unit_price": 50000, "quantity": 5},
        ]
        products = {
            "granit lantai 60x60": [{"name": "Granit Lantai 60x60", "price_idr": 190000}],
            "pipa pvc 4 inch": [{"name": "Pipa PVC 4 inch", "price_idr": 45000}],
        }
        provider = self._make_provider_with_batch_progress(products)

        progress = []
        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            progress_callback=lambda pct: progress.append(pct),
        )

        assert len(progress) > 0
        assert all(40 <= v <= 85 for v in progress), f"Out of range: {progress}"

    def test_progress_is_monotonic(self):
        """Progress values must never decrease."""
        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
            {"id": "2", "description": "Pipa PVC 4 Inch",
             "contractor_unit_price": 50000, "quantity": 5},
        ]
        products = {
            "granit lantai 60x60": [{"name": "Granit Lantai 60x60", "price_idr": 190000}],
            "pipa pvc 4 inch": [{"name": "Pipa PVC 4 inch", "price_idr": 45000}],
        }
        provider = self._make_provider_with_batch_progress(products)

        progress = []
        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            progress_callback=lambda pct: progress.append(pct),
        )

        for i in range(1, len(progress)):
            assert progress[i] >= progress[i - 1], (
                f"Progress went backwards: {progress[i-1]} → {progress[i]} at index {i}"
            )

    def test_scrape_chunk_emits_value_in_55_to_80_window(self):
        """At least one emitted value must be in [55, 80] (the scrape-chunk window)."""
        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
        ]
        products = {
            "granit lantai 60x60": [{"name": "Granit Lantai 60x60", "price_idr": 190000}],
        }
        provider = self._make_provider_with_batch_progress(products)

        progress = []
        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            progress_callback=lambda pct: progress.append(pct),
        )

        scrape_window = [v for v in progress if 55 <= v <= 80]
        assert len(scrape_window) > 0, (
            f"Expected at least one value in 55-80 (scrape window), got {progress}"
        )

    def test_per_item_values_in_80_to_85_window(self):
        """Values emitted after the scrape batch completes must be in [80, 85]."""
        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
        ]
        products = {
            "granit lantai 60x60": [{"name": "Granit Lantai 60x60", "price_idr": 190000}],
        }
        provider = self._make_provider_with_batch_progress(products)

        progress = []
        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            progress_callback=lambda pct: progress.append(pct),
        )

        # The last value(s) should be in 80-85 (per-item post-scrape range)
        assert progress[-1] >= 80, f"Final progress {progress[-1]} not in 80-85 range"
        assert progress[-1] <= 85, f"Final progress {progress[-1]} exceeds 85"

    def test_cache_hits_only_jumps_to_85(self):
        """When all items are cache hits, progress should jump directly to 85."""
        from datetime import datetime, timezone, timedelta

        items = [
            {"id": "1", "description": "Granit Lantai 60x60",
             "contractor_unit_price": 200000, "quantity": 2},
        ]

        fresh_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_sb = MagicMock()
        cache_result = MagicMock()
        cache_result.data = [{
            "normalized_name": "60x60 granit lantai",
            "price_median": 190000,
            "price_updated_at": fresh_time,
            "name_id": "Granit Lantai 60x60",
        }]
        mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value = cache_result

        provider = MagicMock()
        progress = []
        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=mock_sb,
            progress_callback=lambda pct: progress.append(pct),
        )

        # Cache hit path: emits 40+int(15*1/1)=55 for the cache item, then 85 at end
        assert 85 in progress
        provider.batch_search_sync.assert_not_called()


class TestTokenizationPunctuation:
    """Head-noun and confidence must survive punctuation-joined marketplace titles."""

    def test_head_noun_found_across_hyphen(self):
        from app.services.boq_pricer import _head_noun_present
        # "granit" must be found even when the title fuses it with a hyphen.
        assert _head_noun_present("granit lantai 60x60", "Granit-Lantai 60x60 Glossy") is True

    def test_head_noun_found_across_pipe(self):
        from app.services.boq_pricer import _head_noun_present
        assert _head_noun_present("pipa pvc", "Pipa|PVC Rucika 4 inch") is True

    def test_head_noun_still_absent_when_truly_missing(self):
        from app.services.boq_pricer import _head_noun_present
        # The production false-positive: glass canopy query vs sliding-canopy product.
        assert _head_noun_present(
            "atap kaca topian pintu dan jendela",
            "Void Kanopi Sliding akrilik kaca | awning transparan",
        ) is False

    def test_confidence_counts_punctuation_joined_words(self):
        from app.services.boq_pricer import _match_confidence
        # All three query words present despite hyphen/comma fusion in the title.
        c = _match_confidence("granit lantai 60x60", "Granit-Lantai, 60x60 Premium")
        assert c == 1.0

    def test_dimension_token_preserved(self):
        from app.services.boq_pricer import _tokenize
        assert "60x60" in _tokenize("Granit Lantai 60x60")


class TestHeadNounPrecisionBias:
    """Documents the deliberate precision bias of the head-noun gate.

    The gate requires the query's head noun as a whole word in the product
    name. This intentionally drops spelling/synonym variants (e.g. plywood vs
    triplek, gypsum vs gipsum) rather than risk a wrong match feeding the
    customer-facing savings number. These assertions pin that tradeoff so any
    future softening (e.g. a synonym map) is a conscious change, and so the
    coverage cost is visible. Monitor production `boq_match_rejected` logs with
    reason=head_noun_missing to quantify real-world impact.
    """

    def test_synonym_head_noun_is_rejected(self):
        from app.services.boq_pricer import _head_noun_present
        # "plywood" query vs Indonesian-named equivalent → dropped (precision bias).
        assert _head_noun_present("plywood 9mm", "Triplek 9mm 122x244") is False

    def test_spelling_variant_head_noun_is_rejected(self):
        from app.services.boq_pricer import _head_noun_present
        # Spelling variant gipsum/gypsum → dropped (precision bias).
        assert _head_noun_present("gypsum board 9mm", "Gipsum Jayaboard 9mm") is False

    def test_exact_head_noun_still_accepted(self):
        from app.services.boq_pricer import _head_noun_present
        # The common case — exact material noun present — is unaffected.
        assert _head_noun_present("gypsum board 9mm", "Gypsum Jayaboard 9mm") is True
