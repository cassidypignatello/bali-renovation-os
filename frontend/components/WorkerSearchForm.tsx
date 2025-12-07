'use client';

import { useState } from 'react';
import { useWorkerSearch } from '@/lib/hooks';
import type { WorkerSearchRequest } from '@/lib/types';

interface WorkerSearchFormProps {
  onSearchComplete?: () => void;
}

export function WorkerSearchForm({ onSearchComplete }: WorkerSearchFormProps) {
  const { data, loading, error, search } = useWorkerSearch();
  const [formData, setFormData] = useState<WorkerSearchRequest>({
    project_type: '',
    location: '',
    min_trust_score: undefined,
    budget_range: null,
    max_results: 10,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await search(formData);
    onSearchComplete?.();
  };

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: value === '' ? undefined : value,
    }));
  };

  return (
    <div className="bg-white rounded-lg shadow-lg p-8">
      <h2 className="text-2xl font-semibold mb-6 text-gray-900">
        Find Trusted Workers
      </h2>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="project_type" className="block text-sm font-medium text-gray-700 mb-2">
            Project Type
          </label>
          <input
            type="text"
            id="project_type"
            name="project_type"
            value={formData.project_type}
            onChange={handleChange}
            placeholder="e.g., Villa Renovation, Pool Construction"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
          />
        </div>

        <div>
          <label htmlFor="location" className="block text-sm font-medium text-gray-700 mb-2">
            Location
          </label>
          <input
            type="text"
            id="location"
            name="location"
            value={formData.location}
            onChange={handleChange}
            placeholder="e.g., Canggu, Ubud, Seminyak"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            required
          />
        </div>

        <div>
          <label htmlFor="budget_range" className="block text-sm font-medium text-gray-700 mb-2">
            Budget Range (optional)
          </label>
          <select
            id="budget_range"
            name="budget_range"
            value={formData.budget_range || ''}
            onChange={handleChange}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Any Budget</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>

        <div>
          <label htmlFor="min_trust_score" className="block text-sm font-medium text-gray-700 mb-2">
            Minimum Trust Score (optional)
          </label>
          <input
            type="number"
            id="min_trust_score"
            name="min_trust_score"
            value={formData.min_trust_score || ''}
            onChange={handleChange}
            min="0"
            max="100"
            placeholder="0-100"
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white py-3 px-6 rounded-lg font-semibold hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Searching...' : 'Search Workers'}
        </button>
      </form>

      {data && data.workers.length > 0 && (
        <div className="mt-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <p className="text-green-800">
            Found {data.total_found} workers. Showing {data.showing} results.
          </p>
        </div>
      )}
    </div>
  );
}
