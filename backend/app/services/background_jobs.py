"""
Background job service for scheduled tasks.

Jobs:
- Worker cache refresh: Scrape popular specializations weekly
- Trust score recalculation: Update scores for stale workers daily
- Data cleanup: Remove old scrape job records monthly

Uses APScheduler for lightweight in-process scheduling.
For production scale, migrate to Celery + Redis.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.integrations.google_maps_scraper import scrape_google_maps_workers
from app.integrations.supabase import (
    bulk_insert_workers,
    get_supabase_client,
    update_worker_scraped_timestamp,
)
from app.services.trust_calculator import calculate_trust_score
from app.services.worker_deduplication import deduplicate_workers

settings = get_settings()


class BackgroundJobService:
    """
    Background job scheduler for worker data maintenance.

    Jobs:
    1. Cache refresh: Weekly scraping of popular specializations
    2. Trust recalculation: Daily trust score updates for stale workers
    3. Cleanup: Monthly removal of old scrape job records
    """

    def __init__(self):
        """Initialize scheduler with async support"""
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self.is_running = False

    def start(self):
        """
        Start the background job scheduler.

        Jobs are configured but won't run in test/development
        unless explicitly enabled via ENABLE_BACKGROUND_JOBS=true
        """
        if not settings.enable_background_jobs:
            print("Background jobs disabled (ENABLE_BACKGROUND_JOBS=false)")
            return

        # Job 1: Cache refresh - Weekly on Sunday at 2 AM UTC
        self.scheduler.add_job(
            self.refresh_popular_workers,
            trigger=CronTrigger(day_of_week="sun", hour=2, minute=0),
            id="cache_refresh_weekly",
            name="Refresh popular worker caches",
            replace_existing=True,
        )

        # Job 2: Trust score recalculation - Daily at 3 AM UTC
        self.scheduler.add_job(
            self.recalculate_stale_trust_scores,
            trigger=CronTrigger(hour=3, minute=0),
            id="trust_recalc_daily",
            name="Recalculate stale trust scores",
            replace_existing=True,
        )

        # Job 3: Cleanup old scrape jobs - Monthly on 1st at 4 AM UTC
        self.scheduler.add_job(
            self.cleanup_old_scrape_jobs,
            trigger=CronTrigger(day=1, hour=4, minute=0),
            id="cleanup_monthly",
            name="Clean up old scrape job records",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        print("Background job scheduler started")

    def stop(self):
        """Stop the scheduler gracefully"""
        if self.is_running:
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            print("Background job scheduler stopped")

    async def refresh_popular_workers(self):
        """
        Refresh worker cache for popular specializations.

        Scrapes Google Maps for:
        - pool (highest demand)
        - bathroom (high demand)
        - kitchen (high demand)
        - general (fallback category)

        Cost estimate: ~$0.32-$1.60 per week (4 specializations × $0.08-$0.40)
        """
        popular_specializations = ["pool", "bathroom", "kitchen", "general"]
        location = "Bali"  # Default location

        print(f"[CACHE REFRESH] Starting refresh for {len(popular_specializations)} specializations")

        for specialization in popular_specializations:
            try:
                await self._refresh_specialization_cache(specialization, location)
            except Exception as e:
                print(f"[CACHE REFRESH] Error refreshing {specialization}: {str(e)}")
                continue

        print("[CACHE REFRESH] Completed cache refresh")

    async def _refresh_specialization_cache(
        self,
        specialization: str,
        location: str,
        max_results: int = 20,
        min_rating: float = 4.0
    ):
        """
        Refresh cache for a single specialization.

        Args:
            specialization: Worker specialization (pool, bathroom, etc.)
            location: Location for scraping (default: Bali)
            max_results: Maximum workers to scrape per search
            min_rating: Minimum Google Maps rating filter
        """
        print(f"[CACHE REFRESH] Scraping {specialization} in {location}")

        # Step 1: Scrape from Google Maps
        raw_workers = await scrape_google_maps_workers(
            project_type=specialization,
            location=location,
            max_results_per_search=max_results,
            min_rating=min_rating
        )

        if not raw_workers:
            print(f"[CACHE REFRESH] No workers found for {specialization}")
            return

        print(f"[CACHE REFRESH] Found {len(raw_workers)} workers for {specialization}")

        # Step 2: Deduplicate
        deduplicated_workers = deduplicate_workers(raw_workers)
        print(f"[CACHE REFRESH] Deduplicated to {len(deduplicated_workers)} workers")

        # Step 3: Calculate trust scores
        workers_with_trust = []
        for worker in deduplicated_workers:
            trust_result = calculate_trust_score(worker)
            worker.update({
                "trust_score": trust_result.score,
                "trust_level": trust_result.level.value,
                "trust_breakdown": trust_result.breakdown,
                "last_score_calculated_at": datetime.now(timezone.utc).isoformat(),
            })
            workers_with_trust.append(worker)

        # Step 4: Bulk insert (upsert by gmaps_place_id)
        saved_workers = await bulk_insert_workers(workers_with_trust)
        print(f"[CACHE REFRESH] Saved {len(saved_workers)} workers")

        # Step 5: Update scraped timestamps
        worker_ids = [w["id"] for w in saved_workers if "id" in w]
        if worker_ids:
            await update_worker_scraped_timestamp(worker_ids)

        print(f"[CACHE REFRESH] Completed {specialization}")

    async def recalculate_stale_trust_scores(self):
        """
        Recalculate trust scores for workers with stale scores.

        Targets workers where:
        - last_score_calculated_at > 30 days ago
        - OR last_score_calculated_at is NULL

        Trust scores should be recalculated periodically because:
        - Review counts change over time
        - New verification signals appear (photos, website)
        - Freshness component decays
        """
        print("[TRUST RECALC] Starting trust score recalculation")

        # Calculate cutoff date (30 days ago)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)

        supabase = get_supabase_client()

        # Fetch workers with stale trust scores
        response = (
            supabase.table("workers")
            .select("*")
            .eq("is_active", True)
            .or_(
                f"last_score_calculated_at.is.null,"
                f"last_score_calculated_at.lt.{cutoff_date.isoformat()}"
            )
            .limit(1000)  # Process max 1000 workers per run
            .execute()
        )

        workers = response.data if response.data else []

        if not workers:
            print("[TRUST RECALC] No stale workers found")
            return

        print(f"[TRUST RECALC] Recalculating scores for {len(workers)} workers")

        # Recalculate trust scores
        for worker in workers:
            try:
                trust_result = calculate_trust_score(worker)

                # Update worker trust score
                supabase.table("workers").update({
                    "trust_score": trust_result.score,
                    "trust_level": trust_result.level.value,
                    "trust_breakdown": trust_result.breakdown,
                    "last_score_calculated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", worker["id"]).execute()

            except Exception as e:
                print(f"[TRUST RECALC] Error recalculating worker {worker['id']}: {str(e)}")
                continue

        print(f"[TRUST RECALC] Completed recalculation for {len(workers)} workers")

    async def cleanup_old_scrape_jobs(self):
        """
        Clean up old scrape job records to prevent database bloat.

        Removes scrape jobs where:
        - Status = 'completed' or 'failed'
        - Created > 90 days ago

        Keeps recent jobs and pending/running jobs indefinitely.
        """
        print("[CLEANUP] Starting old scrape job cleanup")

        # Calculate cutoff date (90 days ago)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)

        supabase = get_supabase_client()

        # Delete old completed/failed scrape jobs
        response = (
            supabase.table("scrape_jobs")
            .delete()
            .in_("status", ["completed", "failed"])
            .lt("created_at", cutoff_date.isoformat())
            .execute()
        )

        deleted_count = len(response.data) if response.data else 0
        print(f"[CLEANUP] Deleted {deleted_count} old scrape job records")

    async def trigger_manual_cache_refresh(
        self,
        specialization: str,
        location: str = "Bali"
    ):
        """
        Manually trigger cache refresh for a specific specialization.

        Useful for:
        - Testing cache refresh logic
        - Admin-initiated cache warming
        - On-demand refreshes for new specializations

        Args:
            specialization: Worker specialization to refresh
            location: Location for scraping (default: Bali)
        """
        print(f"[MANUAL REFRESH] Triggered for {specialization} in {location}")
        await self._refresh_specialization_cache(specialization, location)


# Global scheduler instance
_scheduler_instance: BackgroundJobService | None = None


def get_scheduler() -> BackgroundJobService:
    """
    Get singleton scheduler instance.

    Returns:
        BackgroundJobService: Global scheduler instance
    """
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = BackgroundJobService()
    return _scheduler_instance


def start_background_jobs():
    """Start background job scheduler on application startup"""
    scheduler = get_scheduler()
    scheduler.start()


def stop_background_jobs():
    """Stop background job scheduler on application shutdown"""
    scheduler = get_scheduler()
    scheduler.stop()
