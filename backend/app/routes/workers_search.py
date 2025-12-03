"""
Worker search endpoint with intelligent cache-or-scrape strategy.

Flow:
1. Check cache for recent workers (7-day TTL)
2. If cache hit: deduplicate → rank → return
3. If cache miss: trigger background scrape → return empty with 202 status
4. Background scrape: scrape → deduplicate → save → calculate trust scores
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from pydantic import BaseModel

from app.integrations.google_maps_scraper import scrape_google_maps_workers
from app.integrations.supabase import (
    bulk_insert_workers,
    check_worker_unlock,
    get_cached_workers,
    get_worker_by_id,
    update_worker_scraped_timestamp,
)
from app.middleware.rate_limit import STANDARD_LIMIT, limiter
from app.schemas.worker import WorkerFullDetails, WorkerPreview
from app.services.trust_calculator import calculate_trust_score, mask_worker_name
from app.services.worker_deduplication import deduplicate_workers
from app.services.worker_matcher import rank_workers

router = APIRouter(prefix="/workers", tags=["workers"])


class WorkerSearchResponse(BaseModel):
    """Response for worker search with status"""

    status: str  # 'cache_hit' or 'scraping'
    workers: list[WorkerPreview]
    total_count: int
    cache_age_hours: int | None = None
    estimated_scrape_time_seconds: int | None = None


class WorkerSearchRequest(BaseModel):
    """Worker search filters"""

    project_type: str
    location: str = "Bali"
    budget_range: str | None = None  # 'low', 'medium', 'high'
    min_trust_score: int = 40
    max_results: int = 10


async def background_scrape_and_save(
    project_type: str,
    location: str,
) -> None:
    """
    Background task to scrape, deduplicate, and save workers.

    Args:
        project_type: Project type for scraping (pool, bathroom, etc.)
        location: Location for scraping (default: Bali)
    """
    try:
        # Step 1: Scrape from Google Maps
        raw_workers = await scrape_google_maps_workers(
            project_type=project_type,
            location=location,
            max_results_per_search=20,
            min_rating=4.0
        )

        if not raw_workers:
            return

        # Step 2: Deduplicate workers
        deduplicated_workers = deduplicate_workers(raw_workers)

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

        # Step 4: Bulk insert to database (upsert by gmaps_place_id)
        saved_workers = await bulk_insert_workers(workers_with_trust)

        # Step 5: Update scraped timestamps
        worker_ids = [w["id"] for w in saved_workers if "id" in w]
        if worker_ids:
            await update_worker_scraped_timestamp(worker_ids)

    except Exception as e:
        # Log error but don't fail (background task)
        print(f"Background scrape error for {project_type}: {str(e)}")


def transform_to_preview(worker: dict[str, Any]) -> WorkerPreview:
    """
    Transform database worker to preview response with masking.

    Args:
        worker: Worker dictionary from database

    Returns:
        WorkerPreview: Masked worker preview
    """
    from app.schemas.worker import TrustLevel, TrustScoreDetailed

    # Mask contact information
    masked_name = mask_worker_name(
        worker.get("business_name") or worker.get("name", "Unknown")
    )

    # Build trust score object matching TrustScoreDetailed schema
    trust_level_str = worker.get("trust_level", "LOW")
    trust_level = TrustLevel[trust_level_str] if trust_level_str in TrustLevel.__members__ else TrustLevel.LOW

    trust_score = TrustScoreDetailed(
        total_score=worker.get("trust_score", 0),
        trust_level=trust_level,
        breakdown=worker.get("trust_breakdown", {}),
        source_tier=worker.get("source_tier", "google_maps"),
        review_count=worker.get("gmaps_review_count", 0),
        rating=worker.get("gmaps_rating"),
    )

    return WorkerPreview(
        id=worker["id"],
        preview_name=masked_name,
        trust_score=trust_score,
        location=worker.get("location", "Bali"),
        specializations=worker.get("specializations", []),
        preview_review=worker.get("preview_review"),
        photos_count=worker.get("gmaps_photos_count", 0),
        opening_hours=worker.get("opening_hours"),
        price_idr_per_day=worker.get("olx_price_idr"),
        contact_locked=True,
        unlock_price_idr=50000,
    )


@router.post("/search", status_code=status.HTTP_200_OK)
@limiter.limit(STANDARD_LIMIT)
async def search_workers(
    request: Request,
    search_request: WorkerSearchRequest,
    background_tasks: BackgroundTasks,
) -> WorkerSearchResponse:
    """
    Search for workers with intelligent cache-or-scrape strategy.

    **Cache Strategy**:
    - Checks for recent workers (7-day cache)
    - If cache hit: returns deduplicated + ranked workers immediately
    - If cache miss: triggers background scrape, returns 202 with empty results

    **Background Scraping**:
    - Scrapes Google Maps in background (cost: ~$0.08-$0.40)
    - Deduplicates workers by phone/place_id/name
    - Calculates trust scores
    - Saves to database for future requests

    **Rate Limiting**: 10 requests per minute to prevent API abuse

    Args:
        search_request: Search filters (project_type, location, budget, etc.)
        background_tasks: FastAPI background tasks for async scraping

    Returns:
        WorkerSearchResponse: Status + workers list + metadata

    Example:
        ```json
        POST /workers/search
        {
            "project_type": "pool_construction",
            "location": "Canggu",
            "budget_range": "medium",
            "min_trust_score": 60,
            "max_results": 10
        }
        ```

    Response (cache hit):
        ```json
        {
            "status": "cache_hit",
            "workers": [...],
            "total_count": 15,
            "cache_age_hours": 48
        }
        ```

    Response (cache miss):
        ```json
        {
            "status": "scraping",
            "workers": [],
            "total_count": 0,
            "estimated_scrape_time_seconds": 30
        }
        ```
    """
    # Step 1: Check cache for recent workers (7-day TTL)
    cached_workers = await get_cached_workers(
        specialization=search_request.project_type,
        max_age_hours=168  # 7 days
    )

    # CASE 1: Cache Hit - Return ranked workers immediately
    if cached_workers:
        # Deduplicate (in case of duplicates from multiple sources)
        deduplicated = deduplicate_workers(cached_workers)

        # Rank by project requirements
        ranked = rank_workers(
            workers=deduplicated,
            project_type=search_request.project_type,
            location=search_request.location,
            min_trust_score=search_request.min_trust_score,
            budget_range=search_request.budget_range,
            max_results=search_request.max_results
        )

        # Transform to preview format with masking
        previews = [transform_to_preview(w) for w in ranked]

        # Calculate cache age
        if ranked and ranked[0].get("last_scraped_at"):
            cache_age = datetime.now(timezone.utc) - datetime.fromisoformat(
                ranked[0]["last_scraped_at"]
            )
            cache_age_hours = int(cache_age.total_seconds() / 3600)
        else:
            cache_age_hours = None

        return WorkerSearchResponse(
            status="cache_hit",
            workers=previews,
            total_count=len(previews),
            cache_age_hours=cache_age_hours
        )

    # CASE 2: Cache Miss - Trigger background scrape
    background_tasks.add_task(
        background_scrape_and_save,
        project_type=search_request.project_type,
        location=search_request.location
    )

    return WorkerSearchResponse(
        status="scraping",
        workers=[],
        total_count=0,
        estimated_scrape_time_seconds=30
    )


@router.get("/{worker_id}/preview", status_code=status.HTTP_200_OK)
@limiter.limit(STANDARD_LIMIT)
async def get_worker_preview(
    request: Request,
    worker_id: str
) -> WorkerPreview:
    """
    Get masked preview for a specific worker.

    Contact information (phone, email) remains locked until payment.

    Args:
        worker_id: UUID of the worker

    Returns:
        WorkerPreview: Masked worker preview

    Raises:
        HTTPException: 404 if worker not found
    """
    worker = await get_worker_by_id(worker_id)

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker {worker_id} not found"
        )

    return transform_to_preview(worker)


@router.get("/{worker_id}/details", status_code=status.HTTP_200_OK)
@limiter.limit(STANDARD_LIMIT)
async def get_worker_details(
    request: Request,
    worker_id: str,
    user_email: str = Query(..., description="User email for unlock verification")
) -> WorkerFullDetails:
    """
    Get full worker details with contact information.

    **Unlock Required**: User must have unlocked this worker via payment.

    **Flow**:
    1. Check if worker exists
    2. Verify user has unlocked this worker
    3. Return full details with unmasked contact information
    4. Include negotiation tips based on trust score

    Args:
        worker_id: UUID of the worker
        user_email: User's email for unlock verification

    Returns:
        WorkerFullDetails: Complete worker information with contacts

    Raises:
        HTTPException:
            - 404 if worker not found
            - 402 Payment Required if worker not unlocked

    Example:
        ```
        GET /workers/{worker_id}/details?user_email=user@example.com
        ```
    """
    # Step 1: Check if worker exists
    worker = await get_worker_by_id(worker_id)

    if not worker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Worker {worker_id} not found"
        )

    # Step 2: Verify unlock status
    is_unlocked = await check_worker_unlock(worker_id, user_email)

    if not is_unlocked:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Worker contact details are locked. Payment required to unlock.",
                "worker_id": worker_id,
                "unlock_price_idr": 50000,
                "payment_url": f"/payments/unlock-worker/{worker_id}"
            }
        )

    # Step 3: Transform to full details with contacts
    return transform_to_full_details(worker)


def transform_to_full_details(worker: dict[str, Any]) -> WorkerFullDetails:
    """
    Transform database worker to full details response.

    Args:
        worker: Worker dictionary from database

    Returns:
        WorkerFullDetails: Complete worker details with contacts
    """
    from app.schemas.worker import (
        TrustLevel,
        TrustScoreDetailed,
        WorkerContact,
        WorkerLocation,
        WorkerReview,
    )

    # Build trust score object
    trust_level_str = worker.get("trust_level", "LOW")
    trust_level = (
        TrustLevel[trust_level_str]
        if trust_level_str in TrustLevel.__members__
        else TrustLevel.LOW
    )

    trust_score = TrustScoreDetailed(
        total_score=worker.get("trust_score", 0),
        trust_level=trust_level,
        breakdown=worker.get("trust_breakdown", {}),
        source_tier=worker.get("source_tier", "google_maps"),
        review_count=worker.get("gmaps_review_count", 0),
        rating=worker.get("gmaps_rating"),
    )

    # Contact information (unmasked)
    contact = WorkerContact(
        phone=worker.get("phone"),
        whatsapp=worker.get("whatsapp"),
        email=worker.get("email"),
        website=worker.get("website"),
    )

    # Location details
    location = WorkerLocation(
        address=worker.get("address"),
        area=worker.get("location", "Bali"),
        latitude=worker.get("latitude"),
        longitude=worker.get("longitude"),
        maps_url=worker.get("gmaps_url"),
    )

    # Reviews (limit to top 10)
    reviews = []
    # TODO: Fetch actual reviews from worker_reviews table
    # For now, use preview_review if available
    if worker.get("preview_review"):
        reviews.append(
            WorkerReview(
                rating=int(worker.get("gmaps_rating", 5)),
                text=worker["preview_review"],
                reviewer="Google Maps User",
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                source="google_maps",
            )
        )

    # Generate negotiation script based on trust score
    negotiation_script = generate_negotiation_tips(worker)

    return WorkerFullDetails(
        id=worker["id"],
        business_name=worker.get("business_name") or worker.get("name", "Unknown"),
        trust_score=trust_score,
        contact=contact,
        location=location,
        reviews=reviews,
        specializations=worker.get("specializations", []),
        photos_count=worker.get("gmaps_photos_count", 0),
        opening_hours=worker.get("opening_hours"),
        categories=worker.get("gmaps_categories", []),
        price_idr_per_day=worker.get("olx_price_idr"),
        negotiation_script=negotiation_script,
        unlocked_at=datetime.now(timezone.utc),
    )


def generate_negotiation_tips(worker: dict[str, Any]) -> str:
    """
    Generate AI-powered negotiation tips based on worker trust score and data.

    Args:
        worker: Worker data dictionary

    Returns:
        str: Negotiation guidance script
    """
    trust_score = worker.get("trust_score", 0)
    trust_level = worker.get("trust_level", "LOW")
    review_count = worker.get("gmaps_review_count", 0)
    rating = worker.get("gmaps_rating", 0.0)

    tips = []

    # Trust level context
    if trust_level == "VERIFIED":
        tips.append(f"✓ This contractor has VERIFIED status ({trust_score}/100 trust score) with {review_count} reviews.")
        tips.append("They have strong credentials - you're in good hands but expect premium pricing.")
    elif trust_level == "HIGH":
        tips.append(f"✓ This contractor has HIGH trust ({trust_score}/100) with {review_count} reviews.")
        tips.append("Solid reputation - fair pricing expected with good quality.")
    elif trust_level == "MEDIUM":
        tips.append(f"⚠️ This contractor has MEDIUM trust ({trust_score}/100).")
        tips.append("Ask for references and photos of completed work before committing.")
    else:
        tips.append(f"⚠️ This contractor has LOW trust ({trust_score}/100).")
        tips.append("Exercise caution. Request detailed quotes, timeline, and verify credentials.")

    # Pricing guidance
    if worker.get("olx_price_idr"):
        tips.append(f"💰 Listed rate: {worker['olx_price_idr']:,} IDR/day")
    else:
        tips.append("💰 No published rates - negotiate based on project scope.")

    # Review insights
    if rating and rating >= 4.5:
        tips.append(f"⭐ Excellent rating ({rating}/5.0) - quality work expected.")
    elif rating and rating >= 4.0:
        tips.append(f"⭐ Good rating ({rating}/5.0) - generally satisfied customers.")

    # Negotiation tactics
    tips.append("\n📋 Negotiation Tips:")
    tips.append("• Ask about warranty and post-completion support")
    tips.append("• Request detailed timeline with milestones")
    tips.append("• Clarify payment schedule (deposit, progress payments, final)")
    tips.append("• Get quotes from 2-3 contractors for comparison")

    if trust_level in ["VERIFIED", "HIGH"]:
        tips.append("• Focus on timeline and warranty rather than heavy price negotiation")
    else:
        tips.append("• Consider lower deposit until you verify their work quality")

    return "\n".join(tips)
