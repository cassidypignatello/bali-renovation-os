/**
 * React hook for fetching worker details
 */

import { useState, useEffect, useCallback } from "react";
import { workersApi } from "../api";
import type { WorkerPreview, WorkerFullDetails } from "../types";

interface UseWorkerDetailsOptions {
  workerId: string | null;
  fetchFull?: boolean;
}

interface UseWorkerDetailsResult {
  preview: WorkerPreview | null;
  fullDetails: WorkerFullDetails | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useWorkerDetails({
  workerId,
  fetchFull = false,
}: UseWorkerDetailsOptions): UseWorkerDetailsResult {
  const [preview, setPreview] = useState<WorkerPreview | null>(null);
  const [fullDetails, setFullDetails] = useState<WorkerFullDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!workerId) return;

    setLoading(true);
    setError(null);

    if (fetchFull) {
      const response = await workersApi.getDetails(workerId);
      if (response.error) {
        setError(response.error.message);
      } else if (response.data) {
        setFullDetails(response.data);
      }
    } else {
      const response = await workersApi.getPreview(workerId);
      if (response.error) {
        setError(response.error.message);
      } else if (response.data) {
        setPreview(response.data);
      }
    }

    setLoading(false);
  }, [workerId, fetchFull]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { preview, fullDetails, loading, error, refetch: fetchData };
}
