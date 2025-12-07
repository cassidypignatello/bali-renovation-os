/**
 * Payment and unlock API methods
 */

import { apiClient } from "./client";
import type {
  UnlockRequest,
  UnlockResponse,
  ApiResponse,
} from "../types";

export const paymentsApi = {
  /**
   * Initiate payment to unlock worker details
   * POST /unlock
   */
  unlockWorker: async (
    request: UnlockRequest
  ): Promise<ApiResponse<UnlockResponse>> => {
    return apiClient.post<UnlockResponse, UnlockRequest>("/unlock", request);
  },

  /**
   * Check if user has already unlocked a worker
   * GET /unlock/status?worker_id={workerId}
   */
  checkUnlockStatus: async (
    workerId: string
  ): Promise<ApiResponse<{ unlocked: boolean; unlocked_at?: string }>> => {
    return apiClient.get(`/unlock/status`, { worker_id: workerId });
  },
};
