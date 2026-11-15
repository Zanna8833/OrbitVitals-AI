import type { DailyIndicatorId, DailyIndicatorSeries, QualityFlag } from './types'

/**
 * Technical views for the medical team. Everything is relative to the
 * astronaut's own usual range: no population or clinical threshold.
 *
 * "Range units": (value − usual median) / (half-width of the usual range).
 * 0 = the usual median, ±1 = the edge of the usual range, ±2 = twice as far.
 */
export function rangeUnits(value: number, series: DailyIndicatorSeries): number | null {
  const b = series.baseline
  if (!b) return null
  const half = value >= b.median ? b.high - b.median : b.median - b.low
  return half > 0 ? (value - b.median) / half : null
}

export interface DayDeviation {
  missionDay: number
  date: string
  value: number | null
  quality: QualityFlag
  /** Range units, null without a value or a baseline. */
  units: number | null
}

export function deviationsOf(series: DailyIndicatorSeries): DayDeviation[] {
  return series.days.map((d) => ({
    missionDay: d.missionDay,
    date: d.date,
    value: d.value,
    quality: d.quality,
    units: d.value === null ? null : rangeUnits(d.value, series),
  }))
}

/** Latest reliable reading and where it sits. */
export interface LatestCell {
  indicator: DailyIndicatorId
  value: number | null
  missionDay: number | null
  quality: QualityFlag
  units: number | null
  /** Consecutive reliable days on the same side outside the usual range. */
  streak: number
}

export function latestCell(series: DailyIndicatorSeries): LatestCell {
  const reliable = series.days.filter((d) => d.value !== null && d.quality === 'good')
  const last = [...series.days].reverse().find((d) => d.value !== null) ?? null
  const ref = reliable[reliable.length - 1] ?? null
  const units = ref ? rangeUnits(ref.value as number, series) : null
  let streak = 0
  if (units !== null && Math.abs(units) > 1) {
    const side = Math.sign(units)
    for (let i = reliable.length - 1; i >= 0; i--) {
      const u = rangeUnits(reliable[i].value as number, series)
      if (u === null || Math.abs(u) <= 1 || Math.sign(u) !== side) break
      streak++
    }
  }
  return {
    indicator: series.indicator,
    value: ref?.value ?? last?.value ?? null,
    missionDay: ref?.missionDay ?? last?.missionDay ?? null,
    quality: ref ? 'good' : (last?.quality ?? 'missing'),
    units,
    streak,
  }
}

/**
 * Share of an astronaut's indicators with a reliable reading on each of the
 * last `days` days. Only indicators measured at least once count, so an
 * instrument the crew does not use does not make every day look incomplete.
 */
export function completeness(series: DailyIndicatorSeries[], lastDay: number, days: number): { missionDay: number; date: string | null; share: number | null; reliable: number; total: number }[] {
  const used = series.filter((s) => s.days.some((d) => d.value !== null))
  const out = []
  for (let d = lastDay - days + 1; d <= lastDay; d++) {
    if (d < 1) continue
    const day = used.map((s) => s.days.find((x) => x.missionDay === d))
    const reliable = day.filter((x) => x && x.value !== null && x.quality === 'good').length
    out.push({ missionDay: d, date: day.find((x) => x)?.date ?? null, share: used.length ? reliable / used.length : null, reliable, total: used.length })
  }
  return out
}
