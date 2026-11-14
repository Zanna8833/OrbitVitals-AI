import { useId, useLayoutEffect, useRef, useState } from 'react'
import type { DailyIndicatorId, DailyIndicatorSeries, DailyValue } from '../domain/types'
import { DAILY_INDICATORS, QUALITY_LABEL, formatDailyValue } from '../domain/parameters'
import { linear, niceDomain, niceTicks } from './chartScale'

/** Smallest visible y-span per indicator, so small day-to-day noise is not magnified. */
const MIN_SPAN: Record<DailyIndicatorId, number> = {
  resting_hr: 14, sleep_duration: 2.5, resting_spo2: 5, resting_resp_rate: 6,
  hrv_rmssd: 22, bp_systolic: 24, bp_diastolic: 16, body_temperature: 1.8,
  activity_minutes: 48, body_mass: 2, sleep_efficiency: 18,
}
const M = { left: 40, right: 44, top: 10, bottom: 24 }

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

  // Line segments between consecutive mission days only (a missing day breaks the line).
  let path = ''
  for (let i = 1; i < days.length; i++) {
    const a = days[i - 1]
    const b = days[i]
    if (a.value === null || b.value === null) continue
    path += `M${x(a.missionDay).toFixed(1)},${y(a.value).toFixed(1)}L${x(b.missionDay).toFixed(1)},${y(b.value).toFixed(1)}`
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

  return (
    <figure className="daily-chart">
      <div ref={wrapRef} className="daily-chart-body" role="img" aria-label={summary}>
        <svg width={width} height={height} aria-hidden="true">
          <defs>
            <clipPath id={`dclip-${uid}`}>
              <rect x={margin.left} y={margin.top} width={plotW} height={plotH} />
            </clipPath>
          </defs>
          {!mini && niceTicks(y0, y1, 3).map((v) => (
            <g key={v}>
              <line x1={margin.left} x2={margin.left + plotW} y1={y(v)} y2={y(v)} className="grid" />
              <text x={margin.left - 6} y={y(v) + 4} className="tick" textAnchor="end">
                {formatDailyValue(series.indicator, v)}
              </text>
            </g>
          ))}
          {base && (
            <g clipPath={`url(#dclip-${uid})`}>
              <rect x={margin.left} y={y(base.high)} width={plotW} height={Math.max(1, y(base.low) - y(base.high))} className="band" />
              <rect
                x={x(base.fromDay) - dayStep / 2}
                y={margin.top}
                width={(base.toDay - base.fromDay + 1) * dayStep}
                height={plotH}
                className="baseline-days"
              />
            </g>
          )}
          <path d={path} className="line" />
          {days.map((d) =>
            d.value === null ? (
              <line key={d.missionDay} x1={x(d.missionDay)} x2={x(d.missionDay)} y1={margin.top + plotH - 6} y2={margin.top + plotH} className="missing-tick" />
            ) : (
              <circle
                key={d.missionDay}
                cx={x(d.missionDay)}
                cy={y(d.value)}
                r={d === latest ? 5 : 3.5}
                className={d.quality === 'good' ? 'daily-dot' : 'mark-uncertain q-uncertain'}
              >
                <title>
                  Day {d.missionDay}: {formatDailyValue(series.indicator, d.value)} {unit}, quality {QUALITY_LABEL[d.quality].toLowerCase()}
                </title>
              </circle>
            ),
          )}
          {!mini && latest && (
            <text x={x(latest.missionDay) + 8} y={y(latest.value) + 4} className="direct-label">
              {formatDailyValue(series.indicator, latest.value)}
            </text>
          )}
          {!mini && xTicks.map((d) => (
            <text key={d} x={x(d)} y={height - 6} className="tick" textAnchor="middle">
              {d === lastDay ? 'Today' : d}
            </text>
          ))}
          {!mini && <text x={margin.left - 6} y={height - 6} className="tick" textAnchor="end">Day</text>}
        </svg>
      </div>
      {!mini && <figcaption className="daily-chart-foot">
        <span>
          <span className="swatch swatch-band" aria-hidden="true" /> Usual range
          {base ? ` (days ${base.fromDay}–${base.toDay})` : ' — not available yet'}
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
