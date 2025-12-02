"""
Unit tests for worker deduplication service.

Tests cover:
- Phone normalization (Indonesian formats)
- Business name normalization
- Name similarity scoring
- Duplicate detection logic
- Profile merging strategies
"""

import pytest

from app.services.worker_deduplication import (
    are_workers_duplicates,
    calculate_name_similarity,
    deduplicate_workers,
    merge_worker_profiles,
    normalize_business_name,
    normalize_phone_number,
)


class TestPhoneNormalization:
    """Test Indonesian phone number normalization"""

    def test_normalizes_international_format(self):
        """Should handle +62 prefix"""
        assert normalize_phone_number("+62812345678") == "+62812345678"

    def test_normalizes_country_code_without_plus(self):
        """Should add + to country code"""
        assert normalize_phone_number("62812345678") == "+62812345678"

    def test_normalizes_local_mobile_format(self):
        """Should convert 08xx to +628xx"""
        assert normalize_phone_number("0812345678") == "+62812345678"
        assert normalize_phone_number("0856789012") == "+62856789012"

    def test_normalizes_mobile_without_leading_zero(self):
        """Should handle 8xx format"""
        assert normalize_phone_number("812345678") == "+62812345678"

    def test_normalizes_landline_format(self):
        """Should handle landline numbers"""
        assert normalize_phone_number("0361234567") == "+62361234567"
        assert normalize_phone_number("(0361) 234567") == "+62361234567"

    def test_removes_formatting_characters(self):
        """Should remove spaces, hyphens, parentheses"""
        assert normalize_phone_number("+62 812 345 678") == "+62812345678"
        assert normalize_phone_number("+62-812-345-678") == "+62812345678"
        assert normalize_phone_number("(0812) 345-678") == "+62812345678"

    def test_handles_none_input(self):
        """Should return None for None input"""
        assert normalize_phone_number(None) is None

    def test_handles_empty_string(self):
        """Should return None for empty string"""
        assert normalize_phone_number("") is None

    def test_rejects_invalid_formats(self):
        """Should return None for invalid phone numbers"""
        assert normalize_phone_number("123") is None
        assert normalize_phone_number("invalid") is None
        assert normalize_phone_number("+1234567890") is None  # Non-Indonesian

    def test_handles_whatsapp_format(self):
        """Should normalize WhatsApp numbers"""
        assert normalize_phone_number("+62 812-3456-7890") == "+6281234567890"


class TestBusinessNameNormalization:
    """Test business name normalization for comparison"""

    def test_converts_to_lowercase(self):
        """Should convert names to lowercase"""
        assert normalize_business_name("BALI POOL SERVICE") == "bali pool service"

    def test_removes_indonesian_entity_types(self):
        """Should remove PT, CV, UD, Toko, Jasa"""
        assert normalize_business_name("PT. Bali Pool Service") == "bali pool service"
        assert normalize_business_name("CV Bali Construction") == "bali construction"
        assert normalize_business_name("UD Pak Wayan") == "pak wayan"
        assert normalize_business_name("Toko Bangunan Bali") == "bangunan bali"
        assert normalize_business_name("Jasa Renovasi") == "renovasi"

    def test_removes_english_entity_types(self):
        """Should remove LLC, Inc, Ltd"""
        assert normalize_business_name("Bali Pools LLC") == "bali pools"
        assert normalize_business_name("Construction Inc.") == "construction"
        assert normalize_business_name("Builders Ltd") == "builders"

    def test_removes_possessives(self):
        """Should remove 's from names"""
        assert normalize_business_name("Pak Wayan's Pool Service") == "pak wayan pool service"
        assert normalize_business_name("John's Construction") == "john construction"

    def test_removes_special_characters(self):
        """Should remove &, -, etc."""
        assert normalize_business_name("Pool & Spa Service") == "pool spa service"
        assert normalize_business_name("Bali-Construction") == "baliconstruction"  # Hyphen joins words
        assert normalize_business_name("A+ Pools") == "a pools"

    def test_removes_extra_whitespace(self):
        """Should normalize whitespace"""
        assert normalize_business_name("  Bali   Pool  ") == "bali pool"
        assert normalize_business_name("Bali\t\nPool") == "bali pool"

    def test_handles_empty_string(self):
        """Should handle empty input"""
        assert normalize_business_name("") == ""

    def test_handles_numbers_in_name(self):
        """Should preserve numbers"""
        assert normalize_business_name("24/7 Pool Service") == "247 pool service"


class TestNameSimilarity:
    """Test business name similarity calculation"""

    def test_exact_match_after_normalization(self):
        """Should return 1.0 for normalized exact matches"""
        assert calculate_name_similarity("Bali Pool Service", "bali pool service") == 1.0
        assert calculate_name_similarity("PT. Bali Pool", "Bali Pool") == 1.0

    def test_high_similarity_for_minor_differences(self):
        """Should score high for typos and minor variations"""
        score = calculate_name_similarity("Bali Pool Service", "Bali Pool Services")
        assert score > 0.9

        score = calculate_name_similarity("Pak Wayan Pool", "Pak Wayan Pools")
        assert score > 0.9

    def test_moderate_similarity_for_abbreviations(self):
        """Should score moderately for abbreviations"""
        score = calculate_name_similarity("International Pool Service", "Intl Pool Service")
        assert 0.6 < score < 0.9

    def test_low_similarity_for_different_names(self):
        """Should score low for completely different names"""
        score = calculate_name_similarity("Bali Pool Service", "Canggu Construction")
        assert score < 0.5

    def test_zero_similarity_for_empty_strings(self):
        """Should handle empty strings"""
        score = calculate_name_similarity("", "Bali Pool")
        assert score == 0.0


class TestDuplicateDetection:
    """Test worker duplicate detection logic"""

    def test_detects_exact_phone_match(self):
        """Should match workers with same phone (different formats)"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "phone": "+62812345678",
        }
        worker2 = {
            "business_name": "Different Name",
            "phone": "0812345678",  # Same phone, different format
        }
        assert are_workers_duplicates(worker1, worker2) is True

    def test_detects_place_id_match(self):
        """Should match workers with same Google Maps place_id"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "gmaps_place_id": "ChIJtest123",
        }
        worker2 = {
            "business_name": "Bali Pool Services",
            "gmaps_place_id": "ChIJtest123",
        }
        assert are_workers_duplicates(worker1, worker2, phone_match_required=False) is True

    def test_detects_high_name_similarity_with_location(self):
        """Should match similar names in same location"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "location": "Canggu",
            "phone": None,
        }
        worker2 = {
            "business_name": "Bali Pool Services",
            "location": "Canggu, Bali",
            "phone": None,
        }
        assert are_workers_duplicates(worker1, worker2, phone_match_required=False) is True

    def test_rejects_similar_names_different_locations(self):
        """Should not match similar names in different locations"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "location": "Canggu",
        }
        worker2 = {
            "business_name": "Bali Pool Service",
            "location": "Ubud",
        }
        assert are_workers_duplicates(worker1, worker2, phone_match_required=False) is False

    def test_rejects_different_names_no_phone(self):
        """Should not match different names without phone"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "location": "Canggu",
        }
        worker2 = {
            "business_name": "Canggu Construction",
            "location": "Canggu",
        }
        assert are_workers_duplicates(worker1, worker2, phone_match_required=False) is False

    def test_respects_phone_match_requirement(self):
        """Should require phone match when specified"""
        worker1 = {
            "business_name": "Bali Pool Service",
            "phone": "+62812345678",
            "location": "Canggu",
        }
        worker2 = {
            "business_name": "Bali Pool Services",
            "phone": "+62856789012",  # Different phone
            "location": "Canggu",
        }
        # With phone_match_required=True (default)
        assert are_workers_duplicates(worker1, worker2) is False


class TestProfileMerging:
    """Test worker profile merging logic"""

    def test_returns_single_profile_unchanged(self):
        """Should return single profile as-is"""
        worker = {"business_name": "Bali Pool", "phone": "+62812345678"}
        merged = merge_worker_profiles([worker])
        assert merged["business_name"] == "Bali Pool"

    def test_prefers_higher_priority_source(self):
        """Should use data from higher priority source"""
        workers = [
            {
                "business_name": "Bali Pool (OLX)",
                "source_tier": "olx",
                "phone": "+62812345678",
            },
            {
                "business_name": "Bali Pool Service",
                "source_tier": "google_maps",
                "phone": "+62812345678",
            },
        ]
        merged = merge_worker_profiles(workers)
        assert merged["business_name"] == "Bali Pool Service"  # Google Maps priority

    def test_fills_missing_fields_from_lower_priority(self):
        """Should fill missing fields from any source"""
        workers = [
            {
                "business_name": "Bali Pool",
                "source_tier": "google_maps",
                "gmaps_rating": 4.8,
                "website": None,
            },
            {
                "business_name": "Bali Pools",
                "source_tier": "olx",
                "website": "https://balipools.com",
            },
        ]
        merged = merge_worker_profiles(workers)
        assert merged["business_name"] == "Bali Pool"  # From Google Maps
        assert merged["website"] == "https://balipools.com"  # From OLX (missing in GM)

    def test_aggregates_specializations(self):
        """Should combine unique specializations"""
        workers = [
            {"specializations": ["pool"], "source_tier": "google_maps"},
            {"specializations": ["pool", "general"], "source_tier": "olx"},
        ]
        merged = merge_worker_profiles(workers)
        assert set(merged["specializations"]) == {"pool", "general"}

    def test_takes_maximum_rating(self):
        """Should use highest rating from all sources"""
        workers = [
            {"gmaps_rating": 4.5, "source_tier": "google_maps"},
            {"olx_rating": 4.8, "source_tier": "olx"},
        ]
        merged = merge_worker_profiles(workers)
        assert merged["gmaps_rating"] == 4.8

    def test_sums_review_counts(self):
        """Should sum review counts from all sources"""
        workers = [
            {"gmaps_review_count": 50, "source_tier": "google_maps"},
            {"olx_review_count": 30, "source_tier": "olx"},
        ]
        merged = merge_worker_profiles(workers)
        assert merged["gmaps_review_count"] == 80

    def test_marks_as_merged_profile(self):
        """Should add merge metadata"""
        workers = [
            {"business_name": "Bali Pool", "source_tier": "google_maps"},
            {"business_name": "Bali Pools", "source_tier": "olx"},
        ]
        merged = merge_worker_profiles(workers)
        assert merged["is_merged"] is True
        assert merged["source_count"] == 2
        assert "google_maps" in merged["merged_sources"]
        assert "olx" in merged["merged_sources"]


class TestDeduplication:
    """Test full deduplication workflow"""

    def test_returns_empty_for_empty_input(self):
        """Should handle empty list"""
        assert deduplicate_workers([]) == []

    def test_returns_single_worker_unchanged(self):
        """Should not modify single worker"""
        workers = [{"business_name": "Bali Pool", "phone": "+62812345678"}]
        deduplicated = deduplicate_workers(workers)
        assert len(deduplicated) == 1
        assert deduplicated[0]["business_name"] == "Bali Pool"

    def test_merges_exact_phone_duplicates(self):
        """Should merge workers with same phone"""
        workers = [
            {
                "business_name": "Bali Pool",
                "phone": "+62812345678",
                "source_tier": "google_maps",
            },
            {
                "business_name": "Bali Pools",
                "phone": "0812345678",
                "source_tier": "olx",
            },
        ]
        deduplicated = deduplicate_workers(workers)
        assert len(deduplicated) == 1
        assert deduplicated[0]["is_merged"] is True

    def test_merges_similar_names_same_location(self):
        """Should merge similar names in same location"""
        workers = [
            {
                "business_name": "Bali Pool Service",
                "location": "Canggu",
                "source_tier": "google_maps",
            },
            {
                "business_name": "Bali Pool Services",
                "location": "Canggu, Bali",
                "source_tier": "olx",
            },
        ]
        deduplicated = deduplicate_workers(workers)
        assert len(deduplicated) == 1

    def test_keeps_different_workers_separate(self):
        """Should not merge clearly different workers"""
        workers = [
            {
                "business_name": "Bali Pool Service",
                "phone": "+62812345678",
                "location": "Canggu",
            },
            {
                "business_name": "Ubud Construction",
                "phone": "+62856789012",
                "location": "Ubud",
            },
        ]
        deduplicated = deduplicate_workers(workers)
        assert len(deduplicated) == 2

    def test_handles_multiple_duplicate_groups(self):
        """Should handle multiple separate duplicate groups"""
        workers = [
            # Group 1: Bali Pool
            {"business_name": "Bali Pool", "phone": "+62812345678", "source_tier": "google_maps"},
            {"business_name": "Bali Pools", "phone": "+62812345678", "source_tier": "olx"},
            # Group 2: Canggu Construction
            {"business_name": "Canggu Construction", "phone": "+62856789012", "source_tier": "google_maps"},
            {"business_name": "Canggu Builders", "phone": "+62856789012", "source_tier": "olx"},
            # Group 3: Unique worker
            {"business_name": "Ubud Renovations", "phone": "+62811111111", "source_tier": "google_maps"},
        ]
        deduplicated = deduplicate_workers(workers)
        assert len(deduplicated) == 3  # 2 merged groups + 1 unique

    def test_deduplication_is_idempotent(self):
        """Should produce same result when run multiple times"""
        workers = [
            {"business_name": "Bali Pool", "phone": "+62812345678", "source_tier": "google_maps"},
            {"business_name": "Bali Pools", "phone": "+62812345678", "source_tier": "olx"},
        ]
        first_pass = deduplicate_workers(workers)
        second_pass = deduplicate_workers(first_pass)
        assert len(first_pass) == len(second_pass)
