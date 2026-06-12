'use client';

import { BoQUpload } from '@/components/BoQUpload';
import { QuickPriceSearch } from '@/components/QuickPriceSearch';

function SheetTab({ number, label }: { number: string; label: string }) {
  return (
    <div
      className="absolute top-0 left-6 z-10 px-3 py-1 border border-b-0 text-xs tracking-wide"
      style={{
        transform: 'translateY(-100%)',
        background: 'white',
        borderColor: 'var(--rule)',
        fontFamily: 'var(--font-display)',
        fontWeight: 600,
        color: 'var(--ink)',
        borderTopWidth: '3px',
        borderTopColor: 'var(--ink)',
      }}
    >
      {number} — {label}
    </div>
  );
}

export default function Home() {
  return (
    <main
      className="min-h-screen px-4 py-16 md:py-20"
      style={{ background: 'var(--paper)' }}
    >
      <div className="mx-auto" style={{ maxWidth: '720px' }}>

        {/* Masthead */}
        <div className="animate-rise-1 relative mb-16">
          {/* Desktop stamp chip */}
          <div
            className="hidden md:flex absolute top-0 right-0 items-center px-3 py-1.5 text-xs font-mono tracking-widest"
            style={{
              border: '1px solid var(--ink)',
              transform: 'rotate(2deg)',
              color: 'var(--ink)',
              fontFamily: 'var(--font-mono)',
              lineHeight: 1.4,
            }}
          >
            EST. 2026 · CANGGU
          </div>

          {/* Overline rule + label */}
          <div className="flex items-center gap-4 mb-4">
            <div className="h-px flex-1 max-w-6" style={{ background: 'var(--rule)' }} />
            <span
              className="text-xs tracking-[0.2em] uppercase"
              style={{ color: 'var(--ink-soft)', fontFamily: 'var(--font-mono)' }}
            >
              Material Price Verification — Bali
            </span>
            <div className="h-px flex-1" style={{ background: 'var(--rule)' }} />
          </div>

          {/* Wordmark */}
          <div className="relative inline-block">
            <h1
              className="font-display italic font-black tracking-tight leading-none"
              style={{
                fontSize: 'clamp(3rem, 8vw, 5.5rem)',
                color: 'var(--ink)',
                fontVariationSettings: '"opsz" 72, "wght" 900',
              }}
            >
              Bangun
            </h1>
            {/* Sun underline flourish */}
            <div
              className="absolute -bottom-2 left-0"
              style={{
                width: '60px',
                height: '4px',
                background: 'var(--sun)',
                transform: 'rotate(-1.5deg)',
                borderRadius: '1px',
              }}
            />
          </div>

          {/* Tagline */}
          <p
            className="mt-6 text-base"
            style={{ color: 'var(--ink-soft)', fontFamily: 'var(--font-body)' }}
          >
            Your contractor&apos;s quote, checked against the live market.
          </p>
        </div>

        {/* Sheet 1: Audit Sheet (BoQUpload) */}
        <div className="animate-rise-2 relative mb-14">
          <SheetTab number="№ 1" label="Upload your BoQ" />
          <div
            className="relative"
            style={{
              background: 'rgba(255,255,255,0.6)',
              border: '1px solid var(--rule)',
              borderTop: '3px solid var(--ink)',
              borderRadius: '2px',
              boxShadow:
                '0 4px 8px rgba(32,35,29,0.04), 0 12px 24px rgba(32,35,29,0.06)',
            }}
          >
            <div className="p-6 md:p-8">
              <BoQUpload />
            </div>
          </div>
        </div>

        {/* Sheet 2: Quick Price Strip */}
        <div className="animate-rise-3 relative mb-14">
          <SheetTab number="№ 2" label="Quick price check" />
          <div
            className="relative"
            style={{
              background: 'var(--paper-deep)',
              border: '1px solid var(--rule)',
              borderTop: '3px solid var(--ink)',
              borderRadius: '2px',
              boxShadow:
                '0 4px 8px rgba(32,35,29,0.03), 0 12px 24px rgba(32,35,29,0.05)',
            }}
          >
            <div className="p-6 md:p-8">
              <QuickPriceSearch />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="animate-rise-4">
          <div className="h-px w-full mb-4" style={{ background: 'var(--rule)' }} />
          <p
            className="text-xs tracking-wide text-center"
            style={{ color: 'var(--ink-soft)', fontFamily: 'var(--font-mono)' }}
          >
            Prices from live Tokopedia listings · Bali sellers prioritized · Updated continuously
          </p>
        </div>

      </div>
    </main>
  );
}
