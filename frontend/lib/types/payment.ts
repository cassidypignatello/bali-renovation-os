/**
 * Payment and transaction types matching backend schemas
 * Maps to backend/app/schemas/payment.py
 */

export enum PaymentStatus {
  PENDING = "pending",
  SETTLEMENT = "settlement",
  CAPTURE = "capture",
  DENY = "deny",
  CANCEL = "cancel",
  EXPIRE = "expire",
  FAILURE = "failure",
}

export enum PaymentMethod {
  CREDIT_CARD = "credit_card",
  BANK_TRANSFER = "bank_transfer",
  GOPAY = "gopay",
  QRIS = "qris",
}

export interface UnlockRequest {
  worker_id: string;
  payment_method: PaymentMethod;
  return_url: string;
}

export interface UnlockResponse {
  transaction_id: string;
  payment_url: string;
  amount_idr: number;
  expires_at: string;
}

export interface MidtransWebhook {
  transaction_status: string;
  order_id: string;
  gross_amount: string;
  payment_type: string;
  transaction_id: string;
  signature_key: string;
  fraud_status: string | null;
  status_code: string;
}
