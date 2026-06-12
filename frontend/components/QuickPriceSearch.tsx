'use client';

import { useState } from 'react';
import { materialsApi, type PriceLookupResponse, type PriceLookupRequest } from '@/lib/api/materials';

interface QuickPriceSearchProps {
  onSearchComplete?: () => void;
}

export function QuickPriceSearch({ onSearchComplete }: QuickPriceSearchProps) {
  const [searchMode, setSearchMode] = useState<'single' | 'multiple'>('single');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<PriceLookupResponse[] | null>(null);
  const [stats, setStats] = useState<{ cacheHits: number; scrapeCount: number; totalCost: number } | null>(null);

  // Single search state
  const [materialName, setMaterialName] = useState('');
  const [quantity, setQuantity] = useState<number>(1);
  const [unit, setUnit] = useState('pcs');

  // Multiple search state (newline-separated list)
  const [materialsList, setMaterialsList] = useState('');

  const formatPrice = (priceIdr: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(priceIdr);
  };

  // Match-confidence stamp chip: >=67% palm, 33-66% sun, below that ink-soft
  const confidenceChipStyle = (confidence: number): React.CSSProperties => {
    if (confidence >= 0.67) return { borderColor: 'var(--palm)', color: 'var(--palm)' };
    if (confidence >= 0.33) return { borderColor: 'var(--sun)', color: 'var(--sun)' };
    return { borderColor: 'var(--ink-soft)', color: 'var(--ink-soft)' };
  };

  const getSourceBadge = (source: string) => {
    switch (source) {
      case 'cached':
        return (
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--sun)' }}>
            Cached
          </span>
        );
      case 'historical':
      case 'historical_fuzzy':
        return (
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--ink-soft)' }}>
            Stale Price
          </span>
        );
      case 'tokopedia':
        return (
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--palm)' }}>
            Live
          </span>
        );
      case 'estimated':
        return (
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--ink-soft)' }}>
            Estimated
          </span>
        );
      default:
        return (
          <span className="font-mono text-[10px] font-medium uppercase tracking-widest" style={{ color: 'var(--ink-soft)' }}>
            {source}
          </span>
        );
    }
  };

  const handleSingleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!materialName.trim()) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setStats(null);

    try {
      const response = await materialsApi.getPrice(materialName.trim(), quantity, unit);
      if (response.data) {
        setResults([response.data]);
        setStats({
          cacheHits: response.data.source === 'cached' || response.data.source.includes('historical') ? 1 : 0,
          scrapeCount: response.data.source === 'tokopedia' ? 1 : 0,
          totalCost: response.data.total_price_idr,
        });
      }
      onSearchComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get price');
    } finally {
      setLoading(false);
    }
  };

  const handleMultipleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const lines = materialsList.trim().split('\n').filter(line => line.trim());
    if (lines.length === 0) return;

    setLoading(true);
    setError(null);
    setResults(null);
    setStats(null);

    // Parse each line: "material name" or "material name, qty, unit"
    const materials: PriceLookupRequest[] = lines.map(line => {
      const parts = line.split(',').map(p => p.trim());
      return {
        material_name: parts[0],
        quantity: parts[1] ? parseFloat(parts[1]) : 1,
        unit: parts[2] || 'pcs',
      };
    });

    try {
      const response = await materialsApi.getPricesBatch(materials);
      if (response.data) {
        setResults(response.data.prices);
        setStats({
          cacheHits: response.data.cache_hits,
          scrapeCount: response.data.scrape_count,
          totalCost: response.data.total_cost_idr,
        });
      }
      onSearchComplete?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get prices');
    } finally {
      setLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    background: 'white',
    border: '1px solid var(--rule)',
    borderRadius: '2px',
    color: 'var(--ink)',
  };

  return (
    <div className="space-y-6">
      {/* Mode Toggle */}
      <div className="flex gap-6" style={{ borderBottom: '1px solid var(--rule)' }}>
        <button
          type="button"
          onClick={() => setSearchMode('single')}
          className="pb-2 font-mono text-xs font-medium uppercase tracking-widest transition-colors"
          style={{
            color: searchMode === 'single' ? 'var(--ink)' : 'var(--ink-soft)',
            borderBottom: searchMode === 'single' ? '2px solid var(--ink)' : '2px solid transparent',
            marginBottom: '-1px',
          }}
        >
          Single Item
        </button>
        <button
          type="button"
          onClick={() => setSearchMode('multiple')}
          className="pb-2 font-mono text-xs font-medium uppercase tracking-widest transition-colors"
          style={{
            color: searchMode === 'multiple' ? 'var(--ink)' : 'var(--ink-soft)',
            borderBottom: searchMode === 'multiple' ? '2px solid var(--ink)' : '2px solid transparent',
            marginBottom: '-1px',
          }}
        >
          Multiple Items
        </button>
      </div>

      {/* Single Item Search */}
      {searchMode === 'single' && (
        <form onSubmit={handleSingleSearch} className="space-y-4">
          <div>
            <label
              htmlFor="materialName"
              className="block font-mono text-[11px] uppercase tracking-widest mb-1.5"
              style={{ color: 'var(--ink-soft)' }}
            >
              What do you need priced?
            </label>
            <input
              id="materialName"
              type="text"
              value={materialName}
              onChange={(e) => setMaterialName(e.target.value)}
              placeholder="e.g., gypsum board 9mm, tempered glass 8mm, semen 50kg"
              className="w-full px-4 py-2 font-body text-sm focus:outline-none focus:ring-2 focus:ring-[var(--palm)]"
              style={inputStyle}
              required
            />
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label
                htmlFor="quantity"
                className="block font-mono text-[11px] uppercase tracking-widest mb-1.5"
                style={{ color: 'var(--ink-soft)' }}
              >
                Quantity
              </label>
              <input
                id="quantity"
                type="number"
                min="0.1"
                step="0.1"
                value={quantity}
                onChange={(e) => setQuantity(parseFloat(e.target.value) || 1)}
                className="w-full px-4 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-[var(--palm)]"
                style={{ ...inputStyle, fontVariantNumeric: 'tabular-nums' }}
              />
            </div>
            <div className="flex-1">
              <label
                htmlFor="unit"
                className="block font-mono text-[11px] uppercase tracking-widest mb-1.5"
                style={{ color: 'var(--ink-soft)' }}
              >
                Unit
              </label>
              <select
                id="unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                className="w-full px-4 py-2 font-body text-sm focus:outline-none focus:ring-2 focus:ring-[var(--palm)]"
                style={inputStyle}
              >
                <option value="pcs">pcs (pieces)</option>
                <option value="m2">m² (square meters)</option>
                <option value="m">m (meters)</option>
                <option value="kg">kg (kilograms)</option>
                <option value="liter">liter</option>
                <option value="sak">sak (bags)</option>
                <option value="roll">roll</option>
                <option value="lembar">lembar (sheets)</option>
              </select>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !materialName.trim()}
            className="w-full py-3 px-6 font-mono font-medium uppercase tracking-widest text-sm text-white transition-all hover:brightness-90 hover:-translate-y-px active:translate-y-0 active:brightness-75 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:brightness-100"
            style={{ background: 'var(--palm)', borderRadius: '2px' }}
          >
            {loading ? 'Checking…' : 'Check Price →'}
          </button>
        </form>
      )}

      {/* Multiple Items Search */}
      {searchMode === 'multiple' && (
        <form onSubmit={handleMultipleSearch} className="space-y-4">
          <div>
            <label
              htmlFor="materialsList"
              className="block font-mono text-[11px] uppercase tracking-widest mb-1.5"
              style={{ color: 'var(--ink-soft)' }}
            >
              Enter materials (one per line)
            </label>
            <textarea
              id="materialsList"
              value={materialsList}
              onChange={(e) => setMaterialsList(e.target.value)}
              placeholder={`gypsum board 9mm, 10, m2
tempered glass 8mm, 5, m2
semen 50kg, 20, pcs
keramik 60x60, 15, m2

Format: material name, quantity, unit
(quantity and unit are optional)`}
              rows={6}
              className="w-full px-4 py-2 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-[var(--palm)]"
              style={inputStyle}
              required
            />
            <p className="mt-1.5 font-mono text-[11px]" style={{ color: 'var(--ink-soft)' }}>
              Format: material name, quantity, unit (quantity and unit are optional, defaults to 1 pcs)
            </p>
          </div>

          <button
            type="submit"
            disabled={loading || !materialsList.trim()}
            className="w-full py-3 px-6 font-mono font-medium uppercase tracking-widest text-sm text-white transition-all hover:brightness-90 hover:-translate-y-px active:translate-y-0 active:brightness-75 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:brightness-100"
            style={{ background: 'var(--palm)', borderRadius: '2px' }}
          >
            {loading ? 'Checking…' : 'Check Prices →'}
          </button>
        </form>
      )}

      {/* Loading State */}
      {loading && (
        <div
          className="p-4 text-center"
          style={{ background: 'rgba(255,255,255,0.5)', border: '1px solid var(--rule)', borderRadius: '2px' }}
        >
          <div
            className="animate-spin inline-block w-5 h-5 border-2 rounded-full mb-2"
            style={{ borderColor: 'var(--palm)', borderTopColor: 'transparent' }}
          ></div>
          <p className="font-body text-sm" style={{ color: 'var(--ink)' }}>
            Checking prices… This may take a moment if we need to fetch live data.
          </p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div
          className="px-4 py-3 font-body text-sm"
          style={{
            background: 'var(--clay-soft)',
            border: '1px solid var(--clay)',
            borderRadius: '2px',
            color: 'var(--clay)',
          }}
        >
          {error}
        </div>
      )}

      {/* Results */}
      {results && results.length > 0 && (
        <div
          className="overflow-hidden"
          style={{ background: 'rgba(255,255,255,0.5)', border: '1px solid var(--rule)', borderRadius: '2px' }}
        >
          {/* Stats Header */}
          {stats && (
            <div
              className="px-4 py-3 flex flex-wrap gap-4 font-mono text-xs"
              style={{ background: 'var(--paper-deep)', borderBottom: '1px solid var(--rule)' }}
            >
              <span style={{ color: 'var(--ink)' }}>
                <strong>{results.length}</strong> item{results.length !== 1 ? 's' : ''} priced
              </span>
              {stats.cacheHits > 0 && (
                <span className="uppercase tracking-wider" style={{ color: 'var(--sun)' }}>
                  {stats.cacheHits} from cache
                </span>
              )}
              {stats.scrapeCount > 0 && (
                <span className="uppercase tracking-wider" style={{ color: 'var(--palm)' }}>
                  {stats.scrapeCount} live lookup{stats.scrapeCount !== 1 ? 's' : ''}
                </span>
              )}
              {results.length > 1 && (
                <span className="ml-auto font-semibold" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
                  Total: {formatPrice(stats.totalCost)}
                </span>
              )}
            </div>
          )}

          {/* Results List */}
          <div>
            {results.map((result, index) => (
              <div
                key={index}
                className="ledger-ruled p-4 transition-colors hover:bg-white/60"
                style={index > 0 ? { borderTop: '1px solid var(--rule)' } : undefined}
              >
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-body font-medium break-words" style={{ color: 'var(--ink)' }}>
                        {result.material_name}
                      </span>
                      {getSourceBadge(result.source)}
                    </div>
                    <div className="font-mono text-xs mt-1" style={{ color: 'var(--ink-soft)' }}>
                      {result.quantity} {result.unit} × {formatPrice(result.unit_price_idr)}/{result.unit}
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div
                      className="font-mono font-semibold text-base"
                      style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}
                    >
                      {formatPrice(result.total_price_idr)}
                    </div>
                    <span
                      className="inline-block font-mono text-[10px] font-medium uppercase tracking-wider px-1.5 py-0.5 mt-1"
                      style={{
                        border: '1px solid',
                        borderRadius: '2px',
                        ...confidenceChipStyle(result.confidence),
                      }}
                    >
                      {Math.round(result.confidence * 100)}% confidence
                    </span>
                  </div>
                </div>

                {/* Marketplace Link */}
                {result.affiliate_url && (
                  <div className="mt-2">
                    <a
                      href={result.affiliate_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-mono text-xs hover:underline"
                      style={{ color: 'var(--palm)' }}
                    >
                      View on Tokopedia →
                    </a>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
