"""
Google Maps scraper integration using Apify compass/crawler-google-places actor.

Cost-optimized configuration for worker discovery in Bali:
- Base cost: $0.004 per place
- Estimated monthly cost: <$1 with aggressive caching
- Safety limits: Max 20 results per search, max 5 searches per run
"""

from datetime import datetime, timedelta
from typing import Any

from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.supabase import save_scrape_job, update_scrape_job_status

settings = get_settings()

# Cost control safety limits
MAX_RESULTS_PER_SEARCH = 20  # $0.08 per search maximum
MAX_SEARCHES_PER_RUN = 5  # $0.40 per run maximum
CACHE_TTL_DAYS = 7  # Weekly refresh (reduce API costs)

# Search queries for Bali workers (Indonesian + English)
WORKER_SEARCH_QUERIES = {
    "pool": [
        "Kontraktor Kolam Renang Canggu",
        "Pool Construction Bali",
        "Swimming Pool Builder Seminyak",
    ],
    "bathroom": [
        "Bathroom Renovation Bali",
        "Jasa Renovasi Kamar Mandi Canggu",
        "Bathroom Contractor Ubud",
    ],
    "kitchen": [
        "Kitchen Renovation Bali",
        "Jasa Renovasi Dapur Canggu",
        "Kitchen Remodel Seminyak",
    ],
    "general": [
        "Construction Contractor Bali",
        "Jasa Renovasi Rumah Bali",
        "Building Contractor Canggu",
        "Jasa Tukang Bangunan Bali",
    ],
}


def get_apify_client() -> ApifyClient:
    """
    Get initialized Apify client.

    Returns:
        ApifyClient: Configured Apify client instance
    """
    return ApifyClient(settings.apify_token)


def create_optimized_search_input(
    search_queries: list[str],
    location: str = "Bali, Indonesia",
    max_results: int = MAX_RESULTS_PER_SEARCH,
    min_rating: float = 4.0,
) -> dict[str, Any]:
    """
    Create cost-optimized Apify input configuration for Google Maps scraping.

    Optimization strategies:
    - Disable expensive features (contacts, images, detailed scraping)
    - Add quality filters (minimum rating, must have website)
    - Limit results per search
    - Skip closed places

    Args:
        search_queries: List of search strings
        location: Location to search in
        max_results: Maximum results per search query
        min_rating: Minimum rating filter (0.0-5.0)

    Returns:
        dict: Apify actor input configuration
    """
    return {
        # Search configuration
        "searchStringsArray": search_queries[:MAX_SEARCHES_PER_RUN],
        "locationQuery": location,
        "maxCrawledPlacesPerSearch": min(max_results, MAX_RESULTS_PER_SEARCH),
        "language": "en",
        # Quality filters (reduce low-quality results)
        "placeMinimumStars": str(min_rating),
        "website": "withWebsite",  # Only businesses with websites (higher trust)
        "skipClosedPlaces": True,
        "searchMatching": "all",
        # Disable expensive features to minimize cost
        "maxImages": 0,  # No images needed
        "maxReviews": 0,  # Don't scrape review text (just count)
        "maxQuestions": 0,  # No Q&A
        "scrapeContacts": False,  # Expensive! We get phone from basic data
        "scrapeReviewsPersonalData": False,  # Don't need reviewer details
        "scrapePlaceDetailPage": False,  # Basic data is enough
        "scrapeDirectories": False,
        "scrapeImageAuthors": False,
        "scrapeTableReservationProvider": False,
        "includeWebResults": False,
        "maximumLeadsEnrichmentRecords": 0,
        # Review settings (we only need count, not text)
        "reviewsSort": "newest",
        "reviewsFilterString": "",
        "reviewsOrigin": "all",
        "allPlacesNoSearchAction": "",
    }


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def scrape_google_maps_workers(
    project_type: str,
    location: str = "Bali, Indonesia",
    max_results_per_search: int = 20,
    min_rating: float = 4.0,
) -> list[dict[str, Any]]:
    """
    Scrape worker/contractor listings from Google Maps using Apify.

    Cost estimate: $0.08-$0.40 per run depending on query count.
    Results are cached in database to minimize repeat scraping costs.

    Args:
        project_type: Type of project ('pool', 'bathroom', 'kitchen', 'general')
        location: Geographic location to search
        max_results_per_search: Max results per search query (capped at 20)
        min_rating: Minimum Google Maps rating filter

    Returns:
        list[dict]: List of worker profiles from Google Maps

    Raises:
        ValueError: If project_type is invalid
        Exception: If Apify scraping fails after retries
    """
    if project_type not in WORKER_SEARCH_QUERIES:
        raise ValueError(
            f"Invalid project_type: {project_type}. "
            f"Must be one of: {list(WORKER_SEARCH_QUERIES.keys())}"
        )

    search_queries = WORKER_SEARCH_QUERIES[project_type]

    # Create optimized input configuration
    actor_input = create_optimized_search_input(
        search_queries=search_queries,
        location=location,
        max_results=max_results_per_search,
        min_rating=min_rating,
    )

    # Estimate cost (base rate: $0.004 per place)
    estimated_places = len(search_queries[:MAX_SEARCHES_PER_RUN]) * min(
        max_results_per_search, MAX_RESULTS_PER_SEARCH
    )
    estimated_cost = estimated_places * 0.004

    # Create scrape job record
    job_id = await save_scrape_job(
        job_type="worker_discovery",
        apify_actor_id="compass/crawler-google-places",
        input_params=actor_input,
        estimated_cost_usd=estimated_cost,
    )

    try:
        # Initialize Apify client
        client = get_apify_client()

        # Start the actor run
        run = client.actor("compass/crawler-google-places").call(run_input=actor_input)

        # Update job with run ID
        await update_scrape_job_status(
            job_id=job_id,
            status="running",
            apify_run_id=run["id"],
            started_at=datetime.utcnow().isoformat(),
        )

        # Fetch results from dataset
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            # Transform Apify output to our schema
            worker_data = transform_gmaps_result(item)
            results.append(worker_data)

        # Update job as completed
        await update_scrape_job_status(
            job_id=job_id,
            status="completed",
            output_data={"results": results[:100]},  # Store first 100 for reference
            results_count=len(results),
            actual_cost_usd=estimated_cost,  # Apify doesn't provide actual cost in run
            completed_at=datetime.utcnow().isoformat(),
        )

        return results

    except Exception as e:
        # Update job as failed
        await update_scrape_job_status(
            job_id=job_id,
            status="failed",
            error_message=str(e),
            completed_at=datetime.utcnow().isoformat(),
        )
        raise


def transform_gmaps_result(raw_data: dict[str, Any]) -> dict[str, Any]:
    """
    Transform Apify Google Maps output to our worker schema.

    Input example from Apify:
    {
        "title": "Moon Cheese Restaurant",
        "totalScore": 4.8,
        "reviewsCount": 1022,
        "street": "88-11 31st Ave",
        "city": "East Elmhurst",
        "state": "New York",
        "countryCode": "US",
        "website": "https://mooncheeserestaurant.shop/",
        "phone": "(718) 255-1168",
        "categoryName": "Restaurant",
        "url": "https://www.google.com/maps/search/?api=1&..."
    }

    Args:
        raw_data: Raw result from Apify actor

    Returns:
        dict: Transformed worker profile matching our schema
    """
    # Extract place ID from URL (if available)
    url = raw_data.get("url", "")
    place_id = None
    if "query_place_id=" in url:
        place_id = url.split("query_place_id=")[1].split("&")[0]

    # Build full address
    address_parts = [
        raw_data.get("street"),
        raw_data.get("city"),
        raw_data.get("state"),
    ]
    full_address = ", ".join(filter(None, address_parts))

    # Determine specializations from category
    category = raw_data.get("categoryName", "").lower()
    specializations = infer_specializations(category, raw_data.get("title", ""))

    return {
        "business_name": raw_data.get("title"),
        "source_tier": "google_maps",
        # Contact
        "phone": raw_data.get("phone"),
        "website": raw_data.get("website"),
        "whatsapp": None,  # Not provided by Google Maps scraper
        "email": None,  # Not provided in basic scraping
        # Location
        "location": raw_data.get("city", "Bali"),  # Fallback to Bali
        "address": full_address,
        "latitude": raw_data.get("latitude"),
        "longitude": raw_data.get("longitude"),
        # Google Maps data
        "gmaps_place_id": place_id,
        "gmaps_rating": raw_data.get("totalScore"),
        "gmaps_review_count": raw_data.get("reviewsCount", 0),
        "gmaps_photos_count": 0,  # Not available without detailed scraping
        "gmaps_url": url,
        "gmaps_categories": [raw_data.get("categoryName")] if raw_data.get("categoryName") else [],
        # Specializations
        "specializations": specializations,
        # Metadata
        "last_scraped_at": datetime.utcnow().isoformat(),
        "is_active": True,
    }


def infer_specializations(category: str, title: str) -> list[str]:
    """
    Infer worker specializations from Google Maps category and business title.

    Args:
        category: Google Maps category name
        title: Business title/name

    Returns:
        list[str]: Inferred specializations
    """
    specializations = set()
    combined_text = f"{category} {title}".lower()

    # Pool-related keywords
    if any(
        keyword in combined_text
        for keyword in ["pool", "kolam", "swimming", "renang"]
    ):
        specializations.add("pool")

    # Bathroom-related keywords
    if any(
        keyword in combined_text
        for keyword in ["bathroom", "kamar mandi", "plumbing", "toilet"]
    ):
        specializations.add("bathroom")

    # Kitchen-related keywords
    if any(keyword in combined_text for keyword in ["kitchen", "dapur"]):
        specializations.add("kitchen")

    # Construction/general contractor keywords
    if any(
        keyword in combined_text
        for keyword in [
            "construction",
            "contractor",
            "builder",
            "tukang",
            "renovasi",
            "renovation",
            "bangunan",
        ]
    ):
        specializations.add("general")

    # Default to general if no specific specialization found
    return list(specializations) if specializations else ["general"]
