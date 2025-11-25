"""
Apify client for Tokopedia product scraping
"""

from functools import lru_cache

from apify_client import ApifyClient
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings


@lru_cache
def get_apify_client() -> ApifyClient:
    """
    Get singleton Apify client instance

    Returns:
        ApifyClient: Configured Apify client
    """
    settings = get_settings()
    return ApifyClient(settings.apify_token)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
async def scrape_tokopedia_prices(
    material_name: str, max_results: int = 5
) -> list[dict]:
    """
    Scrape material prices from Tokopedia using Apify

    Uses retry logic for resilience against scraping failures.

    Args:
        material_name: Material to search for
        max_results: Maximum number of results to return

    Returns:
        list[dict]: Product listings with prices
            [
                {
                    "name": "Product name",
                    "price_idr": 150000,
                    "url": "https://tokopedia.com/...",
                    "seller": "Seller name",
                    "rating": 4.8,
                    "sold_count": 150
                }
            ]

    Raises:
        Exception: If scraping fails after retries
    """
    client = get_apify_client()

    # Configure scraping task for Tokopedia
    run_input = {
        "keyword": material_name,
        "maxItems": max_results,
        "proxyConfiguration": {"useApifyProxy": True},
    }

    try:
        # Run Tokopedia scraper actor
        # Note: Replace 'your-actor-id' with actual Tokopedia scraper actor ID
        run = client.actor("your-actor-id").call(run_input=run_input)

        # Fetch results from dataset
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(
                {
                    "name": item.get("name", ""),
                    "price_idr": item.get("price", 0),
                    "url": item.get("url", ""),
                    "seller": item.get("shop", {}).get("name", ""),
                    "rating": item.get("rating", 0.0),
                    "sold_count": item.get("sold", 0),
                }
            )

        return results

    except Exception as e:
        raise Exception(f"Tokopedia scraping failed for '{material_name}': {e}")


async def scrape_multiple_materials(materials: list[str]) -> dict[str, list[dict]]:
    """
    Scrape prices for multiple materials

    Args:
        materials: List of material names to search

    Returns:
        dict: Material name -> list of products
    """
    results = {}

    for material in materials:
        try:
            products = await scrape_tokopedia_prices(material, max_results=3)
            results[material] = products
        except Exception as e:
            # Log error but continue with other materials
            results[material] = []
            print(f"Scraping failed for {material}: {e}")

    return results


def calculate_median_price(products: list[dict]) -> int:
    """
    Calculate median price from scraped products

    Args:
        products: List of product dictionaries with 'price_idr' key

    Returns:
        int: Median price in IDR, or 0 if no products
    """
    if not products:
        return 0

    prices = sorted([p["price_idr"] for p in products if p.get("price_idr", 0) > 0])

    if not prices:
        return 0

    mid = len(prices) // 2
    if len(prices) % 2 == 0:
        return (prices[mid - 1] + prices[mid]) // 2
    else:
        return prices[mid]
