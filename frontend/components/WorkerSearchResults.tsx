'use client';

import { TrustLevel, type WorkerPreview } from '@/lib/types';

interface WorkerSearchResultsProps {
  workers: WorkerPreview[];
  unlockPriceIdr: number;
  onUnlockWorker?: (workerId: string) => void;
}

const TRUST_LEVEL_COLORS: Record<TrustLevel, string> = {
  [TrustLevel.VERIFIED]: 'bg-green-100 text-green-800',
  [TrustLevel.HIGH]: 'bg-blue-100 text-blue-800',
  [TrustLevel.MEDIUM]: 'bg-yellow-100 text-yellow-800',
  [TrustLevel.LOW]: 'bg-gray-100 text-gray-800',
};

export function WorkerSearchResults({
  workers,
  unlockPriceIdr,
  onUnlockWorker,
}: WorkerSearchResultsProps) {
  if (workers.length === 0) {
    return null;
  }

  const formatPrice = (priceIdr: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(priceIdr);
  };

  return (
    <div className="mt-8 space-y-4">
      <h3 className="text-xl font-semibold text-gray-900">Search Results</h3>

      {workers.map((worker) => (
        <div
          key={worker.id}
          className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
        >
          <div className="flex justify-between items-start mb-4">
            <div className="flex-1">
              <h4 className="text-lg font-semibold text-gray-900">
                {worker.preview_name}
              </h4>
              <p className="text-sm text-gray-600 mt-1">
                {worker.location}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 rounded-full text-xs font-semibold ${
                  TRUST_LEVEL_COLORS[worker.trust_score.trust_level]
                }`}
              >
                {worker.trust_score.trust_level}
              </span>
              <span className="text-lg font-bold text-gray-900">
                {worker.trust_score.total_score}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mb-4">
            {worker.specializations.map((spec, idx) => (
              <span
                key={idx}
                className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded"
              >
                {spec}
              </span>
            ))}
          </div>

          {worker.preview_review && (
            <div className="mb-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-700 italic">
                &quot;{worker.preview_review}&quot;
              </p>
            </div>
          )}

          <div className="flex items-center justify-between text-sm text-gray-600">
            <div className="flex gap-4">
              {worker.trust_score.review_count > 0 && (
                <span>
                  ⭐ {worker.trust_score.rating?.toFixed(1)} ({worker.trust_score.review_count} reviews)
                </span>
              )}
              {worker.photos_count > 0 && (
                <span>
                  📷 {worker.photos_count} photos
                </span>
              )}
              {worker.price_idr_per_day && (
                <span>
                  💰 {formatPrice(worker.price_idr_per_day)}/day
                </span>
              )}
            </div>

            {worker.contact_locked && (
              <button
                onClick={() => onUnlockWorker?.(worker.id)}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
              >
                Unlock Contact - {formatPrice(worker.unlock_price_idr)}
              </button>
            )}
          </div>

          {worker.opening_hours && (
            <div className="mt-3 text-sm text-gray-600">
              🕐 {worker.opening_hours}
            </div>
          )}
        </div>
      ))}

      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <p>
          💡 <strong>Unlock contacts</strong> to get full business details, phone numbers,
          and AI-powered negotiation tips for {formatPrice(unlockPriceIdr)} per worker.
        </p>
      </div>
    </div>
  );
}
