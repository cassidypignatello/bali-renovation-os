"""
Worker ranking and matching service for project-based worker discovery.

Handles:
- Project type to specialization mapping
- Worker ranking by trust score and relevance
- Location-based relevance scoring
- Budget-based filtering and scoring
- Multi-criteria ranking with weighted scores
"""

from typing import Any

from app.services.trust_calculator import TrustLevel


# Map user-facing project types to worker specializations
PROJECT_TYPE_TO_SPECIALIZATION = {
    # Pool projects
    "pool_construction": "pool",
    "pool_renovation": "pool",
    "pool_installation": "pool",
    "pool_repair": "pool",
    "pool_maintenance": "pool",
    "swimming_pool": "pool",
    # Bathroom projects
    "bathroom_renovation": "bathroom",
    "bathroom_remodel": "bathroom",
    "bathroom_installation": "bathroom",
    "bathroom_repair": "bathroom",
    "bathroom_upgrade": "bathroom",
    # Kitchen projects
    "kitchen_renovation": "kitchen",
    "kitchen_remodel": "kitchen",
    "kitchen_installation": "kitchen",
    "kitchen_upgrade": "kitchen",
    "kitchen_repair": "kitchen",
    # General construction
    "general_construction": "general",
    "home_renovation": "general",
    "villa_construction": "general",
    "building_renovation": "general",
    "house_construction": "general",
    "renovation": "general",
    "construction": "general",
}

# Bali area hierarchy for location matching
BALI_AREA_GROUPS = {
    "south": ["canggu", "seminyak", "kuta", "legian", "jimbaran", "uluwatu", "pecatu"],
    "central": ["denpasar", "sanur", "renon"],
    "east": ["ubud", "gianyar", "sidemen"],
    "north": ["lovina", "singaraja"],
}

# Budget range definitions (IDR)
BUDGET_RANGES = {
    "low": (0, 50_000_000),  # Under 50M IDR
    "medium": (50_000_000, 150_000_000),  # 50-150M IDR
    "high": (150_000_000, float("inf")),  # Over 150M IDR
}


def map_project_type_to_specialization(project_type: str) -> str:
    """
    Convert user's project_type to worker specialization for scraping/matching.

    Args:
        project_type: User-facing project type (e.g., "pool_construction")

    Returns:
        Worker specialization (e.g., "pool")

    Examples:
        >>> map_project_type_to_specialization("pool_construction")
        'pool'
        >>> map_project_type_to_specialization("bathroom_renovation")
        'bathroom'
        >>> map_project_type_to_specialization("unknown_type")
        'general'
    """
    return PROJECT_TYPE_TO_SPECIALIZATION.get(project_type.lower(), "general")


def calculate_location_relevance(
    worker_location: str, requested_location: str
) -> float:
    """
    Calculate location relevance score between worker and requested location.

    Scoring:
    - 1.0: Exact area match (Canggu = Canggu)
    - 0.8: Same area group (Canggu → Seminyak, both South)
    - 0.5: Different area, same island (Canggu → Ubud)
    - 0.3: No location data available

    Args:
        worker_location: Worker's location/area
        requested_location: User's requested location

    Returns:
        Relevance score between 0.0 and 1.0

    Examples:
        >>> calculate_location_relevance("Canggu", "Canggu")
        1.0
        >>> calculate_location_relevance("Canggu", "Seminyak")
        0.8
        >>> calculate_location_relevance("Canggu", "Ubud")
        0.5
    """
    if not worker_location or not requested_location:
        return 0.3  # Low score for missing location data

    worker_loc = worker_location.lower().strip()
    requested_loc = requested_location.lower().strip()

    # Exact match
    if worker_loc == requested_loc or worker_loc in requested_loc or requested_loc in worker_loc:
        return 1.0

    # Find area groups for both locations
    worker_group = None
    requested_group = None

    for group_name, areas in BALI_AREA_GROUPS.items():
        if any(area in worker_loc for area in areas):
            worker_group = group_name
        if any(area in requested_loc for area in areas):
            requested_group = group_name

    # Same area group (South, Central, etc.)
    if worker_group and requested_group and worker_group == requested_group:
        return 0.8

    # Different areas but same island
    return 0.5


def calculate_specialization_match(
    worker_specializations: list[str], required_specialization: str
) -> float:
    """
    Calculate how well worker's specializations match requirement.

    Scoring:
    - 1.0: Exact specialization match
    - 0.7: Has "general" specialization (can do anything)
    - 0.0: No relevant specialization

    Args:
        worker_specializations: List of worker's specializations
        required_specialization: Required specialization for project

    Returns:
        Match score between 0.0 and 1.0

    Examples:
        >>> calculate_specialization_match(["pool", "general"], "pool")
        1.0
        >>> calculate_specialization_match(["general"], "pool")
        0.7
        >>> calculate_specialization_match(["bathroom"], "pool")
        0.0
    """
    if not worker_specializations:
        return 0.0

    # Exact match
    if required_specialization in worker_specializations:
        return 1.0

    # General contractor can do most things (lower confidence)
    if "general" in worker_specializations:
        return 0.7

    # No relevant specialization
    return 0.0


def calculate_budget_relevance(
    worker_price: float | None, budget_range: str | None
) -> float:
    """
    Calculate budget relevance score.

    Scoring:
    - 1.0: Worker price within budget range
    - 0.5: No budget or price data (neutral)
    - 0.3: Worker price outside budget range

    Args:
        worker_price: Worker's daily/project rate (IDR)
        budget_range: User's budget range (low, medium, high)

    Returns:
        Relevance score between 0.0 and 1.0

    Examples:
        >>> calculate_budget_relevance(40_000_000, "low")
        1.0
        >>> calculate_budget_relevance(100_000_000, "low")
        0.3
        >>> calculate_budget_relevance(None, "medium")
        0.5
    """
    if not budget_range or not worker_price:
        return 0.5  # Neutral score for missing data

    min_budget, max_budget = BUDGET_RANGES.get(budget_range, (0, float("inf")))

    # Worker price within budget range
    if min_budget <= worker_price <= max_budget:
        return 1.0

    # Worker price outside budget range
    return 0.3


def calculate_overall_rank_score(
    worker: dict[str, Any],
    required_specialization: str,
    requested_location: str,
    budget_range: str | None = None,
    trust_weight: float = 0.5,
    location_weight: float = 0.2,
    specialization_weight: float = 0.2,
    budget_weight: float = 0.1,
) -> float:
    """
    Calculate overall ranking score for worker based on multiple criteria.

    Weighted scoring formula:
    score = (trust_score_normalized * trust_weight) +
            (location_relevance * location_weight) +
            (specialization_match * specialization_weight) +
            (budget_relevance * budget_weight)

    Default weights:
    - Trust score: 50% (most important)
    - Location: 20% (important for travel cost)
    - Specialization: 20% (must be able to do the work)
    - Budget: 10% (nice to have)

    Args:
        worker: Worker profile dict
        required_specialization: Required specialization
        requested_location: User's location
        budget_range: User's budget range (optional)
        trust_weight: Weight for trust score (0-1)
        location_weight: Weight for location relevance (0-1)
        specialization_weight: Weight for specialization match (0-1)
        budget_weight: Weight for budget relevance (0-1)

    Returns:
        Overall ranking score between 0.0 and 100.0

    Examples:
        >>> worker = {
        ...     "trust_score": 85,
        ...     "specializations": ["pool"],
        ...     "location": "Canggu",
        ...     "daily_rate_idr": 45_000_000
        ... }
        >>> calculate_overall_rank_score(worker, "pool", "Canggu", "low")
        92.5
    """
    # Normalize trust score to 0-1 scale
    trust_score = worker.get("trust_score", 0) / 100.0

    # Calculate component scores
    location_score = calculate_location_relevance(
        worker.get("location", ""), requested_location
    )

    specialization_score = calculate_specialization_match(
        worker.get("specializations", []), required_specialization
    )

    # Get worker price (try different fields)
    worker_price = (
        worker.get("daily_rate_idr")
        or worker.get("price_idr_per_day")
        or worker.get("olx_price_idr")
    )
    budget_score = calculate_budget_relevance(worker_price, budget_range)

    # Calculate weighted score
    overall_score = (
        (trust_score * trust_weight)
        + (location_score * location_weight)
        + (specialization_score * specialization_weight)
        + (budget_score * budget_weight)
    )

    # Convert to 0-100 scale
    return overall_score * 100.0


def rank_workers(
    workers: list[dict[str, Any]],
    project_type: str,
    location: str,
    min_trust_score: int = 40,
    budget_range: str | None = None,
    max_results: int = 10,
) -> list[dict[str, Any]]:
    """
    Rank and filter workers based on project requirements.

    Process:
    1. Map project type to specialization
    2. Filter by minimum trust score
    3. Calculate ranking scores for each worker
    4. Sort by ranking score (descending)
    5. Return top N results

    Args:
        workers: List of worker profiles
        project_type: User's project type
        location: User's location
        min_trust_score: Minimum trust score filter (0-100)
        budget_range: User's budget range (optional)
        max_results: Maximum results to return

    Returns:
        Ranked and filtered list of workers with ranking scores

    Examples:
        >>> workers = [
        ...     {"business_name": "Bali Pool", "trust_score": 85, "specializations": ["pool"], "location": "Canggu"},
        ...     {"business_name": "Ubud Construction", "trust_score": 65, "specializations": ["general"], "location": "Ubud"}
        ... ]
        >>> ranked = rank_workers(workers, "pool_construction", "Canggu")
        >>> ranked[0]["business_name"]
        'Bali Pool'
    """
    # Map project type to specialization
    required_specialization = map_project_type_to_specialization(project_type)

    # Filter by minimum trust score
    filtered_workers = [
        w for w in workers if w.get("trust_score", 0) >= min_trust_score
    ]

    # Calculate ranking scores
    for worker in filtered_workers:
        worker["ranking_score"] = calculate_overall_rank_score(
            worker=worker,
            required_specialization=required_specialization,
            requested_location=location,
            budget_range=budget_range,
        )

    # Sort by ranking score (descending)
    ranked_workers = sorted(
        filtered_workers, key=lambda w: w["ranking_score"], reverse=True
    )

    # Return top N results
    return ranked_workers[:max_results]


def filter_by_trust_level(
    workers: list[dict[str, Any]], min_trust_level: TrustLevel
) -> list[dict[str, Any]]:
    """
    Filter workers by minimum trust level badge.

    Trust level hierarchy:
    VERIFIED (80+) > HIGH (60-79) > MEDIUM (40-59) > LOW (<40)

    Args:
        workers: List of worker profiles
        min_trust_level: Minimum trust level

    Returns:
        Filtered list of workers

    Examples:
        >>> workers = [
        ...     {"business_name": "A", "trust_level": "VERIFIED"},
        ...     {"business_name": "B", "trust_level": "MEDIUM"}
        ... ]
        >>> filtered = filter_by_trust_level(workers, TrustLevel.HIGH)
        >>> len(filtered)
        1
    """
    trust_level_scores = {
        TrustLevel.VERIFIED: 4,
        TrustLevel.HIGH: 3,
        TrustLevel.MEDIUM: 2,
        TrustLevel.LOW: 1,
    }

    min_score = trust_level_scores.get(min_trust_level, 0)

    return [
        w
        for w in workers
        if trust_level_scores.get(w.get("trust_level"), 0) >= min_score
    ]
