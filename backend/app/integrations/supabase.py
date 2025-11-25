"""
Async Supabase client for database operations
"""

from functools import lru_cache

from supabase import create_client, Client

from app.config import get_settings


@lru_cache
def get_supabase_client() -> Client:
    """
    Get singleton Supabase client instance

    Returns:
        Client: Configured Supabase client with service key
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


async def save_estimate(estimate_data: dict) -> dict:
    """
    Save cost estimate to database

    Args:
        estimate_data: Estimate data dictionary

    Returns:
        dict: Saved estimate with database ID

    Raises:
        Exception: If database operation fails
    """
    supabase = get_supabase_client()
    response = supabase.table("estimates").insert(estimate_data).execute()
    return response.data[0] if response.data else {}


async def get_estimate(estimate_id: str) -> dict | None:
    """
    Retrieve estimate by ID

    Args:
        estimate_id: Unique estimate identifier

    Returns:
        dict | None: Estimate data or None if not found
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("estimates").select("*").eq("estimate_id", estimate_id).execute()
    )
    return response.data[0] if response.data else None


async def update_estimate_status(estimate_id: str, status: str, **kwargs) -> None:
    """
    Update estimate status and optional fields

    Args:
        estimate_id: Estimate to update
        status: New status value
        **kwargs: Additional fields to update
    """
    supabase = get_supabase_client()
    update_data = {"status": status, **kwargs}
    supabase.table("estimates").update(update_data).eq("estimate_id", estimate_id).execute()


async def get_material_price_history(material_name: str, limit: int = 10) -> list[dict]:
    """
    Get historical pricing for a material from cache

    Args:
        material_name: Material name to search
        limit: Maximum number of results

    Returns:
        list[dict]: Historical price entries
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("material_prices")
        .select("*")
        .ilike("material_name", f"%{material_name}%")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data if response.data else []


async def save_material_price(price_data: dict) -> None:
    """
    Cache material price for future lookups

    Args:
        price_data: Material price data to cache
    """
    supabase = get_supabase_client()
    supabase.table("material_prices").insert(price_data).execute()


async def get_worker_by_id(worker_id: str) -> dict | None:
    """
    Get worker details by ID

    Args:
        worker_id: Worker identifier

    Returns:
        dict | None: Worker data or None if not found
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("workers").select("*").eq("worker_id", worker_id).execute()
    )
    return response.data[0] if response.data else None


async def get_workers_for_project(project_type: str, limit: int = 20) -> list[dict]:
    """
    Get recommended workers for project type

    Args:
        project_type: Type of construction project
        limit: Maximum number of workers

    Returns:
        list[dict]: Worker recommendations
    """
    supabase = get_supabase_client()
    response = (
        supabase.table("workers")
        .select("*")
        .contains("specializations", [project_type])
        .order("trust_score", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data if response.data else []


async def save_transaction(transaction_data: dict) -> dict:
    """
    Save payment transaction

    Args:
        transaction_data: Transaction details

    Returns:
        dict: Saved transaction with ID
    """
    supabase = get_supabase_client()
    response = supabase.table("transactions").insert(transaction_data).execute()
    return response.data[0] if response.data else {}


async def update_transaction_status(transaction_id: str, status: str, **kwargs) -> None:
    """
    Update transaction status

    Args:
        transaction_id: Transaction to update
        status: New payment status
        **kwargs: Additional fields
    """
    supabase = get_supabase_client()
    update_data = {"status": status, **kwargs}
    supabase.table("transactions").update(update_data).eq("transaction_id", transaction_id).execute()
