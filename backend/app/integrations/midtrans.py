"""
Midtrans payment gateway integration with webhook verification
"""

import hashlib
import uuid
from functools import lru_cache

import midtransclient

from app.config import get_settings


@lru_cache
def get_snap_client() -> midtransclient.Snap:
    """
    Get Midtrans Snap client for payment page generation

    Returns:
        midtransclient.Snap: Configured Snap client
    """
    settings = get_settings()
    snap = midtransclient.Snap(
        is_production=settings.env == "production",
        server_key=settings.midtrans_server_key,
        client_key=settings.midtrans_client_key,
    )
    return snap


def verify_signature(
    order_id: str, status_code: str, gross_amount: str, signature: str, server_key: str
) -> bool:
    """
    Verify Midtrans webhook signature using SHA512

    Args:
        order_id: Order identifier
        status_code: Transaction status code
        gross_amount: Transaction amount
        signature: Signature from webhook
        server_key: Midtrans server key

    Returns:
        bool: True if signature is valid
    """
    raw_string = f"{order_id}{status_code}{gross_amount}{server_key}"
    expected_signature = hashlib.sha512(raw_string.encode()).hexdigest()
    return signature == expected_signature


async def create_payment_transaction(
    worker_id: str, amount_idr: int, payment_method: str, return_url: str
) -> dict:
    """
    Create Midtrans payment transaction for worker unlock

    Args:
        worker_id: Worker being unlocked
        amount_idr: Payment amount in IDR
        payment_method: Payment method to enable
        return_url: URL to redirect after payment

    Returns:
        dict: Transaction details with payment URL
            {
                "transaction_id": "TRX-123456",
                "payment_url": "https://app.midtrans.com/snap/v2/...",
                "amount_idr": 50000,
                "expires_at": "2025-11-25T18:00:00Z"
            }

    Raises:
        Exception: If transaction creation fails
    """
    snap = get_snap_client()

    transaction_id = f"TRX-{uuid.uuid4().hex[:12].upper()}"
    order_id = f"UNLOCK-{worker_id}-{uuid.uuid4().hex[:8]}"

    # Build transaction parameters
    transaction_details = {
        "order_id": order_id,
        "gross_amount": amount_idr,
    }

    item_details = [
        {
            "id": worker_id,
            "name": "Worker Details Unlock",
            "price": amount_idr,
            "quantity": 1,
        }
    ]

    # Enable specific payment methods
    enabled_payments = []
    if payment_method == "credit_card":
        enabled_payments.extend(["credit_card", "debit_card"])
    elif payment_method == "bank_transfer":
        enabled_payments.extend(["bank_transfer", "bca_va", "bni_va", "bri_va"])
    elif payment_method == "gopay":
        enabled_payments.append("gopay")
    elif payment_method == "qris":
        enabled_payments.append("qris")

    transaction_data = {
        "transaction_details": transaction_details,
        "item_details": item_details,
        "enabled_payments": enabled_payments,
        "callbacks": {
            "finish": return_url,
        },
    }

    try:
        response = snap.create_transaction(transaction_data)

        return {
            "transaction_id": transaction_id,
            "order_id": order_id,
            "payment_url": response["redirect_url"],
            "token": response["token"],
            "amount_idr": amount_idr,
        }

    except Exception as e:
        raise Exception(f"Failed to create Midtrans transaction: {e}")


async def check_transaction_status(order_id: str) -> dict:
    """
    Check transaction status with Midtrans

    Args:
        order_id: Order ID to check

    Returns:
        dict: Transaction status details
    """
    snap = get_snap_client()

    try:
        status = snap.transactions.status(order_id)
        return {
            "order_id": order_id,
            "transaction_status": status.get("transaction_status"),
            "payment_type": status.get("payment_type"),
            "gross_amount": status.get("gross_amount"),
            "fraud_status": status.get("fraud_status"),
        }

    except Exception as e:
        raise Exception(f"Failed to check transaction status: {e}")
