import type { DailyIndicatorSeries } from '../domain/types'

/**
 * A quiet trend line for summary tiles: the last 14 days against the person's
 * usual range (light band). Decorative summary only — the exact values are in
 * the indicator sheet and its data table, so it is hidden from screen readers.
 */
export function Sparkline({ series, width = 120, height = 36 }: { series: DailyIndicatorSeries; width?: number; height?: number }) {
  const days = series.days.slice(-14)
  const vals = days.filter((d) => d.value !== null).map((d) => d.value as number)
  if (vals.length < 2) return null
  const base = series.baseline
  let lo = Math.min(...vals, base?.low ?? Infinity)
  let hi = Math.max(...vals, base?.high ?? -Infinity)
  if (hi - lo < 1e-6) {
    lo -= 1
    hi += 1
  }
  const pad = (hi - lo) * 0.15
  lo -= pad
  hi += pad
  const n = days.length
  const x = (i: number) => 3 + (i / Math.max(1, n - 1)) * (width - 6)
  const y = (v: number) => height - 3 - ((v - lo) / (hi - lo)) * (height - 6)
  let d = ''
  let pen = false
  days.forEach((day, i) => {
    if (day.value === null) {
      pen = false
      return
    }
    d += `${pen ? 'L' : 'M'}${x(i).toFixed(1)},${y(day.value).toFixed(1)}`
    pen = true
  })
  const lastIdx = days.map((dd) => dd.value !== null).lastIndexOf(true)
  const last = days[lastIdx]
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      {base && <rect x={0} y={y(base.high)} width={width} height={Math.max(1, y(base.low) - y(base.high))} rx={3} className="spark-band" />}
      <path d={d} className="spark-line" />
      {last && <circle cx={x(lastIdx)} cy={y(last.value as number)} r={3} className={last.quality === 'good' ? 'spark-dot' : 'spark-dot is-uncertain'} />}
    </svg>
  )
}
