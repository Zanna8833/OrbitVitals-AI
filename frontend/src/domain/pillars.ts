import type { DailyIndicatorSeries, QualityFlag } from './types'
import type { IndicatorEvaluation } from './crewHealth'

/**
 * The three things OrbitVitals adds to a raw number, computed from the data:
 * 1. Data quality — how many readings can be trusted;
 * 2. Personal baseline — the person's own usual range;
 * 3. Trend — whether, and for how long, the latest readings differ from it.
 * Descriptive only: no clinical threshold, no interpretation.
 */
export interface Pillars {
  quality: { reliable: number; total: number; latestQuality: QualityFlag | null; uncertainDays: number; missingDays: number }
  baseline: { low: number; median: number; high: number; fromDay: number; toDay: number } | null
  trend: {
    position: 'above' | 'below' | 'within' | null
    streakDays: number
    /** Latest reliable value minus the baseline median, in the indicator's unit. */
    delta: number | null
    /** True when the change is sustained (≥ 3 days), the threshold used to flag it. */
    sustained: boolean
  }
}

export const SUSTAINED_DAYS = 3

export function pillarsOf(series: DailyIndicatorSeries, e: IndicatorEvaluation): Pillars {
  const days = series.days
  const reliable = days.filter((d) => d.value !== null && d.quality === 'good').length
  const uncertainDays = days.filter((d) => d.value !== null && d.quality !== 'good').length
  const missingDays = days.filter((d) => d.value === null).length
  const latest = days[days.length - 1]
  const b = series.baseline
  return {
    quality: { reliable, total: days.length, latestQuality: latest ? latest.quality : null, uncertainDays, missingDays },
    baseline: b ? { low: b.low, median: b.median, high: b.high, fromDay: b.fromDay, toDay: b.toDay } : null,
    trend: {
      position: e.position,
      streakDays: e.streakDays,
      delta: b && e.latest && e.latest.value !== null ? e.latest.value - b.median : null,
      sustained: e.position !== null && e.position !== 'within' && e.streakDays >= SUSTAINED_DAYS,
    },
  }
}
