"""
Unit tests for worker matching and ranking service.

Tests cover:
- Project type to specialization mapping
- Location relevance scoring
- Specialization matching
- Budget relevance
- Overall ranking algorithm
- Worker filtering and sorting
"""

import pytest

from app.services.trust_calculator import TrustLevel
from app.services.worker_matcher import (
    BALI_AREA_GROUPS,
    BUDGET_RANGES,
    calculate_budget_relevance,
    calculate_location_relevance,
    calculate_overall_rank_score,
    calculate_specialization_match,
    filter_by_trust_level,
    map_project_type_to_specialization,
    rank_workers,
)


class TestProjectTypeMapping:
    """Test project type to specialization mapping"""

    def test_maps_pool_projects(self):
        """Should map all pool variants to 'pool'"""
        assert map_project_type_to_specialization("pool_construction") == "pool"
        assert map_project_type_to_specialization("pool_renovation") == "pool"
        assert map_project_type_to_specialization("swimming_pool") == "pool"

    def test_maps_bathroom_projects(self):
        """Should map bathroom variants to 'bathroom'"""
        assert map_project_type_to_specialization("bathroom_renovation") == "bathroom"
        assert map_project_type_to_specialization("bathroom_remodel") == "bathroom"

    def test_maps_kitchen_projects(self):
        """Should map kitchen variants to 'kitchen'"""
        assert map_project_type_to_specialization("kitchen_renovation") == "kitchen"
        assert map_project_type_to_specialization("kitchen_remodel") == "kitchen"

    def test_maps_general_construction(self):
        """Should map general construction types"""
        assert map_project_type_to_specialization("general_construction") == "general"
        assert map_project_type_to_specialization("home_renovation") == "general"
        assert map_project_type_to_specialization("renovation") == "general"

    def test_defaults_to_general(self):
        """Should default unknown types to 'general'"""
        assert map_project_type_to_specialization("unknown_type") == "general"
        assert map_project_type_to_specialization("tile_installation") == "general"

    def test_handles_case_insensitivity(self):
        """Should handle different cases"""
        assert map_project_type_to_specialization("POOL_CONSTRUCTION") == "pool"
        assert map_project_type_to_specialization("Pool_Renovation") == "pool"


class TestLocationRelevance:
    """Test location relevance scoring"""

    def test_exact_area_match(self):
        """Should score 1.0 for exact match"""
        assert calculate_location_relevance("Canggu", "Canggu") == 1.0
        assert calculate_location_relevance("Seminyak", "Seminyak") == 1.0

    def test_partial_area_match(self):
        """Should score 1.0 for partial matches"""
        assert calculate_location_relevance("Canggu", "Canggu, Bali") == 1.0
        assert calculate_location_relevance("North Canggu", "Canggu") == 1.0

    def test_same_area_group_match(self):
        """Should score 0.8 for same area group (South, Central, etc.)"""
        # Both in South Bali
        score = calculate_location_relevance("Canggu", "Seminyak")
        assert score == 0.8

        score = calculate_location_relevance("Kuta", "Jimbaran")
        assert score == 0.8

    def test_different_area_same_island(self):
        """Should score 0.5 for different areas"""
        # Canggu (South) vs Ubud (East)
        score = calculate_location_relevance("Canggu", "Ubud")
        assert score == 0.5

        # Seminyak (South) vs Lovina (North)
        score = calculate_location_relevance("Seminyak", "Lovina")
        assert score == 0.5

    def test_handles_missing_location(self):
        """Should score 0.3 for missing location data"""
        assert calculate_location_relevance("", "Canggu") == 0.3
        assert calculate_location_relevance("Canggu", "") == 0.3
        assert calculate_location_relevance(None, "Canggu") == 0.3

    def test_case_insensitive_matching(self):
        """Should handle case differences"""
        assert calculate_location_relevance("CANGGU", "canggu") == 1.0
        assert calculate_location_relevance("Canggu", "CANGGU") == 1.0


class TestSpecializationMatch:
    """Test specialization matching logic"""

    def test_exact_specialization_match(self):
        """Should score 1.0 for exact match"""
        assert calculate_specialization_match(["pool"], "pool") == 1.0
        assert calculate_specialization_match(["pool", "general"], "pool") == 1.0

    def test_general_contractor_match(self):
        """Should score 0.7 for general contractors"""
        assert calculate_specialization_match(["general"], "pool") == 0.7
        assert calculate_specialization_match(["general"], "bathroom") == 0.7

    def test_no_relevant_specialization(self):
        """Should score 0.0 for no match"""
        assert calculate_specialization_match(["bathroom"], "pool") == 0.0
        assert calculate_specialization_match(["kitchen"], "pool") == 0.0

    def test_handles_empty_specializations(self):
        """Should score 0.0 for empty specializations"""
        assert calculate_specialization_match([], "pool") == 0.0
        assert calculate_specialization_match(None, "pool") == 0.0


class TestBudgetRelevance:
    """Test budget relevance scoring"""

    def test_price_within_budget_range(self):
        """Should score 1.0 when price is in range"""
        # Low budget: 0-50M IDR
        assert calculate_budget_relevance(30_000_000, "low") == 1.0
        assert calculate_budget_relevance(45_000_000, "low") == 1.0

        # Medium budget: 50-150M IDR
        assert calculate_budget_relevance(100_000_000, "medium") == 1.0

        # High budget: 150M+ IDR
        assert calculate_budget_relevance(200_000_000, "high") == 1.0

    def test_price_outside_budget_range(self):
        """Should score 0.3 when price is out of range"""
        # Too expensive for low budget
        assert calculate_budget_relevance(100_000_000, "low") == 0.3

        # Too cheap for high budget (might be suspicious)
        assert calculate_budget_relevance(30_000_000, "high") == 0.3

    def test_handles_missing_data(self):
        """Should score 0.5 for missing budget or price data"""
        assert calculate_budget_relevance(None, "medium") == 0.5
        assert calculate_budget_relevance(100_000_000, None) == 0.5
        assert calculate_budget_relevance(None, None) == 0.5


class TestOverallRankScore:
    """Test overall ranking score calculation"""

    def test_perfect_match(self):
        """Should score high for perfect match"""
        worker = {
            "trust_score": 90,
            "specializations": ["pool"],
            "location": "Canggu",
            "daily_rate_idr": 45_000_000,
        }
        score = calculate_overall_rank_score(
            worker, "pool", "Canggu", "low"
        )
        # High trust (90/100), exact location (1.0), exact specialization (1.0), in budget (1.0)
        assert score > 90

    def test_good_match_different_location(self):
        """Should score moderately for good worker in different area"""
        worker = {
            "trust_score": 85,
            "specializations": ["pool"],
            "location": "Seminyak",  # South Bali, same group as Canggu
            "daily_rate_idr": 45_000_000,
        }
        score = calculate_overall_rank_score(
            worker, "pool", "Canggu", "low"
        )
        # High trust, same area group (0.8), exact spec, in budget
        assert 80 < score < 90

    def test_general_contractor_lower_score(self):
        """Should score lower for general contractor"""
        worker = {
            "trust_score": 85,
            "specializations": ["general"],  # Not specialist
            "location": "Canggu",
            "daily_rate_idr": 45_000_000,
        }
        score = calculate_overall_rank_score(
            worker, "pool", "Canggu", "low"
        )
        # High trust but general contractor (0.7 spec match)
        # Score: (0.85*0.5) + (1.0*0.2) + (0.7*0.2) + (1.0*0.1) = 0.865 = 86.5
        assert 85 < score < 90

    def test_low_trust_worker(self):
        """Should score low for low trust worker"""
        worker = {
            "trust_score": 45,  # Low trust
            "specializations": ["pool"],
            "location": "Canggu",
            "daily_rate_idr": 45_000_000,
        }
        score = calculate_overall_rank_score(
            worker, "pool", "Canggu", "low"
        )
        # Low trust dominates score (50% weight)
        # Score: (0.45*0.5) + (1.0*0.2) + (1.0*0.2) + (1.0*0.1) = 0.725 = 72.5
        assert 70 < score < 75

    def test_respects_weight_customization(self):
        """Should respect custom weights"""
        worker = {
            "trust_score": 90,
            "specializations": ["pool"],
            "location": "Ubud",  # Far from Canggu
            "daily_rate_idr": 45_000_000,
        }

        # Default weights (trust=0.5, location=0.2)
        default_score = calculate_overall_rank_score(
            worker, "pool", "Canggu", "low"
        )

        # Increase location weight
        location_priority_score = calculate_overall_rank_score(
            worker,
            "pool",
            "Canggu",
            "low",
            trust_weight=0.3,
            location_weight=0.5,
        )

        # Location priority should score lower (Ubud far from Canggu)
        assert location_priority_score < default_score


class TestWorkerRanking:
    """Test full worker ranking workflow"""

    def test_ranks_by_overall_score(self):
        """Should rank workers by overall score"""
        workers = [
            {
                "business_name": "Medium Trust",
                "trust_score": 65,
                "specializations": ["pool"],
                "location": "Canggu",
            },
            {
                "business_name": "High Trust",
                "trust_score": 90,
                "specializations": ["pool"],
                "location": "Canggu",
            },
            {
                "business_name": "Low Trust",
                "trust_score": 45,
                "specializations": ["pool"],
                "location": "Canggu",
            },
        ]

        ranked = rank_workers(workers, "pool_construction", "Canggu")

        assert ranked[0]["business_name"] == "High Trust"
        assert ranked[1]["business_name"] == "Medium Trust"
        assert ranked[2]["business_name"] == "Low Trust"

    def test_filters_by_min_trust_score(self):
        """Should filter out low trust workers"""
        workers = [
            {"trust_score": 85, "specializations": ["pool"], "location": "Canggu"},
            {"trust_score": 35, "specializations": ["pool"], "location": "Canggu"},  # Below min
            {"trust_score": 65, "specializations": ["pool"], "location": "Canggu"},
        ]

        ranked = rank_workers(
            workers, "pool_construction", "Canggu", min_trust_score=40
        )

        assert len(ranked) == 2  # Filtered out trust_score=35

    def test_limits_results_to_max(self):
        """Should limit results to max_results"""
        workers = [
            {"trust_score": 80 + i, "specializations": ["pool"], "location": "Canggu"}
            for i in range(20)
        ]

        ranked = rank_workers(
            workers, "pool_construction", "Canggu", max_results=5
        )

        assert len(ranked) == 5

    def test_adds_ranking_score_to_workers(self):
        """Should add ranking_score field to each worker"""
        workers = [
            {"trust_score": 85, "specializations": ["pool"], "location": "Canggu"}
        ]

        ranked = rank_workers(workers, "pool_construction", "Canggu")

        assert "ranking_score" in ranked[0]
        assert isinstance(ranked[0]["ranking_score"], float)
        assert 0 <= ranked[0]["ranking_score"] <= 100

    def test_prefers_specialists_over_generalists(self):
        """Should rank specialists higher than generalists (same trust)"""
        workers = [
            {
                "business_name": "General Contractor",
                "trust_score": 80,
                "specializations": ["general"],
                "location": "Canggu",
            },
            {
                "business_name": "Pool Specialist",
                "trust_score": 80,
                "specializations": ["pool"],
                "location": "Canggu",
            },
        ]

        ranked = rank_workers(workers, "pool_construction", "Canggu")

        assert ranked[0]["business_name"] == "Pool Specialist"

    def test_prefers_nearby_workers(self):
        """Should rank nearby workers higher (same trust, specialization)"""
        workers = [
            {
                "business_name": "Far Worker",
                "trust_score": 80,
                "specializations": ["pool"],
                "location": "Ubud",  # East Bali
            },
            {
                "business_name": "Nearby Worker",
                "trust_score": 80,
                "specializations": ["pool"],
                "location": "Canggu",  # Requested location
            },
        ]

        ranked = rank_workers(workers, "pool_construction", "Canggu")

        assert ranked[0]["business_name"] == "Nearby Worker"

    def test_handles_empty_workers_list(self):
        """Should handle empty input"""
        ranked = rank_workers([], "pool_construction", "Canggu")
        assert ranked == []

    def test_maps_project_type_automatically(self):
        """Should map project type to specialization"""
        workers = [
            {"trust_score": 80, "specializations": ["bathroom"], "location": "Canggu"},
            {"trust_score": 80, "specializations": ["pool"], "location": "Canggu"},
        ]

        # Request bathroom renovation (maps to "bathroom")
        ranked = rank_workers(workers, "bathroom_renovation", "Canggu")

        # Bathroom specialist should rank first
        assert ranked[0]["specializations"] == ["bathroom"]


class TestTrustLevelFiltering:
    """Test filtering by trust level badges"""

    def test_filters_by_verified_level(self):
        """Should only return VERIFIED workers"""
        workers = [
            {"business_name": "A", "trust_level": "VERIFIED"},
            {"business_name": "B", "trust_level": "HIGH"},
            {"business_name": "C", "trust_level": "MEDIUM"},
        ]

        filtered = filter_by_trust_level(workers, TrustLevel.VERIFIED)
        assert len(filtered) == 1
        assert filtered[0]["business_name"] == "A"

    def test_includes_higher_trust_levels(self):
        """Should include workers with equal or higher trust level"""
        workers = [
            {"business_name": "A", "trust_level": "VERIFIED"},
            {"business_name": "B", "trust_level": "HIGH"},
            {"business_name": "C", "trust_level": "MEDIUM"},
            {"business_name": "D", "trust_level": "LOW"},
        ]

        filtered = filter_by_trust_level(workers, TrustLevel.MEDIUM)
        assert len(filtered) == 3  # VERIFIED, HIGH, MEDIUM

    def test_handles_missing_trust_level(self):
        """Should exclude workers with no trust level"""
        workers = [
            {"business_name": "A", "trust_level": "HIGH"},
            {"business_name": "B"},  # No trust_level field
        ]

        filtered = filter_by_trust_level(workers, TrustLevel.HIGH)
        assert len(filtered) == 1
