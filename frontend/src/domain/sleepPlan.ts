import type { SleepAidPlanEntry } from './types'

/**
 * Sleep-aid coordination. The app records only WHO plans a sleep aid on WHICH
 * night — never a drug, a dose or advice. The coverage rule is a demo setting:
 * the real rule is decided by the mission's medical authority.
 */
export const SLEEP_COVER_RULE = {
  /** Crew members who must remain without a sleep aid each night (demo value). */
  minWithoutSleepAid: 1,
} as const

const DAY_MS = 86_400_000

/** `count` consecutive nights starting at `startDate` (YYYY-MM-DD). */
export function nightsFrom(startDate: string, count: number): string[] {
  const start = Date.parse(`${startDate}T00:00:00Z`)
  return Array.from({ length: count }, (_, i) => new Date(start + i * DAY_MS).toISOString().slice(0, 10))
}

export function addDays(date: string, days: number): string {
  return new Date(Date.parse(`${date}T00:00:00Z`) + days * DAY_MS).toISOString().slice(0, 10)
}

export interface NightCoverage {
  night: string
  /** Crew members who planned a sleep aid that night. */
  planned: string[]
  /** Crew members without a planned sleep aid. */
  available: number
  total: number
  /** Fewer crew members without a sleep aid than the rule requires. */
  uncovered: boolean
}

export function coverageOf(entries: SleepAidPlanEntry[], crewIds: string[], night: string): NightCoverage {
  const planned = crewIds.filter((id) => entries.some((e) => e.crewId === id && e.night === night))
  const available = crewIds.length - planned.length
  return { night, planned, available, total: crewIds.length, uncovered: crewIds.length > 0 && available < SLEEP_COVER_RULE.minWithoutSleepAid }
}

/** Would adding this crew member's night leave the crew without enough cover? */
export function wouldUncover(entries: SleepAidPlanEntry[], crewIds: string[], crewId: string, night: string): boolean {
  if (entries.some((e) => e.crewId === crewId && e.night === night)) return false
  return coverageOf([...entries, { crewId, night, updatedAt: '', simulated: true }], crewIds, night).uncovered
}

export function isPlanned(entries: SleepAidPlanEntry[], crewId: string, night: string): boolean {
  return entries.some((e) => e.crewId === crewId && e.night === night)
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** { weekday: 'Sat', day: '14', month: 'Nov' } — always UTC. */
export function nightLabel(night: string) {
  const d = new Date(`${night}T00:00:00Z`)
  return { weekday: WEEKDAYS[d.getUTCDay()], day: String(d.getUTCDate()), month: MONTHS[d.getUTCMonth()] }
}
