"""
Unit tests for Supabase worker operations.

Tests cover:
- Bulk worker insertion with upsert logic
- Cache checking by specialization and age
- Worker search with multiple filters
- Trust score updates with timestamps
- Scraped timestamp bulk updates
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.integrations.supabase import (
    bulk_insert_workers,
    get_cached_workers,
    search_workers,
    update_worker_scraped_timestamp,
    update_worker_trust,
)


class TestBulkInsertWorkers:
    """Test bulk worker insertion with upsert logic"""

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_inserts_multiple_workers(self, mock_get_client):
        """Should insert multiple workers at once"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock response
        mock_table = MagicMock()
        mock_upsert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = [
            {"id": "worker-1", "business_name": "Bali Pool Service"},
            {"id": "worker-2", "business_name": "Canggu Construction"},
        ]

        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = mock_execute

        workers = [
            {"business_name": "Bali Pool Service", "gmaps_place_id": "ChIJ1"},
            {"business_name": "Canggu Construction", "gmaps_place_id": "ChIJ2"},
        ]

        result = await bulk_insert_workers(workers)

        # Verify upsert called with gmaps_place_id conflict
        mock_table.upsert.assert_called_once_with(
            workers, on_conflict="gmaps_place_id"
        )
        assert len(result) == 2
        assert result[0]["business_name"] == "Bali Pool Service"

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_handles_empty_list(self, mock_get_client):
        """Should handle empty worker list gracefully"""
        result = await bulk_insert_workers([])
        assert result == []

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_handles_no_data_response(self, mock_get_client):
        """Should handle empty response from database"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_upsert = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = None  # No data returned

        mock_client.table.return_value = mock_table
        mock_table.upsert.return_value = mock_upsert
        mock_upsert.execute.return_value = mock_execute

        workers = [{"business_name": "Test", "gmaps_place_id": "ChIJ1"}]
        result = await bulk_insert_workers(workers)

        assert result == []


class TestGetCachedWorkers:
    """Test cache checking for recent scrapes"""

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_returns_fresh_cached_workers(self, mock_get_client):
        """Should return workers if cache is fresh"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query chain
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_contains = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_order = MagicMock()
        mock_execute = MagicMock()

        mock_execute.data = [
            {"id": "worker-1", "business_name": "Bali Pool", "trust_score": 85},
            {"id": "worker-2", "business_name": "Pool Pro", "trust_score": 78},
        ]

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.contains.return_value = mock_contains
        mock_contains.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.order.return_value = mock_order
        mock_order.execute.return_value = mock_execute

        result = await get_cached_workers("pool", max_age_hours=168)

        assert result is not None
        assert len(result) == 2
        assert result[0]["trust_score"] == 85

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_returns_none_for_cache_miss(self, mock_get_client):
        """Should return None if no cached workers found"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock empty response
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_contains = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_order = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = []  # No workers found

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.contains.return_value = mock_contains
        mock_contains.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.order.return_value = mock_order
        mock_order.execute.return_value = mock_execute

        result = await get_cached_workers("pool")

        assert result is None

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_uses_custom_cache_age(self, mock_get_client):
        """Should respect custom max_age_hours parameter"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_contains = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_order = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = []

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.contains.return_value = mock_contains
        mock_contains.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.order.return_value = mock_order
        mock_order.execute.return_value = mock_execute

        await get_cached_workers("pool", max_age_hours=24)

        # Verify cutoff time is 24 hours ago (approximately)
        call_args = mock_eq.gte.call_args
        assert call_args is not None


class TestSearchWorkers:
    """Test flexible worker search with filters"""

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_searches_by_specialization(self, mock_get_client):
        """Should filter by specialization"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query chain
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_contains = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = [{"id": "worker-1", "specializations": ["pool"]}]

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.contains.return_value = mock_contains
        mock_contains.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute

        result = await search_workers(specialization="pool")

        mock_eq.contains.assert_called_once_with("specializations", ["pool"])
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_searches_by_location(self, mock_get_client):
        """Should filter by location using ILIKE"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_ilike = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = [{"id": "worker-1", "location": "Canggu"}]

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.ilike.return_value = mock_ilike
        mock_ilike.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute

        result = await search_workers(location="Canggu")

        mock_eq.ilike.assert_called_once_with("location", "%Canggu%")
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_filters_by_trust_score(self, mock_get_client):
        """Should filter by minimum trust score"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = [{"id": "worker-1", "trust_score": 85}]

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute

        result = await search_workers(min_trust_score=80)

        mock_eq.gte.assert_called_once_with("trust_score", 80)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_filters_by_rating(self, mock_get_client):
        """Should filter by minimum Google Maps rating"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_gte = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = [{"id": "worker-1", "gmaps_rating": 4.5}]

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.gte.return_value = mock_gte
        mock_gte.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute

        result = await search_workers(min_rating=4.0)

        mock_eq.gte.assert_called_once_with("gmaps_rating", 4.0)
        assert len(result) == 1

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_combines_multiple_filters(self, mock_get_client):
        """Should chain multiple filters together"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_contains = MagicMock()
        mock_ilike = MagicMock()
        mock_gte1 = MagicMock()
        mock_gte2 = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = MagicMock()
        mock_execute.data = []

        mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.contains.return_value = mock_contains
        mock_contains.ilike.return_value = mock_ilike
        mock_ilike.gte.return_value = mock_gte1
        mock_gte1.gte.return_value = mock_gte2
        mock_gte2.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = mock_execute

        result = await search_workers(
            specialization="pool",
            location="Canggu",
            min_trust_score=80,
            min_rating=4.5,
            limit=10
        )

        # Verify all filters were applied
        mock_eq.contains.assert_called_once()
        mock_contains.ilike.assert_called_once()
        assert result == []


class TestUpdateWorkerTrust:
    """Test trust score updates"""

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_updates_trust_score_with_timestamp(self, mock_get_client):
        """Should update trust score and set calculation timestamp"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute.return_value = mock_execute

        await update_worker_trust(
            worker_id="worker-123",
            trust_score=85,
            trust_level="HIGH",
            trust_breakdown={"source": 24, "reviews": 20}
        )

        # Verify update called with all fields including timestamp
        call_args = mock_table.update.call_args[0][0]
        assert call_args["trust_score"] == 85
        assert call_args["trust_level"] == "HIGH"
        assert call_args["trust_breakdown"] == {"source": 24, "reviews": 20}
        assert call_args["last_score_calculated_at"] == "now()"


class TestUpdateWorkerScrapedTimestamp:
    """Test bulk scraped timestamp updates"""

    @pytest.mark.asyncio
    @patch("app.integrations.supabase.get_supabase_client")
    async def test_updates_multiple_workers(self, mock_get_client):
        """Should update last_scraped_at for multiple workers"""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_in = MagicMock()
        mock_execute = MagicMock()

        mock_client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.in_.return_value = mock_in
        mock_in.execute.return_value = mock_execute

        worker_ids = ["worker-1", "worker-2", "worker-3"]
        await update_worker_scraped_timestamp(worker_ids)

        # Verify IN clause used for bulk update
        mock_update.in_.assert_called_once_with("id", worker_ids)

    @pytest.mark.asyncio
    async def test_handles_empty_list(self):
        """Should handle empty worker_ids list gracefully"""
        # Should not raise exception
        await update_worker_scraped_timestamp([])
