import { type CSSProperties, useId, useLayoutEffect, useRef, useState, type KeyboardEvent } from 'react'
import type { DailyIndicatorId, DailyIndicatorSeries, DailyValue } from '../domain/types'
import { DAILY_INDICATORS, QUALITY_LABEL, formatDailyValue } from '../domain/parameters'
import { linear, niceDomain, niceTicks } from './chartScale'

/** Smallest visible y-span per indicator, so small day-to-day noise is not magnified. */
const MIN_SPAN: Record<DailyIndicatorId, number> = {
  resting_hr: 14, sleep_duration: 2.5, resting_spo2: 5, resting_resp_rate: 6,
  hrv_rmssd: 22, bp_systolic: 24, bp_diastolic: 16, body_temperature: 1.8,
  activity_minutes: 48, body_mass: 2, sleep_efficiency: 18, active_energy: 300,
}
/** `top` leaves a strip above the plot for labels, so text never sits on the data. */
const M = { left: 40, right: 52, top: 22, bottom: 24 }

/**
 * One indicator over the mission days, against the person's own usual range
 * (shaded). Single series: the title names it, so no legend box. Uncertain
 * readings are hollow orange rings; missing days break the line. A data table
 * is available, and the summary is exposed to screen readers.
 */
export function DailyTrendChart({ series, height = 132, mini = false }: { series: DailyIndicatorSeries; height?: number; mini?: boolean }) {
  const def = DAILY_INDICATORS[series.indicator]
  const margin = mini ? { left: 8, right: 9, top: 9, bottom: 6 } : M
  const wrapRef = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(320)
  const [showTable, setShowTable] = useState(false)
  const [hover, setHover] = useState<number | null>(null)
  const uid = useId()

  useLayoutEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const fit = (w: number) => setWidth(Math.max(160, Math.floor(w)))
    fit(el.clientWidth)
    const ro = new ResizeObserver((entries) => fit(entries[0].contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const days = series.days
  const valid = days.filter((d): d is DailyValue & { value: number } => d.value !== null)
  const base = series.baseline
  const firstDay = days[0]?.missionDay ?? 1
  const lastDay = days[days.length - 1]?.missionDay ?? 1

  const vals = valid.map((d) => d.value)
  if (base) vals.push(base.low, base.high)
  let lo = vals.length ? Math.min(...vals) : 0
  let hi = vals.length ? Math.max(...vals) : 1
  const minSpan = MIN_SPAN[series.indicator]
  if (hi - lo < minSpan) {
    const c = (hi + lo) / 2
    lo = c - minSpan / 2
    hi = c + minSpan / 2
  }
  if ((series.indicator === 'resting_spo2' || series.indicator === 'sleep_efficiency') && hi > 100) {
    lo -= hi - 100
    hi = 100
  }
  const [y0, y1] = niceDomain(lo, hi, 3)
  const plotW = width - margin.left - margin.right
  const plotH = height - margin.top - margin.bottom
  const x = linear(firstDay, Math.max(lastDay, firstDay + 1), margin.left, margin.left + plotW)
  const y = linear(y0, y1, margin.top + plotH, margin.top)

  // Contiguous runs of valid days (a missing day breaks the line — never interpolated).
  const runs: { day: number; value: number }[][] = []
  for (const d of days) {
    if (d.value === null) {
      runs.push([])
      continue
    }
    if (!runs.length) runs.push([])
    runs[runs.length - 1].push({ day: d.missionDay, value: d.value })
  }
  const segments = runs.filter((r) => r.length > 0)
  /** Monotone cubic curve through the points: smooth, but never overshoots a reading. */
  const smooth = (pts: { x: number; y: number }[]) => {
    if (pts.length < 3 || mini) return pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join('')
    const n = pts.length
    const dx = pts.slice(1).map((p, i) => p.x - pts[i].x)
    const m = pts.slice(1).map((p, i) => (p.y - pts[i].y) / dx[i])
    const t = pts.map((_, i) => (i === 0 ? m[0] : i === n - 1 ? m[n - 2] : m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2))
    let d = `M${pts[0].x.toFixed(1)},${pts[0].y.toFixed(1)}`
    for (let i = 0; i < n - 1; i++) {
      const h = dx[i] / 3
      d += `C${(pts[i].x + h).toFixed(1)},${(pts[i].y + t[i] * h).toFixed(1)} ${(pts[i + 1].x - h).toFixed(1)},${(pts[i + 1].y - t[i + 1] * h).toFixed(1)} ${pts[i + 1].x.toFixed(1)},${pts[i + 1].y.toFixed(1)}`
    }
    return d
  }
  const segPts = segments.map((seg) => seg.map((p) => ({ x: x(p.day), y: y(p.value) })))
  const path = segPts.map((p) => (p.length === 1 ? `M${p[0].x},${p[0].y}h0.01` : smooth(p))).join('')
  const bottom = margin.top + plotH
  const area = segPts
    .filter((p) => p.length > 1)
    .map((p) => `${smooth(p)}L${p[p.length - 1].x.toFixed(1)},${bottom}L${p[0].x.toFixed(1)},${bottom}Z`)
    .join('')

  // The current change: the latest consecutive days on the same side of the usual range.
  let streak: { from: number; to: number; side: 'above' | 'below' } | null = null
  if (base) {
    const good = days.filter((d) => d.value !== null && d.quality === 'good') as (DailyValue & { value: number })[]
    const side = (v: number) => (v > base.high ? 'above' : v < base.low ? 'below' : null)
    const last = good[good.length - 1]
    const s0 = last ? side(last.value) : null
    if (last && s0) {
      let i = good.length - 1
      while (i > 0 && side(good[i - 1].value) === s0) i--
      if (good.length - i >= 3) streak = { from: good[i].missionDay, to: last.missionDay, side: s0 }
    }
  }

  const latest = valid[valid.length - 1]
  const dayStep = plotW / Math.max(1, lastDay - firstDay)
  const tickEvery = dayStep >= 34 ? 1 : dayStep >= 18 ? 2 : 3
  const xTicks = days.map((d) => d.missionDay).filter((d) => (d - firstDay) % tickEvery === 0 || d === lastDay)
  const unit = def.unit
  const summary =
    `${def.label} (${def.when}), mission days ${firstDay}–${lastDay}.` +
    (latest ? ` Latest ${formatDailyValue(series.indicator, latest.value)} ${unit} on day ${latest.missionDay}.` : ' No readings.') +
    (base ? ` Usual range ${formatDailyValue(series.indicator, base.low)}–${formatDailyValue(series.indicator, base.high)} ${unit}.` : '')

  const missing = days.filter((d) => d.value === null)
  // Y labels at least 16 px apart: on a short chart only the bottom and top remain.
  const allYTicks = niceTicks(y0, y1, 3)
  const yTicks =
    plotH < 28 ? allYTicks.slice(-1) : allYTicks.length > 2 && plotH / (allYTicks.length - 1) < 16 ? [allYTicks[0], allYTicks[allYTicks.length - 1]] : allYTicks
  // Label placement: nothing overlaps (≈6 px per character at 11 px).
  const streakText = streak ? `${streak.to - streak.from + 1} days ${streak.side} usual` : ''
  const baselineTextEnd = base ? Math.max(margin.left + 2, x(base.fromDay) - dayStep / 2 + 2) + `Baseline days ${base.fromDay}–${base.toDay}`.length * 6 : 0
  const streakTextStart = streak ? x(streak.to) + dayStep / 2 - streakText.length * 6.3 : Infinity
  const showBaselineText = !!base && baselineTextEnd + 8 < streakTextStart
  let usualY: number | null = base ? (y(base.high) + y(base.low)) / 2 + 4 : null
  if (base && latest && usualY !== null && x(latest.missionDay) > margin.left + plotW - dayStep && Math.abs(y(latest.value as number) + 4 - usualY) < 13) {
    // The latest value's label sits there: move "usual" to the band edge farther from it.
    const above = y(base.high) - 4
    const below = y(base.low) + 12
    const pick = Math.abs(above - y(latest.value as number)) > Math.abs(below - y(latest.value as number)) ? above : below
    usualY = pick > margin.top + 4 && pick < margin.top + plotH ? pick : null
  }
  const hovered = hover !== null ? days.find((d) => d.missionDay === hover) ?? null : null
  const pickDay = (clientX: number, el: SVGRectElement) => {
    const r = el.getBoundingClientRect()
    const day = Math.round(firstDay + ((clientX - r.left) / r.width) * (lastDay - firstDay))
    setHover(Math.min(lastDay, Math.max(firstDay, day)))
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (mini) return
    const cur = hover ?? lastDay
    let next: number | null = null
    if (e.key === 'ArrowLeft') next = Math.max(firstDay, cur - 1)
    else if (e.key === 'ArrowRight') next = Math.min(lastDay, cur + 1)
    else if (e.key === 'Home') next = firstDay
    else if (e.key === 'End') next = lastDay
    else if (e.key === 'Escape') setHover(null)
    if (next !== null) {
      e.preventDefault()
      setHover(next)
    }
  }
  const compare = (v: number) => (!base ? null : v > base.high ? 'above your usual range' : v < base.low ? 'below your usual range' : 'within your usual range')

  return (
    <figure className="daily-chart">
      <div
        ref={wrapRef}
        className="daily-chart-body"
        role={mini ? 'img' : 'group'}
        aria-label={mini ? summary : `${summary} Use the arrow keys to read each day.`}
        tabIndex={mini ? undefined : 0}
        onKeyDown={onKey}
        onFocus={() => !mini && hover === null && setHover(lastDay)}
        onBlur={() => setHover(null)}
      >
        <svg width={width} height={height} aria-hidden="true">
          <defs>
            <clipPath id={`dclip-${uid}`}>
              <rect x={margin.left} y={margin.top} width={plotW} height={plotH} />
            </clipPath>
            <pattern id={`dhatch-${uid}`} patternUnits="userSpaceOnUse" width="5" height="5" patternTransform="rotate(45)">
              <line x1="0" y1="0" x2="0" y2="5" className="hatch-line" strokeWidth="1.2" />
            </pattern>
          </defs>
          {!mini && yTicks.map((v) => (
            <g key={v}>
              <line x1={margin.left} x2={margin.left + plotW} y1={y(v)} y2={y(v)} className="grid" />
              <text x={margin.left - 8} y={y(v) + 4} className="tick" textAnchor="end">
                {formatDailyValue(series.indicator, v)}
              </text>
            </g>
          ))}
          {/* Days without a reading: hatched, never interpolated */}
          {!mini &&
            missing.map((d) => (
              <rect
                key={`m${d.missionDay}`}
                x={x(d.missionDay) - dayStep / 2 + 1}
                y={margin.top}
                width={Math.max(2, dayStep - 2)}
                height={plotH}
                fill={`url(#dhatch-${uid})`}
                className="day-missing"
              />
            ))}
          {base && (
            <g clipPath={`url(#dclip-${uid})`}>
              <rect x={margin.left} y={y(base.high)} width={plotW} height={Math.max(1, y(base.low) - y(base.high))} className="band" />
              {!mini && (
                <>
                  <line x1={margin.left} x2={margin.left + plotW} y1={y(base.high)} y2={y(base.high)} className="band-edge" />
                  <line x1={margin.left} x2={margin.left + plotW} y1={y(base.low)} y2={y(base.low)} className="band-edge" />
                </>
              )}
            </g>
          )}
          {!mini && base && (
            <>
              {/* Days used to compute the usual range: a quiet bracket on the baseline */}
              <line x1={Math.max(margin.left + 2, x(base.fromDay) - dayStep / 2 + 2)} x2={x(base.toDay) + dayStep / 2 - 2} y1={margin.top - 3} y2={margin.top - 3} className="baseline-bracket" />
              {showBaselineText && (
                <text x={Math.max(margin.left + 2, x(base.fromDay) - dayStep / 2 + 2)} y={margin.top - 8} className="band-label">
                  Baseline days {base.fromDay}–{base.toDay}
                </text>
              )}
              {usualY !== null && (
                <text x={margin.left + plotW + 6} y={usualY} className="band-label band-label-side">
                  usual
                </text>
              )}
            </>
          )}
          {!mini && streak && (
            <g>
              <rect
                x={x(streak.from) - dayStep / 2}
                y={margin.top}
                width={x(streak.to) - x(streak.from) + dayStep}
                height={plotH}
                rx={6}
                className="streak-zone"
              />
              <text x={x(streak.to) + dayStep / 2} y={margin.top - 8} textAnchor="end" className="streak-label">
                {streak.to - streak.from + 1} days {streak.side} usual
              </text>
            </g>
          )}
          {!mini && (
            <defs>
              <linearGradient id={`dfill-${uid}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" className="area-stop-top" />
                <stop offset="100%" className="area-stop-bottom" />
              </linearGradient>
            </defs>
          )}
          {!mini && area && <path d={area} fill={`url(#dfill-${uid})`} className="trend-area" />}
          <path d={path} className="line trend-line" />
          {hovered && !mini && <line x1={x(hovered.missionDay)} x2={x(hovered.missionDay)} y1={margin.top} y2={margin.top + plotH} className="cursor-line" />}
          {days.map((d) =>
            d.value === null ? (
              <line key={d.missionDay} x1={x(d.missionDay)} x2={x(d.missionDay)} y1={margin.top + plotH - 6} y2={margin.top + plotH} className="missing-tick" />
            ) : (
              <circle
                key={d.missionDay}
                cx={x(d.missionDay)}
                cy={y(d.value)}
                r={hovered?.missionDay === d.missionDay ? 5.5 : d === latest ? 5 : d.quality === 'good' ? (mini ? 3.5 : 2.5) : 3.5}
                className={`${d.quality === 'good' ? 'daily-dot' : 'mark-uncertain q-uncertain'}${d === latest ? ' is-latest' : ''}${!mini && d.quality === 'good' && d !== latest && hovered?.missionDay !== d.missionDay ? ' is-quiet' : ''}`}
              />
            ),
          )}
          {!mini && latest && (
            <text x={x(latest.missionDay) + 8} y={y(latest.value) + 4} className="direct-label">
              {formatDailyValue(series.indicator, latest.value)}
            </text>
          )}
          {!mini && xTicks.map((d) => (
            <text key={d} x={x(d)} y={height - 6} className={`tick${hovered?.missionDay === d ? ' tick-active' : ''}`} textAnchor="middle">
              {d === lastDay ? 'Today' : d}
            </text>
          ))}
          {!mini && <text x={margin.left - 8} y={height - 6} className="tick" textAnchor="end">Day</text>}
          {!mini && (
            <rect
              x={margin.left - dayStep / 2}
              y={margin.top}
              width={plotW + dayStep}
              height={plotH}
              fill="transparent"
              onMouseMove={(e) => pickDay(e.clientX, e.currentTarget)}
              onMouseLeave={() => setHover(null)}
            />
          )}
        </svg>
        {hovered && !mini && (
          // Floats above the page (position: fixed), so a short chart never cuts it.
          <div className="tt-anchor" style={tooltipAnchor(wrapRef.current, x(hovered.missionDay), x(hovered.missionDay) > width * 0.62)} aria-hidden="true">
          <div className="tooltip daily-tooltip">
            <div className="tt-time">
              Mission day {hovered.missionDay}
              {hovered.missionDay === lastDay ? ' · today' : ''} · {hovered.date}
            </div>
            {hovered.value === null ? (
              <div className="tt-value">No reading</div>
            ) : (
              <>
                <div className="tt-value">
                  <strong>{formatDailyValue(series.indicator, hovered.value)}</strong> {unit}
                </div>
                <div className={`tt-row${hovered.quality === 'good' ? '' : ' tt-attention'}`}>
                  <span>Quality</span>
                  <span>{QUALITY_LABEL[hovered.quality]}</span>
                </div>
                {base && (
                  <div className="tt-row">
                    <span>vs usual median</span>
                    <span>
                      {hovered.value - base.median > 0 ? '+' : ''}
                      {formatDailyValue(series.indicator, hovered.value - base.median)} {unit}
                    </span>
                  </div>
                )}
                {compare(hovered.value) && <div className="tt-muted">{compare(hovered.value)}</div>}
                {streak && hovered.missionDay >= streak.from && hovered.missionDay <= streak.to && (
                  <div className="tt-attention tt-streak">
                    Day {hovered.missionDay - streak.from + 1} of {streak.to - streak.from + 1} {streak.side} usual
                  </div>
                )}
                {hovered.quality !== 'good' && <div className="tt-muted">Not used for the baseline or the trend</div>}
              </>
            )}
          </div>
          </div>
        )}
        <div className="sr-only" aria-live="polite">
          {hovered && !mini
            ? `Day ${hovered.missionDay}: ${hovered.value === null ? 'no reading' : `${formatDailyValue(series.indicator, hovered.value)} ${unit}, quality ${QUALITY_LABEL[hovered.quality].toLowerCase()}`}`
            : ''}
        </div>
      </div>
      {/* On very short charts the legend gives way to the plot; the full chart is in Details. */}
      {!mini && height >= 96 && <figcaption className="daily-chart-foot">
        <span>
          <span className="swatch swatch-band" aria-hidden="true" /> Usual range
          {base ? ` from baseline days ${base.fromDay}–${base.toDay}` : ' — not available yet'}
          {missing.length > 0 && (
            <>
              <span className="swatch swatch-hatch" aria-hidden="true" /> No reading
            </>
          )}
        </span>
        <button type="button" className="link-button" aria-expanded={showTable} onClick={() => setShowTable((v) => !v)}>
          {showTable ? 'Hide table' : 'Data table'}
        </button>
      </figcaption>}
      {!mini && showTable && (
        <div className="table-scroll daily-table">
          <table className="data-table compact">
            <caption className="sr-only">{def.label}: daily readings</caption>
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col">Date</th>
                <th scope="col" className="num">
                  {def.label} ({unit})
                </th>
                <th scope="col">Quality</th>
              </tr>
            </thead>
            <tbody>
              {[...days].reverse().map((d) => (
                <tr key={d.missionDay}>
                  <td className="num">{d.missionDay}</td>
                  <td>{d.date}</td>
                  <td className="num">{formatDailyValue(series.indicator, d.value)}</td>
                  <td>{QUALITY_LABEL[d.quality]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </figure>
  )
}

/** Fixed position next to the hovered day, kept inside the window. */
function tooltipAnchor(el: HTMLElement | null, px: number, flip: boolean): CSSProperties {
  if (!el) return { position: 'absolute', top: 6, left: px + 12 }
  const r = el.getBoundingClientRect()
  const top = Math.max(8, Math.min(r.top + 6, window.innerHeight - 200))
  return flip
    ? { position: 'fixed', top, left: r.left + px - 12, transform: 'translateX(-100%)', zIndex: 40 }
    : { position: 'fixed', top, left: r.left + px + 12, zIndex: 40 }
}
