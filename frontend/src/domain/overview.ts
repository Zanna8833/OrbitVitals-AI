import type { CrewSnapshot, ReviewEvent } from './types'
import { computeFreshness, type Freshness } from './freshness'

/**
 * Triage summary for the top of the Flight Surgeon review. Counts only —
 * no scores, no thresholds beyond the demo display thresholds of freshness.
 */
export interface OverviewSummary {
  /** Events not yet reviewed (open + in review). */
  toReview: number
  inReview: number
  crewTotal: number
  /** Crew members whose latest data is "current". */
  upToDate: number
  /** Members whose data is delayed, not updated or missing, with their last data time. */
  notUpToDate: { name: string; lastReceivedAt: string | null; freshness: Exclude<Freshness, 'current'> }[]
}

export function summarizeOverview(snapshots: CrewSnapshot[], events: ReviewEvent[], nowIso: string): OverviewSummary {
  const pending = events.filter((e) => e.status !== 'reviewed')
  const notUpToDate = snapshots.flatMap((s) => {
    const freshness = computeFreshness(s.device.lastReceivedAt, nowIso, s.device.expectedIntervalS)
    return freshness === 'current' ? [] : [{ name: s.crew.displayName, lastReceivedAt: s.device.lastReceivedAt, freshness }]
  })
  return {
    toReview: pending.length,
    inReview: pending.filter((e) => e.status === 'in_review').length,
    crewTotal: snapshots.length,
    upToDate: snapshots.length - notUpToDate.length,
    notUpToDate,
  }
}

/** "Crew A" → "A", "Maria Rossi" → "MR". Pseudonyms only in this prototype. */
export function initialsOf(displayName: string): string {
  const words = displayName.trim().split(/\s+/)
  if (words.length > 1 && /^crew$/i.test(words[0])) return words.slice(1).join('').slice(0, 2).toUpperCase()
  return words
    .slice(0, 2)
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()
}
