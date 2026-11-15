import type { EventStatus, QualityFlag } from '../domain/types'
import { EVENT_STATUS_LABEL, QUALITY_LABEL } from '../domain/parameters'
import type { Freshness } from '../domain/freshness'
import { FRESHNESS_GLYPH, FRESHNESS_LABEL } from '../domain/freshness'

/**
 * Functional status glyphs: each state has its own SHAPE as well as colour,
 * and is always paired with a text label (colour is never the only cue).
 */
export function QualityGlyph({ quality, size = 12 }: { quality: QualityFlag; size?: number }) {
  const s = size
  const c = s / 2
  const common = { width: s, height: s, viewBox: `0 0 ${s} ${s}`, 'aria-hidden': true as const, className: `glyph q-${quality}` }
  switch (quality) {
    case 'good':
      return (
        <svg {...common}>
          <circle cx={c} cy={c} r={c - 1} fill="currentColor" />
        </svg>
      )
    case 'uncertain':
      return (
        <svg {...common}>
          <circle cx={c} cy={c} r={c - 1.5} fill="none" stroke="currentColor" strokeWidth={1.5} />
          <path d={`M${c} 1.5 A${c - 1.5} ${c - 1.5} 0 0 1 ${c} ${s - 1.5} Z`} fill="currentColor" />
        </svg>
      )
    case 'poor':
      return (
        <svg {...common}>
          <path d={`M${c} 1 L${s - 1} ${s - 1.5} L1 ${s - 1.5} Z`} fill="currentColor" />
        </svg>
      )
    case 'missing':
      return (
        <svg {...common}>
          <circle cx={c} cy={c} r={c - 1.5} fill="none" stroke="currentColor" strokeWidth={1.5} strokeDasharray="2 2" />
        </svg>
      )
  }
}

export function QualityTag({ quality }: { quality: QualityFlag }) {
  return (
    <span className={`tag tag-q-${quality}`}>
      <QualityGlyph quality={quality} />
      {QUALITY_LABEL[quality]}
    </span>
  )
}

export function FreshnessTag({ freshness, compact = false }: { freshness: Freshness; compact?: boolean }) {
  const glyph = FRESHNESS_GLYPH[freshness]
  return (
    <span className={`tag tag-f-${freshness}${compact ? ' tag-compact' : ''}`}>
      <QualityGlyph quality={glyph} />
      {FRESHNESS_LABEL[freshness]}
    </span>
  )
}

/** Review status chip: shape + text (open ○ · in review ◐ · reviewed ✓), never colour alone. */
export function EventStatusChip({ status }: { status: EventStatus }) {
  return (
    <span className={`status status-${status}`}>
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="status-mark">
        {status === 'open' && <circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.6" />}
        {status === 'in_review' && (
          <>
            <circle cx="5" cy="5" r="3.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M5 1.4 A3.6 3.6 0 0 1 5 8.6 Z" fill="currentColor" />
          </>
        )}
        {status === 'reviewed' && <path d="M1.5 5.2 4 7.6 8.6 2.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />}
      </svg>
      {EVENT_STATUS_LABEL[status]}
    </span>
  )
}
