"""
Tokopedia Affiliate Link Utilities

Appends affiliate tracking parameters to product URLs for revenue generation.
The affiliate ID is loaded from the TOKOPEDIA_AFFILIATE_ID environment variable.
"""

from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from app.config import get_settings

# Allowed Tokopedia domains for affiliate link generation
TOKOPEDIA_DOMAINS = frozenset({"tokopedia.com", "tokopedia.co.id"})


def _is_valid_tokopedia_hostname(hostname: str | None) -> bool:
    """
    Check if hostname is a valid Tokopedia domain or subdomain.

    Args:
        hostname: The hostname to validate (e.g., 'www.tokopedia.com')

    Returns:
        True if hostname is tokopedia.com, tokopedia.co.id, or a subdomain thereof
    """
    if not hostname:
        return False

    hostname = hostname.lower()

    for domain in TOKOPEDIA_DOMAINS:
        if hostname == domain or hostname.endswith(f".{domain}"):
            return True

    return False


def generate_affiliate_url(product_url: str | None) -> str | None:
    """
    Append Tokopedia affiliate tracking parameter to a product URL.

    Args:
        product_url: Original Tokopedia product URL (or None)

    Returns:
        URL with affiliate ID appended as query parameter, or:
        - None if product_url is None or empty
        - Original product_url (unchanged) if affiliate ID is not configured
        - Original product_url (unchanged) if URL is not a valid Tokopedia domain

    Example:
        >>> generate_affiliate_url("https://www.tokopedia.com/shop/product-slug")
        "https://www.tokopedia.com/shop/product-slug?extParam=ivf%3Dfalse%26src%3Daffiliate%26aff_id%3DYOUR_AFF_ID"
    """
    if not product_url:
        return None

    settings = get_settings()
    affiliate_id = settings.tokopedia_affiliate_id

    if not affiliate_id:
        # No affiliate ID configured - return original URL
        return product_url

    # Validate it's a Tokopedia URL with strict hostname check
    parsed = urlparse(product_url)
    if not _is_valid_tokopedia_hostname(parsed.hostname):
        # Not a valid Tokopedia URL - return as-is
        return product_url

    # Parse existing query parameters
    existing_params = parse_qs(parsed.query)

    # URL-encode affiliate ID to prevent injection of special characters
    encoded_affiliate_id = quote(affiliate_id, safe="")

    # Build the affiliate extParam following Tokopedia's affiliate format
    # Format: extParam=ivf%3Dfalse%26src%3Daffiliate%26aff_id%3D{AFFILIATE_ID}
    aff_param = f"ivf=false&src=affiliate&aff_id={encoded_affiliate_id}"

    # Add or update extParam
    existing_params["extParam"] = [aff_param]

    # Rebuild URL with affiliate tracking
    new_query = urlencode(existing_params, doseq=True)
    affiliate_url = urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )

    return affiliate_url


def batch_generate_affiliate_urls(
    product_urls: list[str | None],
) -> list[str | None]:
    """
    Generate affiliate URLs for a batch of product URLs.

    Args:
        product_urls: List of original product URLs (may contain None values)

    Returns:
        List of affiliate URLs with same length as input
    """
    return [generate_affiliate_url(url) for url in product_urls]
