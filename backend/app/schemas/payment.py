"""
Payment and transaction schemas for Midtrans integration
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    """Payment transaction status"""

    PENDING = "pending"
    SETTLEMENT = "settlement"
    CAPTURE = "capture"
    DENY = "deny"
    CANCEL = "cancel"
    EXPIRE = "expire"
    FAILURE = "failure"


class PaymentMethod(str, Enum):
    """Supported payment methods"""

    CREDIT_CARD = "credit_card"
    BANK_TRANSFER = "bank_transfer"
    GOPAY = "gopay"
    QRIS = "qris"


class UnlockRequest(BaseModel):
    """
    Request to unlock worker details via payment

    Attributes:
        worker_id: Worker to unlock
        payment_method: Preferred payment method
        return_url: URL to redirect after payment
    """

    worker_id: str = Field(..., description="Worker ID to unlock")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    return_url: str = Field(..., description="Return URL after payment")

    class Config:
        json_schema_extra = {
            "example": {
                "worker_id": "wrk_abc123",
                "payment_method": "gopay",
                "return_url": "https://app.example.com/workers/wrk_abc123",
            }
        }


class UnlockResponse(BaseModel):
    """
    Response after initiating payment for worker unlock

    Attributes:
        transaction_id: Unique transaction identifier
        payment_url: URL to complete payment
        amount_idr: Payment amount in IDR
        expires_at: Payment link expiration
    """

    transaction_id: str = Field(..., description="Transaction ID")
    payment_url: str = Field(..., description="Payment URL")
    amount_idr: int = Field(..., ge=0, description="Amount in IDR")
    expires_at: datetime = Field(..., description="Payment expiration")


class MidtransWebhook(BaseModel):
    """
    Midtrans payment webhook notification

    Attributes:
        transaction_status: Payment status from Midtrans
        order_id: Order identifier
        gross_amount: Transaction amount
        payment_type: Payment method used
        transaction_id: Midtrans transaction ID
        signature_key: SHA512 signature for verification
        fraud_status: Fraud detection status
        status_code: HTTP status code from Midtrans
    """

    transaction_status: str = Field(..., description="Transaction status")
    order_id: str = Field(..., description="Order ID")
    gross_amount: str = Field(..., description="Transaction amount")
    payment_type: str = Field(..., description="Payment method")
    transaction_id: str = Field(..., description="Midtrans transaction ID")
    signature_key: str = Field(..., description="SHA512 signature")
    fraud_status: str | None = Field(None, description="Fraud detection status")
    status_code: str = Field(..., description="Status code")

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_status": "settlement",
                "order_id": "ORDER-123456",
                "gross_amount": "50000.00",
                "payment_type": "gopay",
                "transaction_id": "abc-123-def",
                "signature_key": "abc123...",
                "fraud_status": "accept",
                "status_code": "200",
            }
        }
