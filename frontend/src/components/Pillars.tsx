import type { DailyIndicatorId } from '../domain/types'
import type { Pillars } from '../domain/pillars'
import { DAILY_INDICATORS, QUALITY_LABEL, formatDailyValue } from '../domain/parameters'
import { QualityGlyph } from './StatusGlyphs'
import { isPastView } from '../state/pastView'

export type MethodTopic = 'quality' | 'baseline' | 'trend'

/**
 * The three things OrbitVitals adds to a number, side by side: how reliable it
 * is, what is usual for this person, and whether the change is sustained.
 */
export function PillarStrip({ p, indicator, onExplain }: { p: Pillars; indicator: DailyIndicatorId; onExplain: (t: MethodTopic) => void }) {
  const unit = DAILY_INDICATORS[indicator].unit === 'ms RMSSD' ? 'ms' : DAILY_INDICATORS[indicator].unit
  const f = (v: number) => formatDailyValue(indicator, v)
  const q = p.quality
  const qualityLevel = q.total === 0 ? 'missing' : q.reliable / q.total >= 0.85 ? 'good' : q.reliable / q.total >= 0.6 ? 'uncertain' : 'poor'
  const t = p.trend
  const arrow = t.position === 'above' ? '↑' : t.position === 'below' ? '↓' : '→'
  return (
    <div className="pillars" role="group" aria-label="Data quality, personal baseline and trend">
      <div className="pillar">
        <PillarHead n={1} label="Data quality" onExplain={() => onExplain('quality')} />
        <p className="pillar-value">
          <QualityGlyph quality={qualityLevel} size={12} /> {q.reliable}/{q.total} <span className="pillar-unit">days reliable</span>
        </p>
        <p className="pillar-note">
          {isPastView() ? 'That day' : 'Today'}: {q.latestQuality ? QUALITY_LABEL[q.latestQuality].toLowerCase() : 'no reading'}
          {q.uncertainDays ? ` · ${q.uncertainDays} uncertain` : ''}
          {q.missingDays ? ` · ${q.missingDays} missing` : ''}
        </p>
      </div>
      <div className="pillar">
        <PillarHead n={2} label="Personal baseline" onExplain={() => onExplain('baseline')} />
        {p.baseline ? (
          <>
            <p className="pillar-value">
              {f(p.baseline.low)}–{f(p.baseline.high)} <span className="pillar-unit">{unit}</span>
            </p>
            <p className="pillar-note">
              Your usual range · days {p.baseline.fromDay}–{p.baseline.toDay}
            </p>
          </>
        ) : (
          <>
            <p className="pillar-value muted">Building</p>
            <p className="pillar-note">Not enough reliable days yet</p>
          </>
        )}
      </div>
      <div className={`pillar${t.sustained ? ' is-attention' : ''}`}>
        <PillarHead n={3} label="Trend" onExplain={() => onExplain('trend')} />
        {t.position === null ? (
          <>
            <p className="pillar-value muted">—</p>
            <p className="pillar-note">Needs a baseline first</p>
          </>
        ) : t.position === 'within' ? (
          <>
            <p className="pillar-value">
              {arrow} <span className="pillar-unit">within usual</span>
            </p>
            <p className="pillar-note">No sustained change</p>
          </>
        ) : (
          <>
            <p className="pillar-value">
              {arrow} {t.delta !== null ? `${t.delta > 0 ? '+' : ''}${f(t.delta)}` : ''} <span className="pillar-unit">{unit} vs usual</span>
            </p>
            <p className="pillar-note">
              {t.streakDays} {t.streakDays === 1 ? 'day' : 'days'} {t.position} usual · {t.sustained ? 'sustained' : 'not sustained yet'}
            </p>
          </>
        )}
      </div>
    </div>
  )
}

function PillarHead({ n, label, onExplain }: { n: number; label: string; onExplain: () => void }) {
  return (
    <span className="pillar-head">
      <span className="pillar-n" aria-hidden="true">
        {n}
      </span>
      {label}
      <button type="button" className="info-button" onClick={onExplain} aria-label={`How ${label.toLowerCase()} is computed`}>
        i
      </button>
    </span>
  )
}
