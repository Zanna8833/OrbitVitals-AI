import type { QualityFlag } from './types'
import { toMs } from './time'

/**
 * Data freshness, i.e. how old the latest received sample is compared with the
 * expected sampling interval. These are DISPLAY thresholds for the demo, not
 * clinical thresholds; they must be agreed with the backend team and experts.
 */
export type Freshness = 'current' | 'delayed' | 'stale' | 'none'

export const FRESHNESS_RULES = {
  /** "delayed" after this many missed sampling intervals. */
  delayedAfterIntervals: 6,
  /** "stale" after this many seconds without data. */
  staleAfterS: 300,
} as const

export function computeFreshness(lastIso: string | null, nowIso: string, samplingIntervalS: number): Freshness {
  if (!lastIso) return 'none'
  const ageS = (toMs(nowIso) - toMs(lastIso)) / 1000
  if (ageS > FRESHNESS_RULES.staleAfterS) return 'stale'
  if (ageS > samplingIntervalS * FRESHNESS_RULES.delayedAfterIntervals) return 'delayed'
  return 'current'
}

export const FRESHNESS_LABEL: Record<Freshness, string> = {
  current: 'Current',
  delayed: 'Delayed',
  stale: 'Not updated',
  none: 'No data',
}

/** Freshness reuses the quality glyph shapes: current ● · delayed ◐ · not updated ▲ · no data ◌. */
export const FRESHNESS_GLYPH: Record<Freshness, QualityFlag> = { current: 'good', delayed: 'uncertain', stale: 'poor', none: 'missing' }
