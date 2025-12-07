'use client';

import { useState } from 'react';
import { TrustLevel, type WorkerFullDetails } from '@/lib/types';

interface UnlockedWorkerDetailsProps {
  worker: WorkerFullDetails;
}

const TRUST_LEVEL_COLORS: Record<TrustLevel, string> = {
  [TrustLevel.VERIFIED]: 'bg-green-100 text-green-800',
  [TrustLevel.HIGH]: 'bg-blue-100 text-blue-800',
  [TrustLevel.MEDIUM]: 'bg-yellow-100 text-yellow-800',
  [TrustLevel.LOW]: 'bg-gray-100 text-gray-800',
};

export function UnlockedWorkerDetails({ worker }: UnlockedWorkerDetailsProps) {
  const [copiedScript, setCopiedScript] = useState(false);

  const formatPrice = (priceIdr: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(priceIdr);
  };

  const handleWhatsAppClick = () => {
    if (worker.contact.whatsapp) {
      const phoneNumber = worker.contact.whatsapp.replace(/\D/g, '');
      const message = encodeURIComponent(
        `Halo ${worker.business_name}, saya tertarik dengan layanan ${worker.specializations[0]} untuk proyek renovasi saya.`
      );
      window.open(`https://wa.me/${phoneNumber}?text=${message}`, '_blank');
    }
  };

  const copyNegotiationScript = () => {
    if (worker.negotiation_script) {
      navigator.clipboard.writeText(worker.negotiation_script);
      setCopiedScript(true);
      setTimeout(() => setCopiedScript(false), 2000);
    }
  };

  const formatPhoneNumber = (phone: string | null) => {
    if (!phone) return null;
    // Format Indonesian phone number: +62 812-3456-7890
    const cleaned = phone.replace(/\D/g, '');
    if (cleaned.startsWith('62')) {
      return `+62 ${cleaned.slice(2, 5)}-${cleaned.slice(5, 9)}-${cleaned.slice(9)}`;
    }
    return phone;
  };

  return (
    <div className="space-y-6">
      {/* Success Banner */}
      <div className="bg-green-50 border border-green-200 rounded-lg p-4">
        <p className="text-green-800 font-semibold">
          ✅ Contact details unlocked! You can now reach out to {worker.business_name}.
        </p>
        <p className="text-sm text-green-700 mt-1">
          Unlocked on {new Date(worker.unlocked_at).toLocaleDateString('id-ID', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
          })}
        </p>
      </div>

      {/* Business Info Header */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 mb-2">
              {worker.business_name}
            </h1>
            <p className="text-gray-600">{worker.location.area}</p>
          </div>
          <span
            className={`px-4 py-2 rounded-full text-sm font-semibold ${
              TRUST_LEVEL_COLORS[worker.trust_score.trust_level]
            }`}
          >
            {worker.trust_score.trust_level} - {worker.trust_score.total_score}
          </span>
        </div>

        {/* Specializations */}
        <div className="flex flex-wrap gap-2 mb-4">
          {worker.specializations.map((spec, idx) => (
            <span
              key={idx}
              className="px-3 py-1 bg-blue-50 text-blue-700 text-sm rounded-full"
            >
              {spec}
            </span>
          ))}
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-gray-200">
          {worker.trust_score.rating && (
            <div>
              <p className="text-sm text-gray-600">Rating</p>
              <p className="text-xl font-semibold text-gray-900">
                ⭐ {worker.trust_score.rating.toFixed(1)}
              </p>
            </div>
          )}
          <div>
            <p className="text-sm text-gray-600">Reviews</p>
            <p className="text-xl font-semibold text-gray-900">
              {worker.trust_score.review_count}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-600">Photos</p>
            <p className="text-xl font-semibold text-gray-900">{worker.photos_count}</p>
          </div>
          {worker.price_idr_per_day && (
            <div>
              <p className="text-sm text-gray-600">Price/Day</p>
              <p className="text-lg font-semibold text-gray-900">
                {formatPrice(worker.price_idr_per_day)}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Contact Information */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">📞 Contact Information</h2>

        <div className="space-y-4">
          {worker.contact.whatsapp && (
            <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">WhatsApp</p>
                <p className="text-lg font-semibold text-gray-900">
                  {formatPhoneNumber(worker.contact.whatsapp)}
                </p>
              </div>
              <button
                onClick={handleWhatsAppClick}
                className="px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 transition-colors"
              >
                Message on WhatsApp
              </button>
            </div>
          )}

          {worker.contact.phone && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-sm text-gray-600">Phone</p>
              <a
                href={`tel:${worker.contact.phone}`}
                className="text-lg font-semibold text-blue-600 hover:underline"
              >
                {formatPhoneNumber(worker.contact.phone)}
              </a>
            </div>
          )}

          {worker.contact.email && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-sm text-gray-600">Email</p>
              <a
                href={`mailto:${worker.contact.email}`}
                className="text-lg font-semibold text-blue-600 hover:underline"
              >
                {worker.contact.email}
              </a>
            </div>
          )}

          {worker.contact.website && (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-sm text-gray-600">Website</p>
              <a
                href={worker.contact.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-lg font-semibold text-blue-600 hover:underline"
              >
                {worker.contact.website} →
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Location */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">📍 Location</h2>

        <div className="space-y-3">
          {worker.location.address && (
            <p className="text-gray-700">{worker.location.address}</p>
          )}
          <p className="text-gray-700 font-semibold">{worker.location.area}</p>

          {worker.location.maps_url && (
            <a
              href={worker.location.maps_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 transition-colors"
            >
              Open in Google Maps →
            </a>
          )}

          {worker.opening_hours && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-sm text-gray-600">Opening Hours</p>
              <p className="text-gray-900">{worker.opening_hours}</p>
            </div>
          )}
        </div>
      </div>

      {/* Negotiation Script */}
      {worker.negotiation_script && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <div className="flex justify-between items-start mb-4">
            <h2 className="text-xl font-bold text-gray-900">💬 Negotiation Script</h2>
            <button
              onClick={copyNegotiationScript}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg font-semibold hover:bg-gray-300 transition-colors"
            >
              {copiedScript ? '✓ Copied!' : 'Copy Script'}
            </button>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
            <p className="text-sm text-blue-800">
              💡 <strong>AI-powered script:</strong> Use this as a starting point for your
              conversation. Adjust based on your specific needs and budget.
            </p>
          </div>

          <div className="prose max-w-none">
            <pre className="whitespace-pre-wrap bg-gray-50 p-4 rounded-lg text-sm text-gray-800 font-sans">
              {worker.negotiation_script}
            </pre>
          </div>
        </div>
      )}

      {/* Reviews */}
      {worker.reviews.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            ⭐ Reviews ({worker.reviews.length})
          </h2>

          <div className="space-y-4">
            {worker.reviews.map((review, idx) => (
              <div key={idx} className="border-b border-gray-200 pb-4 last:border-0">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="font-semibold text-gray-900">{review.reviewer}</p>
                    <p className="text-sm text-gray-600">
                      {new Date(review.date).toLocaleDateString('id-ID', {
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      })}
                    </p>
                  </div>
                  <div className="flex items-center">
                    <span className="text-yellow-500 mr-1">⭐</span>
                    <span className="font-semibold">{review.rating.toFixed(1)}</span>
                  </div>
                </div>
                <p className="text-gray-700">{review.text}</p>
                <p className="text-xs text-gray-500 mt-2">Source: {review.source}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Categories */}
      {worker.categories.length > 0 && (
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">🏷️ Service Categories</h2>
          <div className="flex flex-wrap gap-2">
            {worker.categories.map((category, idx) => (
              <span
                key={idx}
                className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-lg"
              >
                {category}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
