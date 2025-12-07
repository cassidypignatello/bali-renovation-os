/**
 * React hook for payment and unlock functionality
 */

import { useState } from "react";
import { paymentsApi } from "../api";
import type { UnlockRequest, UnlockResponse, PaymentMethod } from "../types";

interface UsePaymentResult {
  unlockResponse: UnlockResponse | null;
  loading: boolean;
  error: string | null;
  initiateUnlock: (
    workerId: string,
    paymentMethod: PaymentMethod
  ) => Promise<void>;
  checkUnlockStatus: (workerId: string) => Promise<boolean>;
  reset: () => void;
}

export function usePayment(): UsePaymentResult {
  const [unlockResponse, setUnlockResponse] = useState<UnlockResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const initiateUnlock = async (
    workerId: string,
    paymentMethod: PaymentMethod
  ) => {
    setLoading(true);
    setError(null);

    const returnUrl = `${window.location.origin}/workers/${workerId}`;

    const request: UnlockRequest = {
      worker_id: workerId,
      payment_method: paymentMethod,
      return_url: returnUrl,
    };

    const response = await paymentsApi.unlockWorker(request);

    if (response.error) {
      setError(response.error.message);
      setUnlockResponse(null);
    } else if (response.data) {
      setUnlockResponse(response.data);
      // Redirect to payment URL
      window.location.href = response.data.payment_url;
    }

    setLoading(false);
  };

  const checkUnlockStatus = async (workerId: string): Promise<boolean> => {
    const response = await paymentsApi.checkUnlockStatus(workerId);
    return response.data?.unlocked ?? false;
  };

  const reset = () => {
    setUnlockResponse(null);
    setError(null);
    setLoading(false);
  };

  return {
    unlockResponse,
    loading,
    error,
    initiateUnlock,
    checkUnlockStatus,
    reset,
  };
}
