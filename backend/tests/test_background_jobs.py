"""
Unit tests for background job service.

Tests cover:
- Job scheduler lifecycle (start/stop)
- Cache refresh for popular specializations
- Trust score recalculation for stale workers
- Scrape job cleanup
- Manual cache refresh trigger
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.background_jobs import BackgroundJobService, get_scheduler


class TestBackgroundJobService:
    """Test background job scheduler lifecycle"""

    def test_scheduler_initialization(self):
        """Should initialize scheduler with async support"""
        service = BackgroundJobService()

        assert service.scheduler is not None
        assert service.is_running is False

    @patch("app.services.background_jobs.settings")
    def test_start_when_disabled(self, mock_settings):
        """Should not start jobs when ENABLE_BACKGROUND_JOBS=false"""
        mock_settings.enable_background_jobs = False

        service = BackgroundJobService()
        service.start()

        assert service.is_running is False
        assert len(service.scheduler.get_jobs()) == 0

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.settings")
    async def test_start_when_enabled(self, mock_settings):
        """Should start scheduler and register jobs when enabled"""
        mock_settings.enable_background_jobs = True

        service = BackgroundJobService()
        service.start()

        assert service.is_running is True
        jobs = service.scheduler.get_jobs()
        assert len(jobs) == 3  # cache_refresh, trust_recalc, cleanup

        # Verify job IDs
        job_ids = [job.id for job in jobs]
        assert "cache_refresh_weekly" in job_ids
        assert "trust_recalc_daily" in job_ids
        assert "cleanup_monthly" in job_ids

        # Cleanup
        service.stop()

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.settings")
    async def test_stop_gracefully(self, mock_settings):
        """Should stop scheduler gracefully"""
        mock_settings.enable_background_jobs = True

        service = BackgroundJobService()
        service.start()
        assert service.is_running is True

        service.stop()
        assert service.is_running is False

    def test_get_scheduler_singleton(self):
        """Should return same scheduler instance"""
        scheduler1 = get_scheduler()
        scheduler2 = get_scheduler()

        assert scheduler1 is scheduler2


class TestCacheRefresh:
    """Test cache refresh job"""

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.BackgroundJobService._refresh_specialization_cache")
    async def test_refresh_popular_workers(self, mock_refresh):
        """Should refresh cache for all popular specializations"""
        mock_refresh.return_value = None

        service = BackgroundJobService()
        await service.refresh_popular_workers()

        # Should call refresh for all 4 popular specializations
        assert mock_refresh.call_count == 4

        # Verify specializations
        call_args_list = [call[0][0] for call in mock_refresh.call_args_list]
        assert "pool" in call_args_list
        assert "bathroom" in call_args_list
        assert "kitchen" in call_args_list
        assert "general" in call_args_list

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.BackgroundJobService._refresh_specialization_cache")
    async def test_refresh_continues_on_error(self, mock_refresh):
        """Should continue refreshing other specializations if one fails"""
        # First call fails, rest succeed
        mock_refresh.side_effect = [
            Exception("Scrape error"),
            None,
            None,
            None,
        ]

        service = BackgroundJobService()
        await service.refresh_popular_workers()

        # Should still call all 4 specializations
        assert mock_refresh.call_count == 4

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.scrape_google_maps_workers")
    @patch("app.services.background_jobs.deduplicate_workers")
    @patch("app.services.background_jobs.calculate_trust_score")
    @patch("app.services.background_jobs.bulk_insert_workers")
    @patch("app.services.background_jobs.update_worker_scraped_timestamp")
    async def test_refresh_specialization_cache_full_workflow(
        self,
        mock_update_timestamp,
        mock_bulk_insert,
        mock_calculate_trust,
        mock_dedupe,
        mock_scrape,
    ):
        """Should execute full cache refresh workflow"""
        # Mock scraping results
        mock_scrape.return_value = [
            {"gmaps_place_id": "ChIJ1", "business_name": "Worker 1"},
            {"gmaps_place_id": "ChIJ2", "business_name": "Worker 2"},
        ]

        # Mock deduplication
        mock_dedupe.return_value = mock_scrape.return_value

        # Mock trust calculation
        mock_calculate_trust.return_value = MagicMock(
            score=85,
            level=MagicMock(value="HIGH"),
            breakdown={"source": 24, "reviews": 20},
        )

        # Mock database save
        mock_bulk_insert.return_value = [
            {"id": "worker-1", "gmaps_place_id": "ChIJ1"},
            {"id": "worker-2", "gmaps_place_id": "ChIJ2"},
        ]

        service = BackgroundJobService()
        await service._refresh_specialization_cache("pool", "Bali")

        # Verify workflow steps
        mock_scrape.assert_called_once_with(
            project_type="pool",
            location="Bali",
            max_results_per_search=20,
            min_rating=4.0,
        )
        mock_dedupe.assert_called_once()
        assert mock_calculate_trust.call_count == 2
        mock_bulk_insert.assert_called_once()
        mock_update_timestamp.assert_called_once_with(["worker-1", "worker-2"])

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.scrape_google_maps_workers")
    async def test_refresh_specialization_handles_empty_results(self, mock_scrape):
        """Should handle empty scrape results gracefully"""
        mock_scrape.return_value = []

        service = BackgroundJobService()
        await service._refresh_specialization_cache("pool", "Bali")

        # Should not raise exception
        mock_scrape.assert_called_once()


class TestTrustScoreRecalculation:
    """Test trust score recalculation job"""

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.get_supabase_client")
    @patch("app.services.background_jobs.calculate_trust_score")
    async def test_recalculate_stale_trust_scores(
        self, mock_calculate_trust, mock_get_supabase
    ):
        """Should recalculate trust scores for stale workers"""
        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock stale workers query
        mock_select = MagicMock()
        mock_supabase.table.return_value.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value.data = [
            {
                "id": "worker-1",
                "business_name": "Worker 1",
                "gmaps_review_count": 50,
                "gmaps_rating": 4.8,
                "last_score_calculated_at": (
                    datetime.now(timezone.utc) - timedelta(days=60)
                ).isoformat(),
            },
            {
                "id": "worker-2",
                "business_name": "Worker 2",
                "gmaps_review_count": 20,
                "gmaps_rating": 4.2,
                "last_score_calculated_at": None,
            },
        ]

        # Mock trust calculation
        mock_calculate_trust.return_value = MagicMock(
            score=75,
            level=MagicMock(value="HIGH"),
            breakdown={"source": 24, "reviews": 15},
        )

        # Mock update query
        mock_update = MagicMock()
        mock_supabase.table.return_value.update.return_value = mock_update
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = None

        service = BackgroundJobService()
        await service.recalculate_stale_trust_scores()

        # Verify trust calculation called for both workers
        assert mock_calculate_trust.call_count == 2

        # Verify update called for both workers
        assert mock_update.eq.call_count == 2

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.get_supabase_client")
    async def test_recalculate_handles_no_stale_workers(self, mock_get_supabase):
        """Should handle case when no stale workers found"""
        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock empty results
        mock_select = MagicMock()
        mock_supabase.table.return_value.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value.data = []

        service = BackgroundJobService()
        await service.recalculate_stale_trust_scores()

        # Should not raise exception
        mock_supabase.table.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.get_supabase_client")
    @patch("app.services.background_jobs.calculate_trust_score")
    async def test_recalculate_continues_on_error(
        self, mock_calculate_trust, mock_get_supabase
    ):
        """Should continue recalculating even if one worker fails"""
        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock stale workers
        mock_select = MagicMock()
        mock_supabase.table.return_value.select.return_value = mock_select
        mock_select.eq.return_value = mock_select
        mock_select.or_.return_value = mock_select
        mock_select.limit.return_value = mock_select
        mock_select.execute.return_value.data = [
            {"id": "worker-1", "business_name": "Worker 1"},
            {"id": "worker-2", "business_name": "Worker 2"},
        ]

        # First calculation fails, second succeeds
        mock_calculate_trust.side_effect = [
            Exception("Calculation error"),
            MagicMock(score=75, level=MagicMock(value="HIGH"), breakdown={}),
        ]

        # Mock update
        mock_update = MagicMock()
        mock_supabase.table.return_value.update.return_value = mock_update
        mock_update.eq.return_value = mock_update
        mock_update.execute.return_value = None

        service = BackgroundJobService()
        await service.recalculate_stale_trust_scores()

        # Should call both calculations
        assert mock_calculate_trust.call_count == 2

        # Should only update successful one
        assert mock_update.eq.call_count == 1


class TestScrapeJobCleanup:
    """Test scrape job cleanup"""

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.get_supabase_client")
    async def test_cleanup_old_scrape_jobs(self, mock_get_supabase):
        """Should delete old completed/failed scrape jobs"""
        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock delete query
        mock_delete = MagicMock()
        mock_supabase.table.return_value.delete.return_value = mock_delete
        mock_delete.in_.return_value = mock_delete
        mock_delete.lt.return_value = mock_delete
        mock_delete.execute.return_value.data = [
            {"id": "job-1"},
            {"id": "job-2"},
            {"id": "job-3"},
        ]

        service = BackgroundJobService()
        await service.cleanup_old_scrape_jobs()

        # Verify delete called with correct filters
        mock_supabase.table.assert_called_with("scrape_jobs")
        mock_delete.in_.assert_called_once_with("status", ["completed", "failed"])
        mock_delete.lt.assert_called_once()  # Called with cutoff date

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.get_supabase_client")
    async def test_cleanup_handles_no_old_jobs(self, mock_get_supabase):
        """Should handle case when no old jobs to cleanup"""
        # Mock Supabase client
        mock_supabase = MagicMock()
        mock_get_supabase.return_value = mock_supabase

        # Mock empty delete result
        mock_delete = MagicMock()
        mock_supabase.table.return_value.delete.return_value = mock_delete
        mock_delete.in_.return_value = mock_delete
        mock_delete.lt.return_value = mock_delete
        mock_delete.execute.return_value.data = []

        service = BackgroundJobService()
        await service.cleanup_old_scrape_jobs()

        # Should not raise exception
        mock_supabase.table.assert_called()


class TestManualCacheRefresh:
    """Test manual cache refresh trigger"""

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.BackgroundJobService._refresh_specialization_cache")
    async def test_trigger_manual_cache_refresh(self, mock_refresh):
        """Should manually trigger cache refresh for specific specialization"""
        mock_refresh.return_value = None

        service = BackgroundJobService()
        await service.trigger_manual_cache_refresh("pool", "Canggu")

        # Verify refresh called with correct parameters
        mock_refresh.assert_called_once_with("pool", "Canggu")

    @pytest.mark.asyncio
    @patch("app.services.background_jobs.BackgroundJobService._refresh_specialization_cache")
    async def test_manual_refresh_defaults_to_bali(self, mock_refresh):
        """Should default to Bali location if not specified"""
        mock_refresh.return_value = None

        service = BackgroundJobService()
        await service.trigger_manual_cache_refresh("bathroom")

        # Verify refresh called with Bali as default
        mock_refresh.assert_called_once_with("bathroom", "Bali")
