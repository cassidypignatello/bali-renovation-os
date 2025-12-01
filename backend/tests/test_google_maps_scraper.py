"""
Unit tests for Google Maps scraper integration.

Tests use mocked Apify client to avoid actual API costs.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.google_maps_scraper import (
    create_optimized_search_input,
    get_apify_client,
    infer_specializations,
    scrape_google_maps_workers,
    transform_gmaps_result,
    MAX_RESULTS_PER_SEARCH,
    MAX_SEARCHES_PER_RUN,
)


class TestOptimizedSearchInput:
    """Test cost-optimized search input configuration"""

    def test_creates_valid_input_structure(self):
        """Should create valid Apify actor input"""
        queries = ["Pool Construction Bali", "Swimming Pool Builder"]
        result = create_optimized_search_input(queries)

        assert "searchStringsArray" in result
        assert "locationQuery" in result
        assert "maxCrawledPlacesPerSearch" in result
        assert result["locationQuery"] == "Bali, Indonesia"

    def test_respects_max_searches_limit(self):
        """Should cap searches at MAX_SEARCHES_PER_RUN"""
        queries = ["query1", "query2", "query3", "query4", "query5", "query6", "query7"]
        result = create_optimized_search_input(queries)

        assert len(result["searchStringsArray"]) == MAX_SEARCHES_PER_RUN

    def test_respects_max_results_limit(self):
        """Should cap results at MAX_RESULTS_PER_SEARCH"""
        queries = ["Pool Construction"]
        result = create_optimized_search_input(queries, max_results=50)

        assert result["maxCrawledPlacesPerSearch"] == MAX_RESULTS_PER_SEARCH

    def test_applies_quality_filters(self):
        """Should enable quality filters to reduce costs"""
        queries = ["Pool Builder"]
        result = create_optimized_search_input(queries, min_rating=4.5)

        assert result["placeMinimumStars"] == "4.5"
        assert result["website"] == "withWebsite"
        assert result["skipClosedPlaces"] is True

    def test_disables_expensive_features(self):
        """Should disable expensive scraping features"""
        queries = ["Pool Builder"]
        result = create_optimized_search_input(queries)

        # Cost-saving settings
        assert result["maxImages"] == 0
        assert result["maxReviews"] == 0
        assert result["scrapeContacts"] is False
        assert result["scrapeReviewsPersonalData"] is False
        assert result["scrapePlaceDetailPage"] is False


class TestTransformGmapsResult:
    """Test transformation of Apify output to our schema"""

    def test_transforms_basic_result(self):
        """Should transform basic Google Maps result"""
        raw_data = {
            "title": "Pak Wayan Pool Service",
            "totalScore": 4.8,
            "reviewsCount": 67,
            "street": "Jl. Pantai Berawa",
            "city": "Canggu",
            "state": "Bali",
            "countryCode": "ID",
            "website": "https://pakwayanpool.com",
            "phone": "+62361234567",
            "categoryName": "Swimming pool contractor",
            "latitude": -8.123456,
            "longitude": 115.123456,
            "url": "https://www.google.com/maps/search/?api=1&query_place_id=ChIJtest123",
        }

        result = transform_gmaps_result(raw_data)

        assert result["business_name"] == "Pak Wayan Pool Service"
        assert result["source_tier"] == "google_maps"
        assert result["phone"] == "+62361234567"
        assert result["website"] == "https://pakwayanpool.com"
        assert result["location"] == "Canggu"
        assert result["gmaps_rating"] == 4.8
        assert result["gmaps_review_count"] == 67
        assert result["gmaps_place_id"] == "ChIJtest123"
        assert result["is_active"] is True

    def test_extracts_place_id_from_url(self):
        """Should extract place ID from Google Maps URL"""
        raw_data = {
            "title": "Test Business",
            "url": "https://www.google.com/maps/search/?api=1&query_place_id=ChIJN1t_tDetest&foo=bar",
        }

        result = transform_gmaps_result(raw_data)
        assert result["gmaps_place_id"] == "ChIJN1t_tDetest"

    def test_builds_full_address(self):
        """Should combine address components"""
        raw_data = {
            "title": "Test",
            "street": "Jl. Sunset Road 88",
            "city": "Seminyak",
            "state": "Bali",
        }

        result = transform_gmaps_result(raw_data)
        assert result["address"] == "Jl. Sunset Road 88, Seminyak, Bali"

    def test_handles_missing_fields(self):
        """Should handle missing optional fields gracefully"""
        raw_data = {
            "title": "Minimal Data Business",
            "totalScore": 4.5,
        }

        result = transform_gmaps_result(raw_data)

        assert result["business_name"] == "Minimal Data Business"
        assert result["gmaps_rating"] == 4.5
        assert result["phone"] is None
        assert result["website"] is None
        assert result["gmaps_place_id"] is None
        assert result["location"] == "Bali"  # Default fallback

    def test_infers_specializations_from_category(self):
        """Should infer specializations from category"""
        raw_data = {
            "title": "Test Pool Service",
            "categoryName": "Swimming pool contractor",
        }

        result = transform_gmaps_result(raw_data)
        assert "pool" in result["specializations"]


class TestInferSpecializations:
    """Test specialization inference from business data"""

    def test_detects_pool_keywords(self):
        """Should detect pool-related specializations"""
        assert "pool" in infer_specializations("Swimming pool contractor", "Bali Pool Service")
        assert "pool" in infer_specializations("construction", "Kolam Renang Builder")

    def test_detects_bathroom_keywords(self):
        """Should detect bathroom-related specializations"""
        assert "bathroom" in infer_specializations("Plumber", "Bathroom Renovation")
        assert "bathroom" in infer_specializations("contractor", "Kamar Mandi Expert")

    def test_detects_kitchen_keywords(self):
        """Should detect kitchen-related specializations"""
        assert "kitchen" in infer_specializations("Kitchen remodeling", "")
        assert "kitchen" in infer_specializations("", "Dapur Renovation")

    def test_detects_general_construction(self):
        """Should detect general construction work"""
        assert "general" in infer_specializations("General contractor", "")
        assert "general" in infer_specializations("", "Tukang Bangunan Bali")
        assert "general" in infer_specializations("Builder", "Construction Company")

    def test_handles_multiple_specializations(self):
        """Should detect multiple specializations"""
        specs = infer_specializations(
            "General contractor",
            "Pool and Bathroom Renovation"
        )
        assert "pool" in specs
        assert "bathroom" in specs
        assert "general" in specs

    def test_defaults_to_general(self):
        """Should default to general if no specific match"""
        specs = infer_specializations("Restaurant", "Coffee Shop")
        assert specs == ["general"]


class TestScrapeGoogleMapsWorkers:
    """Test main scraping function with mocked Apify client"""

    @pytest.mark.asyncio
    async def test_invalid_project_type_raises_error(self):
        """Should raise ValueError for invalid project type"""
        with pytest.raises(ValueError, match="Invalid project_type"):
            await scrape_google_maps_workers(project_type="invalid_type")

    @pytest.mark.asyncio
    @patch("app.integrations.google_maps_scraper.get_apify_client")
    @patch("app.integrations.google_maps_scraper.save_scrape_job")
    @patch("app.integrations.google_maps_scraper.update_scrape_job_status")
    async def test_successful_scrape_flow(
        self,
        mock_update_job,
        mock_save_job,
        mock_get_client,
    ):
        """Should complete full scrape workflow successfully"""
        # Mock job ID
        mock_save_job.return_value = "test-job-id"

        # Mock Apify client
        mock_client = MagicMock()
        mock_actor = MagicMock()
        mock_run = {
            "id": "apify-run-123",
            "defaultDatasetId": "dataset-456",
        }
        mock_actor.call.return_value = mock_run

        # Mock dataset with sample results
        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = [
            {
                "title": "Pak Wayan Pool Service",
                "totalScore": 4.8,
                "reviewsCount": 67,
                "city": "Canggu",
                "categoryName": "Swimming pool contractor",
                "phone": "+62361234567",
                "website": "https://pakwayanpool.com",
            },
            {
                "title": "Bali Pool Builders",
                "totalScore": 4.5,
                "reviewsCount": 32,
                "city": "Seminyak",
                "categoryName": "Construction company",
            },
        ]

        mock_client.actor.return_value = mock_actor
        mock_client.dataset.return_value = mock_dataset
        mock_get_client.return_value = mock_client

        # Execute scrape
        results = await scrape_google_maps_workers(
            project_type="pool",
            max_results_per_search=20,
        )

        # Verify job creation
        mock_save_job.assert_called_once()
        call_kwargs = mock_save_job.call_args[1]
        assert call_kwargs["job_type"] == "worker_discovery"
        assert call_kwargs["apify_actor_id"] == "compass/crawler-google-places"
        assert call_kwargs["estimated_cost_usd"] > 0

        # Verify Apify actor called
        mock_actor.call.assert_called_once()

        # Verify job status updates
        assert mock_update_job.call_count == 2  # running + completed

        # Verify results
        assert len(results) == 2
        assert results[0]["business_name"] == "Pak Wayan Pool Service"
        assert results[0]["source_tier"] == "google_maps"
        assert results[1]["business_name"] == "Bali Pool Builders"

    @pytest.mark.asyncio
    @patch("app.integrations.google_maps_scraper.get_apify_client")
    @patch("app.integrations.google_maps_scraper.save_scrape_job")
    @patch("app.integrations.google_maps_scraper.update_scrape_job_status")
    async def test_handles_scrape_failure(
        self,
        mock_update_job,
        mock_save_job,
        mock_get_client,
    ):
        """Should handle Apify failures gracefully (with retry attempts)"""
        mock_save_job.return_value = "test-job-id"

        # Mock Apify client to raise error
        mock_client = MagicMock()
        mock_client.actor.side_effect = Exception("Apify API error")
        mock_get_client.return_value = mock_client

        # Execute scrape (should raise after retries)
        with pytest.raises(Exception, match="Apify API error"):
            await scrape_google_maps_workers(project_type="pool")

        # Verify job marked as failed (called 3 times due to retry decorator)
        assert mock_update_job.call_count == 3  # 3 retry attempts

        # Check the final failure call
        final_call_kwargs = mock_update_job.call_args_list[-1][1]
        assert final_call_kwargs["status"] == "failed"
        assert "Apify API error" in final_call_kwargs["error_message"]

    @pytest.mark.asyncio
    @patch("app.integrations.google_maps_scraper.get_apify_client")
    @patch("app.integrations.google_maps_scraper.save_scrape_job")
    @patch("app.integrations.google_maps_scraper.update_scrape_job_status")
    async def test_uses_correct_search_queries_per_type(
        self,
        mock_update_job,
        mock_save_job,
        mock_get_client,
    ):
        """Should use appropriate search queries for each project type"""
        mock_save_job.return_value = "test-job-id"

        # Mock Apify client
        mock_client = MagicMock()
        mock_actor = MagicMock()
        mock_run = {"id": "run-123", "defaultDatasetId": "dataset-456"}
        mock_actor.call.return_value = mock_run
        mock_dataset = MagicMock()
        mock_dataset.iterate_items.return_value = []
        mock_client.actor.return_value = mock_actor
        mock_client.dataset.return_value = mock_dataset
        mock_get_client.return_value = mock_client

        # Test pool queries
        await scrape_google_maps_workers(project_type="pool")
        actor_input = mock_actor.call.call_args[1]["run_input"]
        search_queries = actor_input["searchStringsArray"]
        assert any("pool" in q.lower() or "kolam" in q.lower() for q in search_queries)

        # Test bathroom queries
        await scrape_google_maps_workers(project_type="bathroom")
        actor_input = mock_actor.call.call_args[1]["run_input"]
        search_queries = actor_input["searchStringsArray"]
        assert any("bathroom" in q.lower() or "kamar mandi" in q.lower() for q in search_queries)

    def test_cost_estimation(self):
        """Should estimate costs correctly"""
        # 3 queries × 20 results × $0.004 = $0.24
        queries = ["Query 1", "Query 2", "Query 3"]
        input_config = create_optimized_search_input(queries, max_results=20)

        num_queries = len(input_config["searchStringsArray"])
        max_results = input_config["maxCrawledPlacesPerSearch"]
        estimated_cost = num_queries * max_results * 0.004

        assert estimated_cost == pytest.approx(0.24)
