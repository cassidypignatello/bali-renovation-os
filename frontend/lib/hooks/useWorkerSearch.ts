/**
 * React hook for worker search functionality
 */

import { useState } from "react";
import { workersApi } from "../api";
import type { WorkerSearchRequest, WorkerSearchResponse } from "../types";

interface UseWorkerSearchResult {
  data: WorkerSearchResponse | null;
  loading: boolean;
  error: string | null;
  search: (request: WorkerSearchRequest) => Promise<void>;
  reset: () => void;
}

export function useWorkerSearch(): UseWorkerSearchResult {
  const [data, setData] = useState<WorkerSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = async (request: WorkerSearchRequest) => {
    setLoading(true);
    setError(null);

    const response = await workersApi.search(request);

    if (response.error) {
      setError(response.error.message);
      setData(null);
    } else if (response.data) {
      setData(response.data);
      setError(null);
    }

    setLoading(false);
  };

  const reset = () => {
    setData(null);
    setError(null);
    setLoading(false);
  };

  return { data, loading, error, search, reset };
}
