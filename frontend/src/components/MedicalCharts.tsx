import { useState } from 'react'
import type { CheckIn, DailyIndicatorId, DailyIndicatorSeries, QualityFlag } from '../domain/types'
import { DAILY_INDICATORS, QUALITY_LABEL, formatDailyValue } from '../domain/parameters'
import { deviationsOf, type LatestCell } from '../domain/deviation'
import type { BackendEvaluation } from '../domain/metricCatalog'
import { formatNutrient, type NutrientProgress } from '../domain/nutrition'
import { formatDate } from '../domain/time'
import { useBoxSize } from '../hooks/useLayout'
import { MetricGlyph } from './MetricGlyph'
import { QualityGlyph } from './StatusGlyphs'
import { toneOf } from './tone'

/**
 * Technical charts for the medical team. Every value is placed against the
 * astronaut's own usual range ("range units": ±1 = edge of the usual range),
 * never against a clinical threshold. Colour is backed by numbers and signs.
 */

export const MATRIX_INDICATORS: { id: DailyIndicatorId; short: string; label: string }[] = [
  { id: 'resting_hr', short: 'HR', label: 'Resting HR' },
  { id: 'hrv_rmssd', short: 'HRV', label: 'HRV' },
  { id: 'bp_systolic', short: 'SBP', label: 'Systolic BP' },
  { id: 'bp_diastolic', short: 'DBP', label: 'Diastolic BP' },
  { id: 'resting_spo2', short: 'SpO₂', label: 'SpO₂' },
  { id: 'resting_resp_rate', short: 'RR', label: 'Resp. rate' },
  { id: 'body_temperature', short: 'Temp', label: 'Temperature' },
  { id: 'sleep_duration', short: 'Sleep', label: 'Sleep' },
  { id: 'sleep_efficiency', short: 'Eff.', label: 'Sleep eff.' },
  { id: 'activity_minutes', short: 'Exer.', label: 'Exercise' },
  { id: 'active_energy', short: 'kcal', label: 'Active energy' },
  { id: 'body_mass', short: 'Mass', label: 'Body mass' },
]

/** 0: within, 1: outside (1–2 range units), 2: far (> 2), null: unknown. */
export function bucketOf(units: number | null): 0 | 1 | 2 | null {
  if (units === null) return null
  const a = Math.abs(units)
  return a <= 1 ? 0 : a <= 2 ? 1 : 2
}

const fmtUnits = (u: number) => `${u > 0 ? '+' : ''}${u.toFixed(1)}`

/* ------------------------------------------------------------------ */
/* Crew status matrix                                                  */
/* ------------------------------------------------------------------ */

export function StatusMatrix({
  rows,
  onOpen,
}: {
  rows: { id: string; name: string; cells: LatestCell[] }[]
  onOpen: (crewId: string, indicator: DailyIndicatorId) => void
}) {
  return (
    <div className="matrix-wrap">
      <table className="matrix">
        <colgroup>
          <col className="matrix-namecol" />
          {MATRIX_INDICATORS.map((m) => (
            <col key={m.id} />
          ))}
        </colgroup>
        <caption className="sr-only">Latest reliable value of each indicator, against each astronaut's own usual range</caption>
        <thead>
          <tr>
            <th scope="col" className="matrix-corner">
              <span className="sr-only">Astronaut</span>
            </th>
            {MATRIX_INDICATORS.map((m) => (
              <th key={m.id} scope="col" title={DAILY_INDICATORS[m.id].label}>
                <span className={`matrix-head tone-${toneOf(m.id)}`}>{m.short}</span>
                <span className="matrix-unit">{DAILY_INDICATORS[m.id].unit.replace(' RMSSD', '')}</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row">{r.name}</th>
              {MATRIX_INDICATORS.map((m) => {
                const c = r.cells.find((x) => x.indicator === m.id)
                const b = bucketOf(c?.units ?? null)
                const label = !c || c.value === null
                  ? `${DAILY_INDICATORS[m.id].label}: no reading`
                  : `${DAILY_INDICATORS[m.id].label}: ${formatDailyValue(m.id, c.value)} ${DAILY_INDICATORS[m.id].unit}, day ${c.missionDay}${c.units !== null ? `, ${fmtUnits(c.units)} range units` : ', no usual range yet'}${c.streak > 1 ? `, outside for ${c.streak} days` : ''}${c.quality !== 'good' ? `, quality ${QUALITY_LABEL[c.quality].toLowerCase()}` : ''}`
                return (
                  <td key={m.id}>
                    <button type="button" className={`cell${b === null ? ' is-none' : ` b-${b}`}`} title={label} aria-label={label} onClick={() => onOpen(r.id, m.id)}>
                      {!c || c.value === null ? (
                        <span className="cell-none">—</span>
                      ) : (
                        <>
                          <span className="cell-value">
                            {b !== null && b > 0 && <span aria-hidden="true">{(c.units ?? 0) > 0 ? '↑' : '↓'}</span>}
                            {formatDailyValue(m.id, c.value)}
                          </span>
                          <span className="cell-sub">
                            {c.quality !== 'good' ? <QualityGlyph quality={c.quality} size={9} /> : null}
                            {c.units !== null ? fmtUnits(c.units) : 'no range'}
                            {c.streak > 1 ? ` · ${c.streak}d` : ''}
                          </span>
                        </>
                      )}
                    </button>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <ul className="legend matrix-legend">
        <li>
          <span className="cell-swatch b-0" /> within usual range (±1)
        </li>
        <li>
          <span className="cell-swatch b-1" /> outside (1–2)
        </li>
        <li>
          <span className="cell-swatch b-2" /> far outside (&gt; 2)
        </li>
        <li className="muted">Second line: range units · consecutive days outside</li>
      </ul>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Data completeness map                                               */
/* ------------------------------------------------------------------ */

export function CompletenessMap({ rows }: { rows: { id: string; name: string; days: { missionDay: number; date: string | null; share: number | null; reliable: number; total: number }[] }[] }) {
  const days = rows[0]?.days ?? []
  return (
    <div className="cmap">
      <div className="cmap-scroll">
      <table className="cmap-table">
        <caption className="sr-only">Share of each astronaut's indicators with a reliable reading, per mission day</caption>
        <thead>
          <tr>
            <th scope="col">
              <span className="sr-only">Astronaut</span>
            </th>
            {days.map((d, i) => (
              <th key={d.missionDay} scope="col" className="cmap-day">
                {i % 3 === 0 || i === days.length - 1 ? d.missionDay : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <th scope="row">{r.name}</th>
              {r.days.map((d) => {
                const level = d.share === null ? 'none' : d.share >= 0.999 ? 'full' : d.share >= 0.66 ? 'most' : d.share > 0 ? 'some' : 'zero'
                const t = `Day ${d.missionDay}${d.date ? ` (${formatDate(d.date)})` : ''}: ${d.reliable} of ${d.total} indicators reliable`
                return (
                  <td key={d.missionDay}>
                    <span className={`cmap-cell is-${level}`} title={t} role="img" aria-label={t} />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      <ul className="legend">
        <li>
          <span className="cmap-cell is-full" /> all
        </li>
        <li>
          <span className="cmap-cell is-most" /> most
        </li>
        <li>
          <span className="cmap-cell is-some" /> some
        </li>
        <li>
          <span className="cmap-cell is-zero" /> none reliable
        </li>
        <li className="muted">Mission day · indicators the astronaut uses</li>
      </ul>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Daily deviation from the usual range + quality strip                */
/* ------------------------------------------------------------------ */

const Q_CLASS: Record<QualityFlag, string> = { good: 'q-good', uncertain: 'q-uncertain', poor: 'q-poor', missing: 'q-missing' }

export function DeviationChart({ series, height = 120 }: { series: DailyIndicatorSeries; height?: number }) {
  const [ref, size] = useBoxSize<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const days = deviationsOf(series)
  const w = Math.max(200, size.width)
  const M = { left: 34, right: 10, top: 8, bottom: 30 }
  const plotW = w - M.left - M.right
  const stripH = 8
  const plotH = Math.max(40, height - M.top - M.bottom - stripH - 6)
  const lim = 3
  const y = (u: number) => M.top + ((lim - Math.max(-lim, Math.min(lim, u))) / (2 * lim)) * plotH
  const step = plotW / Math.max(1, days.length)
  const x = (i: number) => M.left + step * i + step / 2
  const bw = Math.max(2, Math.min(16, step * 0.6))
  const h = hover !== null ? days[hover] : null
  const unit = DAILY_INDICATORS[series.indicator].unit
  return (
    <div className="devchart" ref={ref}>
      {size.width > 0 && (
        <svg width={w} height={height} role="img" aria-label={`${DAILY_INDICATORS[series.indicator].label}: daily distance from the usual range, and data quality per day`}>
          <rect x={M.left} y={y(1)} width={plotW} height={y(-1) - y(1)} className="dev-band" />
          {(plotH < 110 ? [-2, 0, 2] : [-2, -1, 0, 1, 2]).map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + plotW} y1={y(v)} y2={y(v)} className={v === 0 ? 'dev-zero' : 'grid'} />
              <text x={M.left - 6} y={y(v) + 3.5} className="tick" textAnchor="end">
                {v > 0 ? `+${v}` : v}
              </text>
            </g>
          ))}
          {days.map((d, i) =>
            d.units === null ? null : (
              <rect
                key={d.missionDay}
                x={x(i) - bw / 2}
                y={Math.min(y(0), y(d.units))}
                width={bw}
                height={Math.max(1.5, Math.abs(y(d.units) - y(0)))}
                rx={1.5}
                className={`dev-bar b-${bucketOf(d.units)}${d.quality !== 'good' ? ' is-unreliable' : ''}${hover === i ? ' is-hover' : ''}`}
              />
            ),
          )}
          {days.map((d, i) => (
            <rect key={`q${d.missionDay}`} x={x(i) - step / 2 + 0.5} y={M.top + plotH + 6} width={Math.max(1, step - 1)} height={stripH} className={`qstrip ${Q_CLASS[d.quality]}`} />
          ))}
          {days.map((d, i) =>
            i % Math.ceil(days.length / 10) === 0 || i === days.length - 1 ? (
              <text key={`t${d.missionDay}`} x={x(i)} y={height - 6} className="tick" textAnchor="middle">
                {d.missionDay}
              </text>
            ) : null,
          )}
          <rect
            x={M.left}
            y={M.top}
            width={plotW}
            height={plotH + stripH + 6}
            fill="transparent"
            onMouseMove={(e) => {
              const r = (e.target as SVGRectElement).getBoundingClientRect()
              setHover(Math.max(0, Math.min(days.length - 1, Math.floor(((e.clientX - r.left) / r.width) * days.length))))
            }}
            onMouseLeave={() => setHover(null)}
          />
        </svg>
      )}
      <p className="devchart-read" aria-live="polite">
        {h ? (
          <>
            <strong>Day {h.missionDay}</strong> · {h.value === null ? 'no reading' : `${formatDailyValue(series.indicator, h.value)} ${unit}`}
            {h.units !== null ? ` · ${fmtUnits(h.units)} range units` : ''} · quality {QUALITY_LABEL[h.quality].toLowerCase()}
          </>
        ) : (
          <span className="muted">Bars: distance from the usual median in range units (±1 = edge of the usual range). Strip: data quality per day. Hover a day for values.</span>
        )}
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Evaluations timeline (backend engines)                              */
/* ------------------------------------------------------------------ */

const DOMAINS: { id: string; label: string }[] = [
  { id: 'vital_signs', label: 'Vital signs' },
  { id: 'sleep', label: 'Sleep' },
  { id: 'physical_activity', label: 'Activity' },
  { id: 'nutrition', label: 'Nutrition' },
]

export function EvaluationTimeline({ items, nowIso, selected, onSelect }: { items: BackendEvaluation[]; nowIso: string; selected: string | null; onSelect: (id: string) => void }) {
  const [ref, size] = useBoxSize<HTMLDivElement>()
  if (!items.length) return <p className="list-empty">No evaluation stored on the server for this astronaut.</p>
  const t = (s: string) => Date.parse(s)
  const start = Math.min(...items.map((e) => t(e.window_start)))
  const end = Math.max(t(nowIso), ...items.map((e) => t(e.window_end)))
  const w = Math.max(240, size.width)
  const L = 92
  const rowH = 30
  const x = (ms: number) => L + ((ms - start) / Math.max(1, end - start)) * (w - L - 8)
  const rows = DOMAINS.filter((d) => items.some((e) => e.domain === d.id))
  const height = rows.length * rowH + 24
  const ticks = Array.from({ length: 5 }, (_, i) => start + ((end - start) * i) / 4)
  return (
    <div className="evtl" ref={ref}>
      {size.width > 0 && (
        <svg width={w} height={height} role="group" aria-label="Evaluation windows by area">
          {rows.map((r, i) => (
            <g key={r.id}>
              <text x={0} y={i * rowH + 19} className="evtl-label">
                {r.label}
              </text>
              <line x1={L} x2={w - 8} y1={i * rowH + 15} y2={i * rowH + 15} className="grid" />
              {items
                .filter((e) => e.domain === r.id)
                .sort((a, b) => (a.window_end < b.window_end ? -1 : 1))
                .map((e, k, arr) => {
                  const inset = (arr.length - 1 - k) * 3
                  return (
                    <rect
                      key={e.evaluation_id}
                      x={x(t(e.window_start))}
                      y={i * rowH + 6 + inset}
                      width={Math.max(4, x(t(e.window_end)) - x(t(e.window_start)))}
                      height={Math.max(6, 18 - inset * 2)}
                      rx={4}
                      tabIndex={0}
                      role="button"
                      aria-label={`${r.label}, ${e.status.replace('_', ' ')}, ${formatDate(e.window_start)} to ${formatDate(e.window_end)}`}
                      className={`evtl-bar is-${e.status}${selected === e.evaluation_id ? ' is-selected' : ''}`}
                      onClick={() => onSelect(e.evaluation_id)}
                      onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && onSelect(e.evaluation_id)}
                    >
                      <title>{`${e.status.replace('_', ' ')} · ${formatDate(e.window_start)} → ${formatDate(e.window_end)}`}</title>
                    </rect>
                  )
                })}
            </g>
          ))}
          {ticks.map((ms, i) => (
            <text key={ms} x={x(ms)} y={height - 4} className="tick" textAnchor={i === 0 ? 'start' : i === ticks.length - 1 ? 'end' : 'middle'}>
              {formatDate(new Date(ms).toISOString()).replace(/ \d{4}$/, '')}
            </text>
          ))}
          <line x1={x(t(nowIso))} x2={x(t(nowIso))} y1={0} y2={rows.length * rowH + 4} className="evtl-now" />
        </svg>
      )}
      <ul className="legend">
        <li>
          <span className="evtl-swatch is-nominal" /> nominal
        </li>
        <li>
          <span className="evtl-swatch is-attention" /> attention
        </li>
        <li>
          <span className="evtl-swatch is-insufficient_data" /> insufficient data
        </li>
        <li className="muted">Each bar is the window an evaluation covers; select one for its findings.</li>
      </ul>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Nutrition against NASA requirements (bullet bars)                   */
/* ------------------------------------------------------------------ */

export function NutritionBullets({ items }: { items: NutrientProgress[] }) {
  const max = 1.5
  return (
    <ul className="bullets">
      {items.map((p) => {
        const target = p.req.min ?? p.req.max ?? 0
        const share = target ? p.value / target : 0
        const limitOnly = p.req.min === null
        const over = p.state === 'over'
        const label = `${p.def.label}: ${formatNutrient(p.def.id, p.value)}, ${limitOnly ? 'limit' : 'minimum'} ${formatNutrient(p.def.id, target)}${p.req.max !== null && !limitOnly ? `, maximum ${formatNutrient(p.def.id, p.req.max)}` : ''}`
        return (
          <li key={p.def.id} title={label}>
            <span className="bullet-name">{p.def.label}</span>
            <span className="bullet-track" role="img" aria-label={label}>
              <span className={`bullet-bar${over ? ' is-over' : p.state === 'below' || p.state === 'unknown' ? ' is-below' : ''}${limitOnly ? ' is-limit' : ''}`} style={{ width: `${(Math.min(max, share) / max) * 100}%` }} />
              <span className="bullet-target" style={{ left: `${(1 / max) * 100}%` }} />
              {p.req.max !== null && !limitOnly && p.req.max / target <= max && <span className="bullet-max" style={{ left: `${(p.req.max / target / max) * 100}%` }} />}
            </span>
            <span className={`bullet-value${over ? ' text-attention' : ''}`}>{Math.round(share * 100)}%</span>
          </li>
        )
      })}
    </ul>
  )
}

/* ------------------------------------------------------------------ */
/* Self-reported check-ins                                             */
/* ------------------------------------------------------------------ */

const CHECKIN_LINES: { key: 'sleepQuality' | 'energy' | 'mood'; label: string; cls: string }[] = [
  { key: 'sleepQuality', label: 'Sleep', cls: 'ci-sleep' },
  { key: 'energy', label: 'Energy', cls: 'ci-energy' },
  { key: 'mood', label: 'Mood', cls: 'ci-mood' },
]

export function CheckInChart({ items, lastDay, days = 14 }: { items: CheckIn[]; lastDay: number; days?: number }) {
  const [ref, size] = useBoxSize<HTMLDivElement>()
  const w = Math.max(200, size.width)
  const H = 92
  const M = { left: 18, right: 6, top: 8, bottom: 16 }
  const first = Math.max(1, lastDay - days + 1)
  const x = (d: number) => M.left + ((d - first) / Math.max(1, lastDay - first)) * (w - M.left - M.right)
  const y = (v: number) => M.top + ((5 - v) / 4) * (H - M.top - M.bottom)
  const inRange = items.filter((c) => c.missionDay >= first && c.missionDay <= lastDay).sort((a, b) => a.missionDay - b.missionDay)
  if (!inRange.length) return <p className="list-empty">No check-in in the last {days} days.</p>
  return (
    <div className="cichart" ref={ref}>
      {size.width > 0 && (
        <svg width={w} height={H} role="img" aria-label={`Self-reported sleep, energy and mood, 1 to 5, over the last ${days} days`}>
          {[1, 3, 5].map((v) => (
            <g key={v}>
              <line x1={M.left} x2={w - M.right} y1={y(v)} y2={y(v)} className="grid" />
              <text x={2} y={y(v) + 3.5} className="tick">
                {v}
              </text>
            </g>
          ))}
          {CHECKIN_LINES.map((l) => (
            <g key={l.key} className={l.cls}>
              <polyline fill="none" strokeWidth="1.8" points={inRange.map((c) => `${x(c.missionDay)},${y(c[l.key])}`).join(' ')} />
              {inRange.map((c) => (
                <circle key={c.id} cx={x(c.missionDay)} cy={y(c[l.key])} r={2.6}>
                  <title>{`Day ${c.missionDay} · ${l.label} ${c[l.key]}/5`}</title>
                </circle>
              ))}
            </g>
          ))}
          <text x={M.left} y={H - 3} className="tick">
            Day {first}
          </text>
          <text x={w - M.right} y={H - 3} className="tick" textAnchor="end">
            {lastDay}
          </text>
        </svg>
      )}
      <ul className="legend">
        {CHECKIN_LINES.map((l) => (
          <li key={l.key}>
            <span className={`ci-swatch ${l.cls}`} /> {l.label}
          </li>
        ))}
        <li className="muted">1 worst · 5 best</li>
      </ul>
    </div>
  )
}

/** Small chart card for the trends grid. */
export function IndicatorChip({ cell, selected, onSelect }: { cell: LatestCell; selected: boolean; onSelect: () => void }) {
  const def = DAILY_INDICATORS[cell.indicator]
  const short = MATRIX_INDICATORS.find((m) => m.id === cell.indicator)?.label ?? def.label
  const b = bucketOf(cell.units)
  return (
    <button type="button" className={`ichip tone-${toneOf(cell.indicator)}${selected ? ' is-selected' : ''}${b !== null && b > 0 ? ' is-out' : ''}`} onClick={onSelect} aria-pressed={selected}>
      <span className="ichip-label" title={def.label}>
        <MetricGlyph id={cell.indicator} size={12} /> {short}
      </span>
      <span className="ichip-value">
        {cell.value === null ? '—' : formatDailyValue(cell.indicator, cell.value)} <small>{cell.value === null ? '' : def.unit.replace(' RMSSD', '')}</small>
      </span>
      <span className="ichip-sub">
        {cell.value === null ? 'No readings' : cell.units === null ? 'No usual range' : `${fmtUnits(cell.units)}${cell.streak > 1 ? ` · ${cell.streak} days out` : ''}`}
      </span>
    </button>
  )
}
