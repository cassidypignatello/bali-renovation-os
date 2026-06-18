"""
Integration test for BoQ pricing pipeline.

Validates that process_boq_job_sync correctly wires extraction → pricing → persistence → summary.
All external services (Supabase, OpenAI, Apify) are mocked — no real API calls, no cost.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_supabase():
    """Build a mock Supabase client that tracks table operations."""
    client = MagicMock()

    # Track per-table state
    _tables: dict[str, list[dict]] = {
        "boq_jobs": [],
        "boq_items": [],
    }

    def make_table(name):
        table = MagicMock()

        # .insert().execute()
        def insert_fn(data):
            chain = MagicMock()
            if isinstance(data, list):
                _tables[name].extend(data)
            else:
                _tables[name].append(data)
            chain.execute.return_value = MagicMock(data=data)
            return chain
        table.insert.side_effect = insert_fn

        # .update().eq().execute()
        def update_fn(data):
            chain = MagicMock()
            eq_chain = MagicMock()

            def eq_fn(field, value):
                # Apply update to matching rows
                for row in _tables[name]:
                    if row.get(field) == value:
                        row.update(data)
                eq_chain.execute.return_value = MagicMock(data=[])
                return eq_chain

            chain.eq.side_effect = eq_fn
            return chain
        table.update.side_effect = update_fn

        # .select().eq().eq().execute() — chained filters
        def select_fn(*cols):
            chain = MagicMock()
            _filters = {}

            def eq_fn(field, value):
                _filters[field] = value
                filtered = [
                    row for row in _tables[name]
                    if all(row.get(k) == v for k, v in _filters.items())
                ]
                result = MagicMock()
                result.data = filtered
                result.execute.return_value = result
                # Allow further chaining
                inner = MagicMock()
                inner.eq = eq_fn
                inner.execute.return_value = result
                inner.data = filtered
                return inner

            chain.eq = eq_fn
            chain.execute.return_value = MagicMock(data=_tables[name])
            return chain

        table.select.side_effect = select_fn
        return table

    client.table.side_effect = make_table
    client._tables = _tables  # expose for assertions
    return client


@pytest.fixture
def sample_material_items():
    """Material items as they'd appear after extraction + save."""
    return [
        {
            "id": "item-1",
            "job_id": "job-123",
            "description": "Pas. Granit Dinding Premium 60x60",
            "item_type": "material",
            "unit": "m2",
            "quantity": 10.0,
            "contractor_unit_price": 250000,
            "contractor_total": 2500000,
            "is_owner_supply": True,
        },
        {
            "id": "item-2",
            "job_id": "job-123",
            "description": "Pipa PVC Rucika 4 inch",
            "item_type": "material",
            "unit": "btg",
            "quantity": 5.0,
            "contractor_unit_price": 85000,
            "contractor_total": 425000,
            "is_owner_supply": False,
        },
        {
            "id": "item-3",
            "job_id": "job-123",
            "description": "Upah tukang batu",
            "item_type": "labor",
            "unit": "org/hr",
            "quantity": 2.0,
            "contractor_unit_price": 150000,
            "contractor_total": 300000,
            "is_owner_supply": False,
        },
    ]


@pytest.fixture
def mock_apify_products():
    """Tokopedia products as returned by the Apify actor."""
    return {
        "granit dinding premium 60x60": [
            {
                "name": "Granit Dinding Premium Roman 60x60",
                "price_idr": 195000,
                "url": "https://tokopedia.com/toko-keramik/granit-dinding",
                "shop": "Toko Keramik Jaya",
                "location": "Jakarta Selatan",
                "rating": 4.7,
                "sold_count": 320,
            },
        ],
        "pipa pvc rucika 4 inch": [
            {
                "name": "Pipa PVC Rucika 4 inch AW",
                "price_idr": 72000,
                "url": "https://tokopedia.com/toko-pipa/pipa-pvc",
                "shop": "Toko Pipa Utama",
                "location": "Surabaya",
                "rating": 4.5,
                "sold_count": 150,
            },
        ],
    }


# =============================================================================
# Test: batch_price_materials wiring
# =============================================================================


class TestBatchPricingWiring:
    """Test that batch_price_materials integrates correctly with TokopediaProvider."""

    def test_full_pipeline_produces_matches_for_materials(
        self, sample_material_items, mock_apify_products
    ):
        """Should produce MaterialPriceMatch for each material item."""
        from app.services.boq_pricer import batch_price_materials
        from app.integrations.marketplace import TokopediaProvider

        # Mock the provider
        provider = MagicMock(spec=TokopediaProvider)
        provider.batch_search_sync.return_value = mock_apify_products

        # Mock rank_results to return BestSellerScore-like objects
        def mock_rank(results):
            scored = []
            for r in results:
                score = MagicMock()
                score.product = r
                score.total_score = 0.8
                scored.append(score)
            return scored

        provider.rank_results.side_effect = mock_rank

        # Only pass material items (filter out labor)
        materials_only = [i for i in sample_material_items if i["item_type"] == "material"]

        matches = batch_price_materials(
            items=materials_only,
            provider=provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        assert len(matches) == 2
        # Owner supply item should be first (sorted by priority)
        first_item, first_match = matches[0]
        assert first_item["id"] == "item-1"
        assert first_match.search_query == "granit dinding premium 60x60"
        assert first_match.result is not None
        assert first_match.result.product_name == "Granit Dinding Premium Roman 60x60"
        assert first_match.market_unit_price == Decimal("195000")

    def test_pipeline_calculates_price_difference(
        self, sample_material_items, mock_apify_products
    ):
        """Should compute correct delta between contractor and market price.

        item-1 is owner-supply: price_difference/pct must be None (comparing
        material market price to a labor rate is meaningless).
        item-2 is contractor-supplied: normal price_difference applies.
        """
        from app.services.boq_pricer import batch_price_materials

        provider = MagicMock()
        provider.batch_search_sync.return_value = mock_apify_products

        def mock_rank(results):
            scored = []
            for r in results:
                score = MagicMock()
                score.product = r
                score.total_score = 0.8
                scored.append(score)
            return scored

        provider.rank_results.side_effect = mock_rank

        materials_only = [i for i in sample_material_items if i["item_type"] == "material"]

        matches = batch_price_materials(
            items=materials_only,
            provider=provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        # Item 1 (is_owner_supply=True): market price IS set (shopping list),
        # but price_difference/pct must be None (labor rate vs material price).
        granit_match = next(m for _, m in matches if "granit" in m.search_query)
        assert granit_match.market_unit_price == Decimal("195000"), "Shopping-list price must be set"
        assert granit_match.price_difference is None, "price_difference must be None for owner-supply"
        assert granit_match.price_difference_pct is None, "price_difference_pct must be None for owner-supply"

        # Item 2 (is_owner_supply=False): contractor=85000, market=72000 → diff=13000 (15.29%)
        pipa_match = next(m for _, m in matches if "pipa" in m.search_query)
        assert pipa_match.price_difference == Decimal("13000")
        assert pipa_match.price_difference_pct == pytest.approx(15.29, abs=0.01)


class TestPersistPriceResultsWiring:
    """Test that persist_price_results writes correct data to Supabase."""

    def test_writes_pricing_fields_to_boq_items(self, mock_apify_products):
        """Should update boq_items rows with tokopedia pricing data."""
        from app.services.boq_pricer import batch_price_materials, persist_price_results

        items = [
            {
                "id": "item-1",
                "description": "Granit Dinding Premium 60x60",
                "item_type": "material",
                "quantity": 10.0,
                "contractor_unit_price": 250000,
                "is_owner_supply": True,
            },
        ]

        provider = MagicMock()
        provider.batch_search_sync.return_value = mock_apify_products

        def mock_rank(results):
            scored = []
            for r in results:
                score = MagicMock()
                score.product = r
                score.total_score = 0.8
                scored.append(score)
            return scored

        provider.rank_results.side_effect = mock_rank

        matches = batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            max_lookups=20,
        )

        # Mock supabase for persistence
        mock_sb = MagicMock()
        mock_table = MagicMock()
        mock_update_chain = MagicMock()
        mock_eq_chain = MagicMock()
        mock_sb.table.return_value = mock_table
        mock_table.update.return_value = mock_update_chain
        mock_update_chain.eq.return_value = mock_eq_chain

        persist_price_results(mock_sb, "job-123", matches)

        # Verify update was called
        mock_sb.table.assert_called_with("boq_items")
        mock_table.update.assert_called_once()
        update_data = mock_table.update.call_args[0][0]

        assert update_data["tokopedia_product_name"] == "Granit Dinding Premium Roman 60x60"
        assert update_data["tokopedia_price"] == 195000
        assert update_data["market_unit_price"] == 195000.0
        assert update_data["match_confidence"] > 0
        # Owner-supply item: price_difference fields must be None (labor vs material)
        assert update_data["price_difference"] is None
        assert update_data["price_difference_percent"] is None


class TestCalculateSummarySync:
    """Test that _calculate_summary_sync aggregates market pricing correctly."""

    def _make_mock_sb(self, items_data):
        """Helper: build a minimal Supabase mock returning the given items."""
        mock_sb = MagicMock()
        mock_result = MagicMock()
        mock_result.data = items_data
        mock_eq = MagicMock()
        mock_eq.execute.return_value = mock_result
        mock_select = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_sb.table.return_value.select.return_value = mock_select
        mock_update_chain = MagicMock()
        mock_update_eq = MagicMock()
        mock_sb.table.return_value.update.return_value = mock_update_chain
        mock_update_chain.eq.return_value = mock_update_eq
        return mock_sb

    def test_computes_savings_over_comparison_subset_only(self):
        """savings math must use only contractor-supplied priced items (not owner-supply).

        Items:
          - item-1 (material, priced, owner-supply): contractor 1,000,000 (labor rate) /
                                                     market 1,500,000 (material price)
          - item-2 (material, priced, contractor-supplied): contractor 2,500,000 /
                                                            market 1,950,000
          - item-3 (labor, unpriced): contractor 300,000

        Expected:
          contractor_total        = 3,800,000  (all items — unchanged "Contractor Quote" tile)
          compared_count          = 1           (only item-2; item-1 is owner-supply)
          priced_contractor_total = 2,500,000   (only item-2)
          market_estimate         = 1,950,000   (only item-2)
          potential_savings       =   550,000   (2,500,000 − 1,950,000)
          savings_percent         = 22.0        (550,000 / 2,500,000 × 100)
          priced_count            = 2           (item-1 + item-2 both have tokopedia_price)
          shopping_list_total     = 1,500,000   (market price of owner-supply item-1)
        """
        from app.services.boq_processor import _calculate_summary_sync

        items_data = [
            {
                "item_type": "material",
                "is_owner_supply": False,
                "contractor_total": 2500000,
                "market_total": 1950000,
                "tokopedia_price": 195000,
            },
            {
                "item_type": "material",
                "is_owner_supply": True,
                "contractor_total": 1000000,
                "market_total": 1500000,
                "tokopedia_price": 150000,
            },
            {
                "item_type": "labor",
                "is_owner_supply": False,
                "contractor_total": 300000,
                "market_total": None,
                "tokopedia_price": None,
            },
        ]

        mock_sb = self._make_mock_sb(items_data)
        _calculate_summary_sync(mock_sb, "job-123")

        mock_sb.table.return_value.update.assert_called_once()
        summary = mock_sb.table.return_value.update.call_args[0][0]

        # Counts
        assert summary["materials_count"] == 2
        assert summary["labor_count"] == 1
        assert summary["owner_supply_count"] == 1
        # priced_count covers ALL items with a tokopedia_price (item-1 + item-2)
        assert summary["priced_count"] == 2
        # compared_count excludes owner-supply (only item-2)
        assert summary["compared_count"] == 1

        # Whole-document contractor total (all items unchanged)
        assert Decimal(summary["contractor_total"]) == Decimal("3800000")

        # Comparison-subset contractor total (item-2 only)
        assert Decimal(summary["priced_contractor_total"]) == Decimal("2500000")

        # Market estimate = item-2 market total only
        assert Decimal(summary["market_estimate"]) == Decimal("1950000")

        # Savings = priced_contractor_total − market_estimate (comparison subset)
        assert Decimal(summary["potential_savings"]) == Decimal("550000")

        # savings_percent = 550,000 / 2,500,000 × 100 = 22.0
        assert summary["savings_percent"] == pytest.approx(22.0, abs=0.01)

        # shopping_list_total = market total of owner-supply priced items
        assert Decimal(summary["shopping_list_total"]) == Decimal("1500000")

    def test_excludes_above_contractor_matches_from_savings(self):
        """Matches priced at/above the contractor rate are dropped from savings.

        For supply-and-install lines the contractor rate already includes the
        material, so a market price above it is almost always a bad match. Without
        this exclusion, inflated mismatches cancel genuine overpricing and the
        savings headline collapses to Rp 0 (the production bug this fixes).

        Items (both contractor-supplied, both priced):
          - item-1 GENUINE overpricing: contractor 15,871,100 / market 7,548,450
          - item-2 BAD high-side match:  contractor  3,375,000 / market 11,250,000

        Expected: only item-1 counts.
          compared_count          = 1
          priced_contractor_total = 15,871,100
          market_estimate         =  7,548,450
          potential_savings       =  8,322,650
          savings_percent         ≈ 52.44
        """
        from app.services.boq_processor import _calculate_summary_sync

        items_data = [
            {
                "item_type": "material",
                "is_owner_supply": False,
                "contractor_total": 15871100,
                "market_total": 7548450,
                "tokopedia_price": 195000,
            },
            {
                "item_type": "material",
                "is_owner_supply": False,
                "contractor_total": 3375000,
                "market_total": 11250000,  # market > contractor → bad match, excluded
                "tokopedia_price": 1500000,
            },
        ]

        mock_sb = self._make_mock_sb(items_data)
        _calculate_summary_sync(mock_sb, "job-123")

        summary = mock_sb.table.return_value.update.call_args[0][0]

        # Both items are priced, but only the genuine-savings one is compared.
        assert summary["priced_count"] == 2
        assert summary["compared_count"] == 1
        assert Decimal(summary["priced_contractor_total"]) == Decimal("15871100")
        assert Decimal(summary["market_estimate"]) == Decimal("7548450")
        assert Decimal(summary["potential_savings"]) == Decimal("8322650")
        assert summary["savings_percent"] == pytest.approx(52.44, abs=0.01)
        # Whole-document contractor total still includes the dropped item.
        assert Decimal(summary["contractor_total"]) == Decimal("19246100")

    def test_handles_no_priced_items(self):
        """Should write NULLs for all pricing fields when no items are priced."""
        from app.services.boq_processor import _calculate_summary_sync

        items_data = [
            {
                "item_type": "material",
                "is_owner_supply": False,
                "contractor_total": 500000,
                "market_total": None,
                "tokopedia_price": None,
            },
        ]

        mock_sb = self._make_mock_sb(items_data)
        _calculate_summary_sync(mock_sb, "job-123")

        summary = mock_sb.table.return_value.update.call_args[0][0]
        assert summary["market_estimate"] is None
        assert summary["potential_savings"] is None
        assert summary["savings_percent"] is None
        assert summary["priced_contractor_total"] is None
        assert summary["priced_count"] == 0
        assert summary["compared_count"] == 0
        assert summary["shopping_list_total"] is None

    def test_shopping_list_total_none_when_no_owner_supply_priced(self):
        """shopping_list_total must be None when there are no priced owner-supply items."""
        from app.services.boq_processor import _calculate_summary_sync

        items_data = [
            {
                "item_type": "material",
                "is_owner_supply": False,
                "contractor_total": 2500000,
                "market_total": 1950000,
                "tokopedia_price": 195000,
            },
        ]

        mock_sb = self._make_mock_sb(items_data)
        _calculate_summary_sync(mock_sb, "job-123")

        summary = mock_sb.table.return_value.update.call_args[0][0]
        assert summary["shopping_list_total"] is None

    def test_compared_count_zero_when_all_priced_are_owner_supply(self):
        """When every priced item is owner-supply, comparison fields must be NULL."""
        from app.services.boq_processor import _calculate_summary_sync

        items_data = [
            {
                "item_type": "material",
                "is_owner_supply": True,
                "contractor_total": 1000000,
                "market_total": 1500000,
                "tokopedia_price": 150000,
            },
        ]

        mock_sb = self._make_mock_sb(items_data)
        _calculate_summary_sync(mock_sb, "job-123")

        summary = mock_sb.table.return_value.update.call_args[0][0]
        assert summary["compared_count"] == 0
        assert summary["market_estimate"] is None
        assert summary["priced_contractor_total"] is None
        assert summary["potential_savings"] is None
        assert summary["savings_percent"] is None
        assert Decimal(summary["shopping_list_total"]) == Decimal("1500000")


class TestNormalizeMaterialNameIntegration:
    """Verify normalization works correctly in the pricing pipeline context."""

    def test_strips_indonesian_prefixes_for_search(self):
        """Should strip Pas., Pek., Instalasi prefixes for cleaner marketplace search."""
        from app.services.boq_pricer import normalize_material_name

        assert normalize_material_name("Pas. Granit Dinding 60x60") == "granit dinding 60x60"
        assert normalize_material_name("Pek. Cat Tembok Dulux") == "cat tembok dulux"
        assert normalize_material_name("Instalasi pipa air") == "pipa air"

    def test_strips_owner_supply_notes(self):
        """Should remove owner supply annotations."""
        from app.services.boq_pricer import normalize_material_name

        result = normalize_material_name("Granit Lantai (Supply By Owner)")
        assert "supply" not in result.lower()
        assert "owner" not in result.lower()

    def test_short_queries_filtered_in_pipeline(self):
        """Items normalizing to < 3 chars should be excluded from pricing."""
        from app.services.boq_pricer import batch_price_materials

        items = [
            {"description": "AB", "item_type": "material"},  # Too short
            {"description": "Pipa PVC 4 inch", "item_type": "material"},
        ]

        provider = MagicMock()
        provider.batch_search_sync.return_value = {"pipa pvc 4 inch": []}
        provider.rank_results.return_value = []

        matches = batch_price_materials(items=items, provider=provider, supabase_client=MagicMock())

        # Only 1 item should be processed (the PVC pipe)
        assert len(matches) == 1


class TestProgressCallback:
    """Test that progress is reported correctly during pricing."""

    def test_reports_progress_in_40_to_85_range(self):
        """Progress callback should receive values between 40 and 85."""
        from app.services.boq_pricer import batch_price_materials

        items = [
            {"description": "Granit Dinding Premium", "item_type": "material", "quantity": 1, "contractor_unit_price": 100000},
            {"description": "Pipa PVC Rucika", "item_type": "material", "quantity": 1, "contractor_unit_price": 50000},
        ]

        provider = MagicMock()
        provider.batch_search_sync.return_value = {
            "granit dinding premium": [],
            "pipa pvc rucika": [],
        }

        progress_values = []

        def track_progress(pct):
            progress_values.append(pct)

        batch_price_materials(
            items=items,
            provider=provider,
            supabase_client=MagicMock(),
            progress_callback=track_progress,
        )

        assert len(progress_values) == 2
        assert all(40 <= v <= 85 for v in progress_values)
        # Should be increasing
        assert progress_values[1] > progress_values[0]


class TestExtractionWarningsPersisted:
    def test_warnings_written_to_job_row(self, mock_supabase):
        """The post-extraction job-metadata update includes extraction_warnings."""
        from app.services.boq_processor import _save_job_metadata_sync
        from app.schemas.boq import ExtractedBoQData

        mock_supabase.table("boq_jobs").insert({"id": "job-1"}).execute()

        extracted = ExtractedBoQData(
            project_name="P",
            contractor_name="C",
            items=[],
            extraction_warnings=["Batch 1 hit the output limit; recovered page-by-page"],
        )
        _save_job_metadata_sync(mock_supabase, "job-1", extracted)

        row = mock_supabase._tables["boq_jobs"][0]
        assert row["extraction_warnings"] == [
            "Batch 1 hit the output limit; recovered page-by-page"
        ]
        assert row["project_name"] == "P"
        assert row["total_items_extracted"] == 0

    def test_results_schema_defaults_warnings_to_empty_list(self):
        """BoQAnalysisResults tolerates pre-migration rows with no warnings key."""
        from app.schemas.boq import (
            BoQAnalysisResults,
            BoQJobStatus,
            BoQMetadata,
            BoQSummary,
        )

        result = BoQAnalysisResults(
            job_id="job-1",
            status=BoQJobStatus.COMPLETED,
            metadata=BoQMetadata(filename="boq.pdf"),
            summary=BoQSummary(
                contractor_total=Decimal("0"),
                market_estimate=Decimal("0"),
                potential_savings=Decimal("0"),
                savings_percent=0.0,
                total_items=0,
                materials_count=0,
                labor_count=0,
                owner_supply_count=0,
                priced_count=0,
            ),
        )

        assert result.extraction_warnings == []
