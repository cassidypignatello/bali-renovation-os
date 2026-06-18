'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  boqApi,
  type BoQUploadResponse,
  type BoQJobStatusResponse,
  type BoQAnalysisResults,
  type BoQItemPriced,
} from '@/lib/api/boq';

type UploadState = 'idle' | 'uploading' | 'processing' | 'completed' | 'failed';

// Stage message boundaries (inclusive lower, exclusive upper)
function getStageMessage(percent: number): string {
  if (percent < 8) return 'Reading your document…';
  if (percent < 30) return 'AI is extracting line items from your pages…';
  if (percent < 40) return 'Organizing extracted items…';
  if (percent < 55) return 'Checking recent market prices…';
  if (percent < 80) return 'Searching Tokopedia for live prices…';
  if (percent < 85) return 'Matching products to your materials…';
  return 'Calculating your savings…';
}

// Next stage boundary (used to cap the creep so bar never visually enters next stage)
function nextStageBoundary(percent: number): number {
  if (percent < 8) return 8;
  if (percent < 30) return 30;
  if (percent < 40) return 40;
  if (percent < 55) return 55;
  if (percent < 80) return 80;
  if (percent < 85) return 85;
  return 100;
}

// Tips shown during the two long stages
const EXTRACTION_TIPS = [
  'We read every line item — quantities, units, and prices.',
  'Items marked "Supply By Owner" become your shopping list.',
  'Large documents can take a few minutes — your analysis is running.',
  'We extract from every page, even dense multi-column tables.',
  'Suspicious price matches are filtered out automatically.',
];

const SCRAPING_TIPS = [
  'Prices come from live Tokopedia listings, Bali sellers prioritized.',
  'Suspicious price matches are filtered out automatically.',
  'We cross-check multiple listings before picking a market price.',
  'Items marked "Supply By Owner" become your shopping list.',
  'Large documents can take a few minutes — your analysis is running.',
];

function useTips(active: boolean, tips: string[]): string {
  const [tipIndex, setTipIndex] = useState(0);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => {
      setTipIndex(i => (i + 1) % tips.length);
    }, 6000);
    return () => clearInterval(id);
  }, [active, tips.length]);

  return tips[tipIndex];
}

// Match-confidence stamp chip: >=67% palm, 33-66% sun, below that ink-soft
function confidenceChipStyle(confidence: number): React.CSSProperties {
  if (confidence >= 0.67) {
    return { borderColor: 'var(--palm)', color: 'var(--palm)' };
  }
  if (confidence >= 0.33) {
    return { borderColor: 'var(--sun)', color: 'var(--sun)' };
  }
  return { borderColor: 'var(--ink-soft)', color: 'var(--ink-soft)' };
}

// CSS-drawn document icon (no emoji): rectangle, ruled lines, folded corner
function DocumentIcon({ ready = false }: { ready?: boolean }) {
  return (
    <div className="relative inline-block mb-5">
      <div
        className="relative mx-auto"
        style={{
          width: '48px',
          height: '60px',
          background: ready ? 'rgba(31,92,61,0.08)' : 'white',
          border: '1px solid var(--ink)',
          borderRadius: '2px',
          transform: 'rotate(-3deg)',
          boxShadow: '2px 3px 8px rgba(32,35,29,0.12)',
        }}
      >
        {/* Three ruled lines */}
        <div
          className="absolute"
          style={{ top: '16px', left: '8px', width: '24px', height: '1.5px', background: 'var(--ink-soft)' }}
        />
        <div
          className="absolute"
          style={{ top: '26px', left: '8px', width: '30px', height: '1.5px', background: 'var(--ink-soft)' }}
        />
        <div
          className="absolute"
          style={{ top: '36px', left: '8px', width: '20px', height: '1.5px', background: 'var(--ink-soft)' }}
        />
        {/* Folded corner */}
        <div
          className="absolute"
          style={{
            top: '-1px',
            right: '-1px',
            width: 0,
            height: 0,
            borderLeft: '12px solid transparent',
            borderTop: '12px solid var(--paper)',
          }}
        />
        <div
          className="absolute"
          style={{
            top: '0px',
            right: '0px',
            width: 0,
            height: 0,
            borderLeft: '11px solid transparent',
            borderTop: '11px solid var(--rule)',
          }}
        />
      </div>
      {/* Palm check circle when ready */}
      {ready && (
        <div
          className="absolute flex items-center justify-center"
          style={{
            bottom: '-6px',
            right: '-10px',
            width: '22px',
            height: '22px',
            borderRadius: '50%',
            background: 'var(--palm)',
          }}
        >
          {/* CSS check via border trick */}
          <span
            style={{
              display: 'block',
              width: '10px',
              height: '5px',
              borderLeft: '2px solid white',
              borderBottom: '2px solid white',
              transform: 'rotate(-45deg) translateY(-1px)',
            }}
          />
        </div>
      )}
    </div>
  );
}

export function BoQUpload() {
  const [state, setState] = useState<UploadState>('idle');
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  // realPercent: what the backend last reported
  const [realPercent, setRealPercent] = useState(0);
  // displayedPercent: the smoothed value shown in the bar
  const [displayedPercent, setDisplayedPercent] = useState(0);
  const [results, setResults] = useState<BoQAnalysisResults | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const animIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const isProcessingRef = useRef(false);
  const realPercentRef = useRef(0);
  const displayedPercentRef = useRef(0);

  // Keep refs in sync so the animation closure always has fresh values
  useEffect(() => { realPercentRef.current = realPercent; }, [realPercent]);
  useEffect(() => { displayedPercentRef.current = displayedPercent; }, [displayedPercent]);

  const stopAnimInterval = useCallback(() => {
    if (animIntervalRef.current) {
      clearInterval(animIntervalRef.current);
      animIntervalRef.current = null;
    }
  }, []);

  const startAnimInterval = useCallback(() => {
    stopAnimInterval();
    animIntervalRef.current = setInterval(() => {
      const real = realPercentRef.current;
      const displayed = displayedPercentRef.current;

      if (displayed >= 100) return;

      if (displayed < real) {
        // Ease toward real: close the gap by ~40% each tick, minimum step 0.5
        const gap = real - displayed;
        const step = Math.max(gap * 0.4, 0.5);
        const next = Math.min(displayed + step, real);
        setDisplayedPercent(next);
      } else if (isProcessingRef.current) {
        // Creep: +1 capped at min(real + 4, nextBoundary - 1)
        const cap = Math.min(real + 4, nextStageBoundary(real) - 1);
        if (displayed < cap) {
          setDisplayedPercent(displayed + 1);
        }
      }
    }, 2500);
  }, [stopAnimInterval]);

  // Clean up all intervals on unmount
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      stopAnimInterval();
    };
  }, [stopAnimInterval]);

  const stageMessage = getStageMessage(realPercent);
  const isExtractingStage = realPercent >= 8 && realPercent < 30;
  const isScrapingStage = realPercent >= 55 && realPercent < 80;
  const showTips = isExtractingStage || isScrapingStage;
  const activeTips = isScrapingStage ? SCRAPING_TIPS : EXTRACTION_TIPS;
  const currentTip = useTips(state === 'processing' && showTips, activeTips);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(price);
  };

  const handleFileSelect = useCallback((file: File) => {
    const validTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
    ];
    const validExtensions = ['.pdf', '.xlsx', '.xls'];

    const hasValidType = validTypes.includes(file.type);
    const hasValidExtension = validExtensions.some(ext =>
      file.name.toLowerCase().endsWith(ext)
    );

    if (!hasValidType && !hasValidExtension) {
      setError('Please upload a PDF or Excel file (.pdf, .xlsx, .xls)');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setError('File too large. Maximum size is 10MB.');
      return;
    }

    setSelectedFile(file);
    setError(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFileSelect(file);
      }
    },
    [handleFileSelect]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const pollStatus = useCallback(async (jobId: string) => {
    const response = await boqApi.getStatus(jobId);

    if (response.error) {
      console.error('[BoQ] Status poll error:', response.error.message, response.error.details);
      setError(response.error.message);
      setState('failed');
      isProcessingRef.current = false;
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      stopAnimInterval();
      return;
    }

    const status = response.data!;
    const newReal = status.progress_percent;

    // Never go backwards
    setRealPercent(prev => Math.max(prev, newReal));
    realPercentRef.current = Math.max(realPercentRef.current, newReal);

    if (status.status === 'completed') {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      isProcessingRef.current = false;
      stopAnimInterval();

      // Snap displayed to 100
      setDisplayedPercent(100);
      setRealPercent(100);

      const resultsResponse = await boqApi.getResults(jobId);
      if (resultsResponse.error) {
        console.error('[BoQ] Results fetch error:', resultsResponse.error.message, resultsResponse.error.details);
        setError(resultsResponse.error.message);
        setState('failed');
      } else {
        setResults(resultsResponse.data!);
        setState('completed');
      }
    } else if (status.status === 'failed') {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      isProcessingRef.current = false;
      stopAnimInterval();
      console.error('[BoQ] Processing failed:', status.error_message);
      setError(status.error_message || 'Processing failed');
      setState('failed');
    }
  }, [stopAnimInterval]);

  const handleUpload = async () => {
    if (!selectedFile) return;

    setState('uploading');
    setError(null);
    setRealPercent(0);
    setDisplayedPercent(0);
    realPercentRef.current = 0;
    displayedPercentRef.current = 0;

    const response = await boqApi.uploadFile(selectedFile);

    if (response.error) {
      console.error('[BoQ] Upload error:', response.error.message, response.error.details);
      setError(response.error.message);
      setState('failed');
      return;
    }

    const data = response.data!;
    setJobId(data.job_id);
    setState('processing');
    isProcessingRef.current = true;

    // Start smooth animation
    startAnimInterval();

    // Start polling for status
    pollIntervalRef.current = setInterval(() => {
      pollStatus(data.job_id);
    }, 2500);

    // Initial poll
    pollStatus(data.job_id);
  };

  const handleReset = () => {
    setState('idle');
    setSelectedFile(null);
    setJobId(null);
    setRealPercent(0);
    setDisplayedPercent(0);
    realPercentRef.current = 0;
    displayedPercentRef.current = 0;
    setResults(null);
    setError(null);
    isProcessingRef.current = false;
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    stopAnimInterval();
  };

  const barPercent = Math.min(Math.round(displayedPercent), 100);

  // Render results view
  if (state === 'completed' && results) {
    return (
      <div className="space-y-8">
        {/* Extraction warnings */}
        {results.extraction_warnings.length > 0 && (
          <div
            className="px-4 py-3 text-sm"
            style={{
              background: 'rgba(217,164,65,0.10)',
              border: '1px solid var(--sun)',
              borderRadius: '2px',
              color: 'var(--ink)',
            }}
          >
            <span className="font-mono font-medium tracking-wider" style={{ color: 'var(--sun)' }}>
              NOTE —{' '}
            </span>
            <span className="font-body">
              Some pages could not be fully read — totals may be incomplete.
              {' '}({results.extraction_warnings.length} {results.extraction_warnings.length === 1 ? 'issue' : 'issues'})
            </span>
          </div>
        )}

        {/* Audit Complete header */}
        <div>
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="min-w-0 flex-1">
              <div
                className="animate-stamp inline-block font-mono text-xs font-medium tracking-[0.2em] uppercase mb-2"
                style={{ color: 'var(--palm)' }}
              >
                Audit Complete
              </div>
              <h3
                className="font-display font-semibold text-xl truncate"
                style={{ color: 'var(--ink)' }}
              >
                {results.metadata.filename}
                {results.metadata.contractor_name && (
                  <span className="ml-2 text-base" style={{ color: 'var(--ink-soft)' }}>
                    — {results.metadata.contractor_name}
                  </span>
                )}
              </h3>
            </div>
            <button
              onClick={handleReset}
              className="flex-shrink-0 px-4 py-2 font-mono text-xs font-medium uppercase tracking-widest transition-all hover:-translate-y-px active:translate-y-0"
              style={{
                background: 'transparent',
                border: '1px solid var(--ink)',
                borderRadius: '2px',
                color: 'var(--ink)',
              }}
            >
              New Audit
            </button>
          </div>

          {/* Ledger strip: key metrics */}
          <div
            className="grid grid-cols-2 md:grid-cols-4"
            style={{ border: '1px solid var(--rule)', borderRadius: '2px', background: 'rgba(255,255,255,0.5)' }}
          >
            <div className="min-w-0 overflow-hidden p-4 border-b md:border-b-0 border-r" style={{ borderColor: 'var(--rule)' }}>
              <div className="font-mono text-[11px] uppercase tracking-widest mb-1" style={{ color: 'var(--ink-soft)' }}>
                Contractor Quote
              </div>
              <div className="font-mono font-semibold whitespace-nowrap" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums', fontSize: 'clamp(0.85rem,2.1vw,1rem)' }}>
                {formatPrice(results.summary.contractor_total)}
              </div>
            </div>
            <div className="min-w-0 overflow-hidden p-4 border-b md:border-b-0 md:border-r" style={{ borderColor: 'var(--rule)' }}>
              <div className="font-mono text-[11px] uppercase tracking-widest mb-1" style={{ color: 'var(--ink-soft)' }}>
                Market Estimate
              </div>
              {results.summary.market_estimate != null ? (
                <div className="font-mono font-semibold whitespace-nowrap" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums', fontSize: 'clamp(0.85rem,2.1vw,1rem)' }}>
                  {formatPrice(results.summary.market_estimate)}
                </div>
              ) : (
                <div className="font-mono text-sm" style={{ color: 'var(--ink-soft)' }}>
                  — Not enough market data
                </div>
              )}
            </div>
            <div className="min-w-0 overflow-hidden p-4 border-r" style={{ background: 'var(--ink-panel)', borderColor: 'var(--rule)' }}>
              <div className="font-mono text-[11px] uppercase tracking-widest mb-1" style={{ color: 'rgba(250,245,236,0.6)' }}>
                Potential Savings
              </div>
              {results.summary.potential_savings != null ? (
                <>
                  <div className="font-mono font-semibold whitespace-nowrap" style={{ color: 'var(--palm-bright)', fontVariantNumeric: 'tabular-nums', fontSize: 'clamp(0.85rem,2.1vw,1rem)' }}>
                    {formatPrice(results.summary.potential_savings)}
                    {results.summary.savings_percent != null && (
                      <span className="ml-1.5 text-sm font-medium" style={{ color: 'var(--sun)' }}>
                        ({results.summary.savings_percent.toFixed(1)}%)
                      </span>
                    )}
                  </div>
                  {results.summary.compared_count != null && results.summary.compared_count > 0 && (
                    <div className="font-mono text-[11px] mt-1" style={{ color: 'rgba(250,245,236,0.6)' }}>
                      across {results.summary.compared_count} material{results.summary.compared_count === 1 ? '' : 's'} priced above market
                    </div>
                  )}
                </>
              ) : (
                <div className="font-mono text-sm" style={{ color: 'rgba(250,245,236,0.6)' }}>
                  — Not enough market data
                </div>
              )}
            </div>
            <div className="min-w-0 overflow-hidden p-4">
              <div className="font-mono text-[11px] uppercase tracking-widest mb-1" style={{ color: 'var(--ink-soft)' }}>
                Items Analyzed
              </div>
              <div className="font-mono font-semibold whitespace-nowrap" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums', fontSize: 'clamp(0.85rem,2.1vw,1rem)' }}>
                {results.summary.priced_count}/{results.summary.materials_count}
                <span className="ml-1 text-xs font-normal" style={{ color: 'var(--ink-soft)' }}>priced</span>
              </div>
            </div>
          </div>
        </div>

        {/* Owner Supply Items - Shopping List */}
        {results.owner_supply_items.length > 0 && (
          <div>
            <div className="flex items-center gap-3 mb-1 flex-wrap">
              <h4 className="font-display font-semibold text-lg" style={{ color: 'var(--ink)' }}>
                Your Shopping List
              </h4>
              <span
                className="font-mono text-[11px] font-medium uppercase tracking-widest px-2.5 py-0.5 rounded-full"
                style={{ border: '1px solid var(--ink)', color: 'var(--ink)' }}
              >
                {results.owner_supply_items.length} {results.owner_supply_items.length === 1 ? 'Item' : 'Items'}
              </span>
              {results.summary.shopping_list_total != null && (
                <span
                  className="font-mono text-[11px] font-medium uppercase tracking-widest px-2.5 py-0.5 rounded-full"
                  style={{ border: '1px solid var(--sun)', color: 'var(--sun)' }}
                >
                  ≈ {formatPrice(results.summary.shopping_list_total)} to buy
                </span>
              )}
            </div>
            <p className="text-sm font-body mb-4" style={{ color: 'var(--ink-soft)' }}>
              These items are marked &quot;Supply By Owner&quot; — you need to purchase them yourself
            </p>
            <div className="space-y-3">
              {results.owner_supply_items.map((item, idx) => (
                <ItemCard key={item.id || idx} item={item} showPricing />
              ))}
            </div>
          </div>
        )}

        {/* Overpriced Items */}
        {results.overpriced_items.length > 0 && (
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h4 className="font-display font-semibold text-lg" style={{ color: 'var(--ink)' }}>
                Potentially Overpriced
              </h4>
              <span
                className="font-mono text-[11px] font-medium uppercase tracking-widest px-2.5 py-0.5 rounded-full"
                style={{ border: '1px solid var(--clay)', color: 'var(--clay)' }}
              >
                {results.overpriced_items.length} {results.overpriced_items.length === 1 ? 'Item' : 'Items'}
              </span>
            </div>
            <p className="text-sm font-body mb-4" style={{ color: 'var(--ink-soft)' }}>
              These items may be priced higher than market rates (&gt;10% above market)
            </p>
            <div className="space-y-3">
              {results.overpriced_items.slice(0, 10).map((item, idx) => (
                <ItemCard key={item.id || idx} item={item} showPricing showDifference />
              ))}
            </div>
          </div>
        )}

        {/* All Materials Summary */}
        <div>
          <div className="flex items-center gap-3 mb-4">
            <h4 className="font-display font-semibold text-lg" style={{ color: 'var(--ink)' }}>
              All Materials
            </h4>
            <span
              className="font-mono text-[11px] font-medium uppercase tracking-widest px-2.5 py-0.5 rounded-full"
              style={{ border: '1px solid var(--ink)', color: 'var(--ink)' }}
            >
              {results.all_materials.length} {results.all_materials.length === 1 ? 'Item' : 'Items'}
            </span>
          </div>
          <div className="max-h-96 overflow-y-auto space-y-2">
            {results.all_materials.map((item, idx) => (
              <ItemCard key={item.id || idx} item={item} compact />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Drop Zone / Audit Panel */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        className={`
          relative p-8 text-center transition-all
          ${state === 'idle' ? 'hover:bg-white/40' : ''}
        `}
        style={{
          border:
            state === 'failed'
              ? '1px solid var(--clay)'
              : state === 'uploading' || state === 'processing'
                ? '1px solid var(--rule)'
                : '1.5px dashed var(--ink)',
          borderRadius: '2px',
          background:
            state === 'failed'
              ? 'var(--clay-soft)'
              : 'var(--paper)',
        }}
      >
        {/* Native label-for pattern: bulletproof file chooser in all browsers including Chrome */}
        <input
          id="boq-file-input"
          type="file"
          accept=".pdf,.xlsx,.xls"
          onChange={(e) => {
            if (e.target.files?.[0]) {
              handleFileSelect(e.target.files[0]);
            }
            e.target.value = '';
          }}
          className="sr-only"
        />

        {state === 'idle' && (
          <label htmlFor="boq-file-input" className="cursor-pointer block">
            {!selectedFile ? (
              <>
                <DocumentIcon />
                <p className="font-display font-semibold text-xl" style={{ color: 'var(--ink)' }}>
                  Drop the quote here
                </p>
                <p className="font-body text-sm mt-2" style={{ color: 'var(--ink-soft)' }}>
                  PDF or Excel — exactly as the contractor sent it
                </p>
              </>
            ) : (
              <>
                <DocumentIcon ready />
                <p className="font-mono font-medium text-sm break-words" style={{ color: 'var(--ink)' }}>
                  {selectedFile.name}
                </p>
                <p className="font-mono text-xs mt-2" style={{ color: 'var(--ink-soft)' }}>
                  {(selectedFile.size / 1024).toFixed(1)} KB · Ready to analyze
                </p>
              </>
            )}
          </label>
        )}

        {(state === 'uploading' || state === 'processing') && (
          <div className="text-left">
            {state === 'uploading' && (
              <p className="font-body font-medium" style={{ color: 'var(--ink)' }}>
                Uploading…
              </p>
            )}
            {state === 'processing' && (
              <>
                <div className="flex items-baseline gap-4 flex-wrap">
                  <span
                    className="font-mono font-semibold"
                    style={{
                      fontSize: '2.5rem',
                      lineHeight: 1,
                      color: 'var(--ink)',
                      fontVariantNumeric: 'tabular-nums',
                    }}
                  >
                    {barPercent}%
                  </span>
                  <span className="font-body text-sm" style={{ color: 'var(--ink)' }}>
                    {stageMessage}
                  </span>
                </div>
                <div
                  className="mt-4 w-full overflow-hidden"
                  style={{ height: '6px', background: 'var(--paper-deep)' }}
                >
                  <div
                    className="progress-bar-sweep h-full transition-all duration-700 ease-out"
                    style={{ width: `${barPercent}%`, background: 'var(--palm)' }}
                  />
                </div>
                {showTips && (
                  <p
                    key={currentTip}
                    className="animate-tick font-mono text-xs mt-3"
                    style={{ color: 'var(--ink-soft)' }}
                  >
                    {currentTip}
                  </p>
                )}
              </>
            )}
          </div>
        )}

        {state === 'failed' && (
          <>
            <p className="font-display font-semibold text-xl" style={{ color: 'var(--clay)' }}>
              We couldn&apos;t read that one.
            </p>
            <p className="font-body text-sm mt-2" style={{ color: 'var(--ink)' }}>
              We couldn&apos;t process this file. Please try again, or contact us if it keeps happening.
            </p>
          </>
        )}
      </div>

      {/* Action Buttons */}
      {state === 'idle' && selectedFile && (
        <button
          onClick={handleUpload}
          className="w-full py-3 px-6 font-mono font-medium uppercase tracking-widest text-sm text-white transition-all hover:brightness-90 hover:-translate-y-px active:translate-y-0 active:brightness-75"
          style={{ background: 'var(--palm)', borderRadius: '2px' }}
        >
          Run the Audit →
        </button>
      )}

      {state === 'failed' && (
        <button
          onClick={handleReset}
          className="w-full py-3 px-6 font-mono font-medium uppercase tracking-widest text-sm text-white transition-all hover:brightness-90 hover:-translate-y-px active:translate-y-0 active:brightness-75"
          style={{ background: 'var(--clay)', borderRadius: '2px' }}
        >
          Try Again
        </button>
      )}

      {/* Info */}
      {state === 'idle' && (
        <p
          className="text-center font-mono text-[11px] uppercase tracking-[0.18em]"
          style={{ color: 'var(--ink-soft)' }}
        >
          Verify Pricing / Build Shopping List / Match Confidence
        </p>
      )}

      {/* Processing Info */}
      {state === 'processing' && (
        <p className="text-center font-mono text-xs" style={{ color: 'var(--ink-soft)' }}>
          Analysis typically takes 3–7 minutes for full documents
        </p>
      )}
    </div>
  );
}

// Item Card Component
function ItemCard({
  item,
  showPricing = false,
  showDifference = false,
  compact = false,
}: {
  item: BoQItemPriced;
  showPricing?: boolean;
  showDifference?: boolean;
  compact?: boolean;
}) {
  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(price);
  };

  if (compact) {
    return (
      <div
        className="flex items-center justify-between py-2 px-3 transition-colors hover:bg-white/80"
        style={{
          background: 'rgba(255,255,255,0.5)',
          border: '1px solid var(--rule)',
          borderRadius: '2px',
        }}
      >
        <div className="flex-1 min-w-0 mr-4">
          <p className="text-sm font-body font-medium truncate break-words" style={{ color: 'var(--ink)' }}>
            {item.description}
          </p>
          {item.quantity && item.unit && (
            <p className="font-mono text-xs" style={{ color: 'var(--ink-soft)' }}>
              {item.quantity} {item.unit}
            </p>
          )}
        </div>
        <div className="flex-shrink-0 text-right">
          {item.contractor_total ? (
            <p className="font-mono text-sm font-medium" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
              {formatPrice(item.contractor_total)}
            </p>
          ) : null}
          {item.match_confidence !== undefined && item.match_confidence > 0 && (
            <span
              className="inline-block font-mono text-[10px] font-medium px-1.5 py-0.5"
              style={{
                border: '1px solid',
                borderRadius: '2px',
                ...confidenceChipStyle(item.match_confidence),
              }}
            >
              {Math.round(item.match_confidence * 100)}%
            </span>
          )}
        </div>
      </div>
    );
  }

  return (
    <div
      className="ledger-ruled p-4 min-w-0"
      style={{
        background: 'rgba(255,255,255,0.5)',
        border: '1px solid var(--rule)',
        borderLeft: showDifference ? '3px solid var(--clay)' : '1px solid var(--rule)',
        borderRadius: '2px',
      }}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="font-body font-medium break-words" style={{ color: 'var(--ink)' }}>
            {item.description}
          </p>
          {item.quantity && item.unit && (
            <p className="font-mono text-sm mt-1" style={{ color: 'var(--ink-soft)' }}>
              {item.quantity} {item.unit}
              {item.contractor_unit_price && (
                <span> @ {formatPrice(item.contractor_unit_price)}</span>
              )}
            </p>
          )}
        </div>
        {item.match_confidence !== undefined && item.match_confidence > 0 && (
          <span
            className="flex-shrink-0 font-mono text-[11px] font-medium uppercase tracking-wider px-2 py-1"
            style={{
              border: '1px solid',
              borderRadius: '2px',
              ...confidenceChipStyle(item.match_confidence),
            }}
          >
            {Math.round(item.match_confidence * 100)}% match
          </span>
        )}
      </div>

      {showPricing && item.tokopedia_product_name && (
        <div className="mt-3 pt-3 min-w-0" style={{ borderTop: '1px solid var(--rule)' }}>
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="font-mono text-xs uppercase tracking-wider" style={{ color: 'var(--ink-soft)' }}>
                Market Match
              </p>
              <p className="font-body text-sm font-medium break-words line-clamp-2" style={{ color: 'var(--ink)' }}>
                {item.tokopedia_product_name}
              </p>
              {item.tokopedia_seller_location && (
                <p className="font-mono text-xs break-words" style={{ color: 'var(--ink-soft)' }}>
                  {item.tokopedia_seller_location}
                </p>
              )}
            </div>
            <div className="flex-shrink-0 text-right">
              {item.tokopedia_price && (
                <p className="font-mono text-base font-semibold" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
                  {formatPrice(item.tokopedia_price)}
                </p>
              )}
              {item.tokopedia_url && (
                <a
                  href={item.tokopedia_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs hover:underline"
                  style={{ color: 'var(--palm)' }}
                >
                  View on Tokopedia →
                </a>
              )}
            </div>
          </div>
        </div>
      )}

      {showDifference && item.price_difference_percent !== undefined && (
        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--rule)' }}>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="font-mono text-sm" style={{ color: 'var(--ink-soft)' }}>
                Contractor: {item.contractor_unit_price ? formatPrice(item.contractor_unit_price) : '—'}
              </p>
              <p className="font-mono text-sm" style={{ color: 'var(--ink-soft)' }}>
                Market: {item.market_unit_price ? formatPrice(item.market_unit_price) : '—'}
              </p>
            </div>
            <div className="flex-shrink-0 text-right">
              <p className="font-mono text-lg font-semibold" style={{ color: 'var(--clay)', fontVariantNumeric: 'tabular-nums' }}>
                +{item.price_difference_percent?.toFixed(1)}%
              </p>
              <p className="font-mono text-xs" style={{ color: 'var(--ink-soft)' }}>
                above market
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
