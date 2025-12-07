'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { workersApi } from '@/lib/api';
import { usePayment } from '@/lib/hooks';
import { UnlockedWorkerDetails } from '@/components/UnlockedWorkerDetails';
import type { WorkerFullDetails } from '@/lib/types';

export default function WorkerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const workerId = params.id as string;

  const { checkUnlockStatus } = usePayment();
  const [worker, setWorker] = useState<WorkerFullDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUnlocked, setIsUnlocked] = useState(false);

  useEffect(() => {
    const loadWorkerDetails = async () => {
      setLoading(true);
      setError(null);

      // Check unlock status first
      const unlocked = await checkUnlockStatus(workerId);
      setIsUnlocked(unlocked);

      if (!unlocked) {
        setError('This worker has not been unlocked yet. Please complete payment to view details.');
        setLoading(false);
        return;
      }

      // Fetch full worker details
      const response = await workersApi.getDetails(workerId);

      if (response.error) {
        setError(response.error.message);
        setWorker(null);
      } else if (response.data) {
        setWorker(response.data);
        setError(null);
      }

      setLoading(false);
    };

    if (workerId) {
      loadWorkerDetails();
    }
  }, [workerId, checkUnlockStatus]);

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="animate-pulse">
              <div className="h-8 bg-gray-200 rounded w-3/4 mb-4" />
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-8" />
              <div className="space-y-4">
                <div className="h-4 bg-gray-200 rounded" />
                <div className="h-4 bg-gray-200 rounded w-5/6" />
                <div className="h-4 bg-gray-200 rounded w-4/6" />
              </div>
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (error || !isUnlocked) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <div className="text-center">
              <h1 className="text-2xl font-bold text-gray-900 mb-4">
                Access Restricted
              </h1>
              <p className="text-gray-600 mb-6">
                {error || 'This worker has not been unlocked yet.'}
              </p>
              <button
                onClick={() => router.push('/')}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
              >
                Return to Search
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  if (!worker) {
    return (
      <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
        <div className="max-w-4xl mx-auto px-4 py-12">
          <div className="bg-white rounded-lg shadow-lg p-8">
            <p className="text-center text-gray-600">Worker not found.</p>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <div className="max-w-4xl mx-auto px-4 py-12">
        {/* Back Button */}
        <button
          onClick={() => router.push('/')}
          className="mb-6 px-4 py-2 text-blue-600 hover:text-blue-700 font-semibold flex items-center gap-2"
        >
          ← Back to Search
        </button>

        <UnlockedWorkerDetails worker={worker} />
      </div>
    </main>
  );
}
