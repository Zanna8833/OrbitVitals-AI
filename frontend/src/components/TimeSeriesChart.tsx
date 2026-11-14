import { useId, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import type { ActivitySegment, ReferenceBand, Sample, TimeSeries } from '../domain/types'
import { PARAMETERS, QUALITY_LABEL, REASON_LABEL, formatValue } from '../domain/parameters'
import { findGaps, referenceAt } from '../domain/observations'
import { formatClock, formatUtc, toMs } from '../domain/time'
import { linear, niceDomain, niceTicks, timeTicks } from './chartScale'
import { QualityTag } from './StatusGlyphs'

export interface ChartProps {
  title: string
  series: TimeSeries | undefined
  /** Visible time range (ms). */
  domain: [number, number]
  /** Simulated "now" (ms). Data after the last sample and before now is shown as "no data received". */
  nowMs: number
  sessionStart: string
  activities?: ActivitySegment[]
  band?: ReferenceBand | null
  highlight?: { start: string; end: string } | null
  /** Shared cursor (ms) to compare several charts at the same instant. */
  cursor: number | null
  onCursor: (t: number | null) => void
  plotHeight?: number
  showActivityStrip?: boolean
}

const M = { left: 52, right: 14 }
/** Below this width the chart scrolls rather than squeezing its axis labels. */
const MIN_CHART_WIDTH = 280
/** Minimum y-span per parameter, so that small sensor noise is not visually magnified. */
const MIN_SPAN = { heart_rate: 40, spo2: 10, resp_rate: 16, motion: 0.4 } as const
const ACT_H = 20
const QUAL_H = 6
const AXIS_H = 22

interface Pt {
  t: number
  s: Sample
}

export function TimeSeriesChart(props: ChartProps) {
  const { series, domain, nowMs, band, highlight, cursor, onCursor, sessionStart } = props
  const plotH = props.plotHeight ?? 120
  const showAct = props.showActivityStrip ?? false
  const def = series ? PARAMETERS[series.parameter] : null
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(640)
  const [focused, setFocused] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const uid = useId()
  const hatchId = `hatch-${uid}`

  // Measure before the first paint (no flash of a too-wide chart on small
  // screens), then follow container resizes.
  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const fit = (w: number) => setWidth(Math.max(MIN_CHART_WIDTH, Math.floor(w)))
    fit(el.clientWidth)
    const ro = new ResizeObserver((entries) => fit(entries[0].contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const pts: Pt[] = useMemo(
    () =>
      (series?.samples ?? [])
        .map((s) => ({ t: toMs(s.t), s }))
        .filter((p) => p.t >= domain[0] && p.t <= domain[1]),
    [series, domain],
  )

  const step = (series?.source.samplingIntervalS ?? 10) * 1000
  const sessionStartMs = toMs(sessionStart)

  const bandPts = useMemo(() => {
    if (!band) return []
    return band.points
      .map((p) => ({ t: sessionStartMs + p.offsetS * 1000, low: p.low, high: p.high }))
      .filter((p) => p.t >= domain[0] - 60000 && p.t <= domain[1] + 60000)
  }, [band, sessionStartMs, domain])

  const param = series?.parameter
  // y domain from visible values and band
  const [y0, y1] = useMemo(() => {
    const vals: number[] = []
    for (const p of pts) if (p.s.value !== null) vals.push(p.s.value)
    for (const b of bandPts) vals.push(b.low, b.high)
    if (!vals.length) return [0, 1]
    let lo = Math.min(...vals)
    let hi = Math.max(...vals)
    const pad = Math.max((hi - lo) * 0.08, param === 'motion' ? 0.02 : 1)
    lo -= pad
    hi += pad
    const minSpan = param ? MIN_SPAN[param] : 1
    if (hi - lo < minSpan) {
      const c = (hi + lo) / 2
      lo = c - minSpan / 2
      hi = c + minSpan / 2
    }
    if (param === 'spo2' && hi > 100) {
      lo -= hi - 100
      hi = 100
    }
    if (param === 'motion') lo = Math.max(lo, 0)
    return niceDomain(lo, hi, 5)
  }, [pts, bandPts, param])

  const top = showAct ? ACT_H + 4 : 6
  const plotW = width - M.left - M.right
  const x = linear(domain[0], domain[1], M.left, M.left + plotW)
  const y = linear(y0, y1, top + plotH, top)
  const qualTop = top + plotH + 4
  const axisTop = qualTop + QUAL_H + 2
  const totalH = axisTop + AXIS_H

  // line segments split by quality and by gaps
  const { goodPath, otherPath } = useMemo(() => {
    let good = ''
    let other = ''
    for (let i = 1; i < pts.length; i++) {
      const a = pts[i - 1]
      const b = pts[i]
      if (a.s.value === null || b.s.value === null || b.t - a.t > step * 1.5) continue
      const seg = `M${x(a.t).toFixed(1)},${y(a.s.value).toFixed(1)}L${x(b.t).toFixed(1)},${y(b.s.value).toFixed(1)}`
      if (a.s.quality === 'good' && b.s.quality === 'good') good += seg
      else other += seg
    }
    return { goodPath: good, otherPath: other }
    // x/y are derived from the deps below
  }, [pts, step, domain, y0, y1, width, plotH, top]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Consecutive samples with the same quality, drawn as one block in the quality strip. */
  const qualityRuns = useMemo(() => {
    const runs: { from: number; to: number; q: Sample['quality'] }[] = []
    for (const p of pts) {
      const last = runs[runs.length - 1]
      if (last && last.q === p.s.quality && p.t - last.to <= step * 1.5) last.to = p.t
      else runs.push({ from: p.t, to: p.t, q: p.s.quality })
    }
    return runs
  }, [pts, step])

  const gaps = useMemo(() => {
    const until = Math.min(domain[1], nowMs)
    const visible = series?.samples.filter((s) => toMs(s.t) <= until) ?? []
    return findGaps(visible, step / 1000, new Date(until).toISOString()).filter((g) => toMs(g.end) >= domain[0])
  }, [series, step, domain, nowMs])

  const bandPath = useMemo(() => {
    if (bandPts.length < 2) return ''
    const upper = bandPts.map((p, i) => `${i ? 'L' : 'M'}${x(p.t).toFixed(1)},${y(p.high).toFixed(1)}`).join('')
    const lower = [...bandPts].reverse().map((p) => `L${x(p.t).toFixed(1)},${y(p.low).toFixed(1)}`).join('')
    return `${upper}${lower}Z`
  }, [bandPts, domain, y0, y1, width, plotH, top]) // eslint-disable-line react-hooks/exhaustive-deps

  const cursorPt = useMemo(() => {
    if (cursor === null || cursor < domain[0] || cursor > domain[1]) return null
    let best: Pt | null = null
    for (const p of pts) if (!best || Math.abs(p.t - cursor) < Math.abs(best.t - cursor)) best = p
    if (best && Math.abs(best.t - cursor) <= step * 1.5) return best
    return null
  }, [cursor, pts, domain, step])

  const activityAtCursor = cursor !== null ? props.activities?.find((a) => toMs(a.start) <= cursor && toMs(a.end) > cursor) : undefined
  const refAtCursor = band && cursor !== null ? referenceAt(band, sessionStart, new Date(cursor).toISOString()) : null

  const onMove = (e: MouseEvent<SVGRectElement>) => {
    const rect = (e.currentTarget.ownerSVGElement as SVGSVGElement).getBoundingClientRect()
    const px = e.clientX - rect.left
    const t = domain[0] + ((px - M.left) / plotW) * (domain[1] - domain[0])
    onCursor(Math.max(domain[0], Math.min(domain[1], t)))
  }

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!pts.length) return
    const idx = cursorPt ? pts.indexOf(cursorPt) : pts.length - 1
    let next: number | null = null
    if (e.key === 'ArrowLeft') next = Math.max(0, idx - (e.shiftKey ? 6 : 1))
    else if (e.key === 'ArrowRight') next = Math.min(pts.length - 1, idx + (e.shiftKey ? 6 : 1))
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = pts.length - 1
    else if (e.key === 'Escape') {
      onCursor(null)
      return
    }
    if (next !== null) {
      e.preventDefault()
      onCursor(pts[next].t)
    }
  }

  const unit = def?.unit ?? ''
  const lastPt = [...pts].reverse().find((p) => p.s.value !== null)
  const ariaSummary = def
    ? `${props.title}, in ${unit}. ${pts.length} samples between ${formatUtc(domain[0], false)} and ${formatUtc(domain[1], false)}. ` +
      (lastPt ? `Last value ${formatValue(series!.parameter, lastPt.s.value)} ${unit} at ${formatUtc(lastPt.t)}, quality ${QUALITY_LABEL[lastPt.s.quality].toLowerCase()}.` : 'No value available.') +
      ' Use the arrow keys to move through the samples.'
    : `${props.title}: data not available.`

  const tooltipText = cursorPt && def
    ? `${formatUtc(cursorPt.t)}: ${cursorPt.s.value === null ? 'no value' : `${formatValue(series!.parameter, cursorPt.s.value)} ${unit}`}, quality ${QUALITY_LABEL[cursorPt.s.quality].toLowerCase()}`
    : ''

  const yTicks = niceTicks(y0, y1, 5)
  const xTicks = timeTicks(domain[0], domain[1], Math.max(3, Math.floor(plotW / 90)))
  const tipLeft = cursorPt ? x(cursorPt.t) : 0
  const tipOnLeft = tipLeft > width * 0.6

  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <span className="chart-title">{props.title}</span>
        <span className="chart-unit">{unit}</span>
        {series && (
          <span className="chart-source" title={series.source.sensorType}>
            {series.source.deviceLabel} · {series.source.sensorType}
          </span>
        )}
        <button type="button" className="link-button chart-table-toggle" aria-expanded={showTable} onClick={() => setShowTable((v) => !v)}>
          {showTable ? 'Hide table' : 'Data table'}
        </button>
      </figcaption>

      <div
        ref={wrapRef}
        className={`chart-body${focused ? ' is-focused' : ''}`}
        tabIndex={0}
        role="group"
        aria-label={ariaSummary}
        onKeyDown={onKey}
        onFocus={() => {
          setFocused(true)
          if (cursor === null && lastPt) onCursor(lastPt.t)
        }}
        onBlur={() => setFocused(false)}
      >
        <svg width={width} height={totalH} role="img" aria-hidden="true">
          <defs>
            <pattern id={hatchId} patternUnits="userSpaceOnUse" width="6" height="6" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="6" className="hatch-line" strokeWidth="1.5" />
            </pattern>
            <clipPath id={`clip-${uid}`}>
              <rect x={M.left} y={0} width={plotW} height={totalH} />
            </clipPath>
          </defs>

          {/* activity context */}
          {showAct &&
            props.activities?.map((a) => {
              const a0 = Math.max(domain[0], toMs(a.start))
              const a1 = Math.min(domain[1], toMs(a.end))
              if (a1 <= a0) return null
              const w = x(a1) - x(a0)
              return (
                <g key={a.start}>
                  <rect x={x(a0) + 1} y={0} width={Math.max(0, w - 2)} height={ACT_H} className={`act act-${a.kind}`} />
                  {w > a.label.length * 6.2 + 12 ? (
                    <text x={x(a0) + 7} y={14} className="act-label">
                      {a.label}
                    </text>
                  ) : w > 40 ? (
                    <text x={x(a0) + 7} y={14} className="act-label">
                      {a.label.slice(0, Math.floor((w - 16) / 6.4))}…
                    </text>
                  ) : null}
                </g>
              )
            })}

          {/* grid */}
          {yTicks.map((v) => (
            <g key={v}>
              <line x1={M.left} x2={M.left + plotW} y1={y(v)} y2={y(v)} className="grid" />
              <text x={M.left - 8} y={y(v) + 4} className="tick" textAnchor="end">
                {series?.parameter === 'motion' ? v.toFixed(2) : v}
              </text>
            </g>
          ))}

          {/* event window */}
          {highlight && (
            <rect
              x={x(Math.max(domain[0], toMs(highlight.start)))}
              y={top}
              width={Math.max(0, x(Math.min(domain[1], toMs(highlight.end))) - x(Math.max(domain[0], toMs(highlight.start))))}
              height={plotH}
              className="highlight"
            />
          )}

          {/* personal historical band */}
          {bandPath && <path d={bandPath} className="band" clipPath={`url(#clip-${uid})`} />}

          {/* missing data */}
          {gaps.map((g) => {
            const g0 = Math.max(domain[0], toMs(g.start) - step / 2)
            const g1 = Math.min(domain[1], toMs(g.end) + step / 2)
            const w = x(g1) - x(g0)
            return (
              <g key={g.start}>
                <rect x={x(g0)} y={top} width={Math.max(1, w)} height={plotH} fill={`url(#${hatchId})`} className="gap" />
                {w > 70 && (
                  <text x={x(g0) + w / 2} y={top + 14} className="gap-label" textAnchor="middle">
                    No data
                  </text>
                )}
              </g>
            )
          })}

          {/* series */}
          <g clipPath={`url(#clip-${uid})`}>
            <path d={otherPath} className="line line-uncertain" />
            <path d={goodPath} className="line" />
          </g>
          {pts
            .filter((p) => p.s.value !== null && p.s.quality !== 'good')
            .map((p) => (
              <circle key={p.t} cx={x(p.t)} cy={y(p.s.value as number)} r={4} className={`mark-uncertain q-${p.s.quality}`} />
            ))}

          {/* quality strip */}
          <g clipPath={`url(#clip-${uid})`}>
            {qualityRuns.map((r) => (
              <rect key={r.from} x={x(r.from - step / 2)} y={qualTop} width={Math.max(1.5, x(r.to + step / 2) - x(r.from - step / 2))} height={QUAL_H} className={`qstrip qs-${r.q}`} />
            ))}
          </g>
          {gaps.map((g) => {
            const g0 = Math.max(domain[0], toMs(g.start) - step / 2)
            const g1 = Math.min(domain[1], toMs(g.end) + step / 2)
            return <rect key={`q${g.start}`} x={x(g0)} y={qualTop} width={Math.max(1, x(g1) - x(g0))} height={QUAL_H} fill={`url(#${hatchId})`} className="qstrip qs-gap" />
          })}

          {/* now marker */}
          {nowMs >= domain[0] && nowMs <= domain[1] && (
            <g>
              <line x1={x(nowMs)} x2={x(nowMs)} y1={top} y2={qualTop + QUAL_H} className="now-line" />
            </g>
          )}

          {/* x axis */}
          <line x1={M.left} x2={M.left + plotW} y1={top + plotH} y2={top + plotH} className="axis" />
          {xTicks.map((t) => (
            <text key={t} x={x(t)} y={axisTop + 13} className="tick" textAnchor="middle">
              {formatClock(t, false)}
            </text>
          ))}
          <text x={M.left - 20} y={axisTop + 13} className="tick tick-utc" textAnchor="end">
            UTC
          </text>

          {/* cursor */}
          {cursorPt && (
            <g pointerEvents="none">
              <line x1={x(cursorPt.t)} x2={x(cursorPt.t)} y1={top} y2={top + plotH} className="cursor-line" />
              {cursorPt.s.value !== null && <circle cx={x(cursorPt.t)} cy={y(cursorPt.s.value)} r={4.5} className="cursor-dot" />}
            </g>
          )}

          <rect
            x={M.left}
            y={0}
            width={plotW}
            height={axisTop}
            fill="transparent"
            onMouseMove={onMove}
            onMouseLeave={() => onCursor(null)}
          />
        </svg>

        {cursorPt && def && (
          <div className="tooltip" style={tipOnLeft ? { right: width - tipLeft + 10 } : { left: tipLeft + 10 }} aria-hidden="true">
            <div className="tt-time">{formatUtc(cursorPt.t)}</div>
            <div className="tt-value">
              {cursorPt.s.value === null ? (
                'No value'
              ) : (
                <>
                  <strong>{formatValue(series!.parameter, cursorPt.s.value)}</strong> {unit}
                </>
              )}
            </div>
            <QualityTag quality={cursorPt.s.quality} />
            {cursorPt.s.reasons?.length ? <div className="tt-muted">{cursorPt.s.reasons.map((r) => REASON_LABEL[r]).join('; ')}</div> : null}
            {refAtCursor && (
              <div className="tt-muted">
                Personal history: {formatValue(series!.parameter, refAtCursor.low)}–{formatValue(series!.parameter, refAtCursor.high)} {unit}
              </div>
            )}
            {activityAtCursor && <div className="tt-muted">Activity: {activityAtCursor.label}</div>}
          </div>
        )}
        <div className="sr-only" aria-live="polite">
          {focused ? tooltipText : ''}
        </div>
      </div>

      {showTable && series && (
        <div className="table-scroll">
          <table className="data-table">
            <caption className="sr-only">{props.title}: samples in the displayed range</caption>
            <thead>
              <tr>
                <th scope="col">Acquired (UTC)</th>
                <th scope="col" className="num">
                  Value ({unit})
                </th>
                <th scope="col">Quality</th>
                <th scope="col">Reason</th>
              </tr>
            </thead>
            <tbody>
              {pts.map((p) => (
                <tr key={p.t}>
                  <td className="num">{formatClock(p.t)}</td>
                  <td className="num">{formatValue(series.parameter, p.s.value)}</td>
                  <td>{QUALITY_LABEL[p.s.quality]}</td>
                  <td>{p.s.reasons?.map((r) => REASON_LABEL[r]).join('; ') ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  )
}

/** Shared key for the chart encodings (single series per chart, so no colour legend is needed). */
export function ChartLegend({ showBand, showHighlight }: { showBand: boolean; showHighlight?: boolean }) {
  return (
    <ul className="chart-legend" aria-label="Chart legend">
      <li>
        <svg width="22" height="10" aria-hidden="true">
          <line x1="1" x2="21" y1="5" y2="5" className="line" />
        </svg>
        Measured value, good quality
      </li>
      <li>
        <svg width="22" height="12" aria-hidden="true">
          <line x1="1" x2="21" y1="6" y2="6" className="line line-uncertain" />
          <circle cx="11" cy="6" r="4" className="mark-uncertain q-uncertain" />
        </svg>
        Uncertain-quality sample
      </li>
      <li>
        <svg width="22" height="12" aria-hidden="true">
          <line x1="1" x2="21" y1="6" y2="6" className="line line-uncertain" />
          <circle cx="11" cy="6" r="4" className="mark-uncertain q-poor" />
        </svg>
        Poor-quality sample
      </li>
      <li>
        <svg width="22" height="10" aria-hidden="true">
          <rect x="1" y="0" width="20" height="10" className="legend-hatch" />
        </svg>
        No data received
      </li>
      {showBand && (
        <li>
          <svg width="22" height="10" aria-hidden="true">
            <rect x="1" y="0" width="20" height="10" className="band" />
          </svg>
          Personal historical range (P10–P90, previous sessions)
        </li>
      )}
      {showHighlight && (
        <li>
          <svg width="22" height="10" aria-hidden="true">
            <rect x="1" y="0" width="20" height="10" className="highlight" />
          </svg>
          Event window
        </li>
      )}
      <li>
        <svg width="22" height="10" aria-hidden="true">
          <line x1="11" x2="11" y1="0" y2="10" className="now-line" />
        </svg>
        Simulated now
      </li>
      <li className="legend-note legend-strip">
        Strip below each chart, quality of every sample (simulated flag):
        {(['good', 'uncertain', 'poor', 'missing'] as const).map((q) => (
          <span key={q}>
            <svg width="14" height="8" aria-hidden="true">
              <rect x="0" y="1" width="14" height="6" className={`qstrip qs-${q}`} />
            </svg>
            {QUALITY_LABEL[q]}
          </span>
        ))}
      </li>
    </ul>
  )
}
