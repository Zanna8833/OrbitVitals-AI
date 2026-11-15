import type { CheckIn, DailyIndicatorSeries, DailyValue } from './types'
import { CHECK_IN_QUESTIONS, DAILY_INDICATORS } from './parameters'
import { isPastView } from '../state/pastView'

/**
 * "My health": the crew member evaluates their own daily indicators against
 * their OWN usual range (personal baseline) and sees what they can do.
 *
 * Boundaries (docs/UX_ANALYSIS.md): no diagnosis, no clinical thresholds, no
 * medical advice. Outside the usual range means "different from your usual",
 * nothing more. Options are offered, never ordered.
 */

export type Position = 'within' | 'above' | 'below'

export interface IndicatorEvaluation {
  series: DailyIndicatorSeries
  /** Latest day with a valid value; null if none. */
  latest: DailyValue | null
  /** True when today's reading exists. */
  measuredToday: boolean
  position: Position | null
  /** Consecutive latest valid days on the same side outside the usual range (0 when within). */
  streakDays: number
  /** Short plain-language status, e.g. "Higher than your usual for 4 days". */
  headline: string
  /** Today's reading is uncertain or missing, so it is worth repeating. */
  repeatSuggested: boolean
}

function positionOf(value: number, low: number, high: number): Position {
  return value > high ? 'above' : value < low ? 'below' : 'within'
}

/** `voice`: "your" in the crew member's own view, "their" in the medical team's view. */
export type Voice = 'your' | 'their'

export function evaluateIndicator(series: DailyIndicatorSeries, todayMissionDay: number, voice: Voice = 'your'): IndicatorEvaluation {
  const valid = series.days.filter((d) => d.value !== null && d.quality === 'good')
  const latest = valid[valid.length - 1] ?? null
  const today = series.days.find((d) => d.missionDay === todayMissionDay)
  const measuredToday = !!today && today.value !== null
  const repeatSuggested = !today || today.value === null || today.quality !== 'good'
  const base = series.baseline

  if (!latest) {
    return { series, latest, measuredToday, position: null, streakDays: 0, headline: 'No readings yet', repeatSuggested }
  }
  if (!base) {
    return { series, latest, measuredToday, position: null, streakDays: 0, headline: `${voice === 'your' ? 'Your' : 'Their'} usual range is not available yet`, repeatSuggested }
  }

  const position = positionOf(latest.value as number, base.low, base.high)
  let streakDays = 0
  if (position !== 'within') {
    for (let i = valid.length - 1; i >= 0; i--) {
      if (positionOf(valid[i].value as number, base.low, base.high) !== position) break
      streakDays++
    }
  }
  const side = position === 'above' ? 'Higher' : 'Lower'
  const headline =
    position === 'within'
      ? `Within ${voice} usual range`
      : streakDays > 1
        ? `${side} than ${voice} usual for ${streakDays} days`
        : `${side} than ${voice} usual today`
  const reliableHeadline = repeatSuggested ? `${headline} (last reliable reading: day ${latest.missionDay}; today’s data need verification)` : headline
  return { series, latest, measuredToday, position, streakDays, headline: reliableHeadline, repeatSuggested }
}

/** A change worth noticing: outside the usual range on at least this many consecutive days. */
export const SUSTAINED_CHANGE_DAYS = 3

export interface HealthSummary {
  title: string
  detail: string
  /** Indicators outside the usual range for SUSTAINED_CHANGE_DAYS or more. */
  changed: IndicatorEvaluation[]
}

export function summarizeHealth(evaluations: IndicatorEvaluation[]): HealthSummary {
  const changed = evaluations.filter((e) => e.position && e.position !== 'within' && e.streakDays >= SUSTAINED_CHANGE_DAYS)
  if (!changed.length) {
    return {
      title: 'Your indicators are within your usual range',
      detail: 'Compared with your own first mission days. This is a personal comparison, not a medical assessment.',
      changed,
    }
  }
  const names = changed.map((e) => DAILY_INDICATORS[e.series.indicator].label.toLowerCase())
  return {
    title: `Different from your usual: ${joinNames(names)}`,
    detail: 'A change from your own usual range is worth noticing, not a diagnosis. You decide whether to share it with the medical team.',
    changed,
  }
}

export type HealthOptionId = 'check_in' | 'repeat_measure' | 'share' | 'procedures'

export interface HealthOption {
  id: HealthOptionId
  title: string
  detail: string
  /** Shown first when a change was noticed. */
  emphasised: boolean
}

/** What the crew member CAN do now — options, ordered by relevance. */
export function healthOptions({
  evaluations,
  summary,
  checkedInToday,
  linkOffline,
}: {
  evaluations: IndicatorEvaluation[]
  summary: HealthSummary
  checkedInToday: boolean
  linkOffline: boolean
}): HealthOption[] {
  const options: HealthOption[] = []
  const changed = summary.changed.length > 0

  if (changed) {
    options.push({
      id: 'share',
      title: 'Share your trends with the medical team',
      detail: linkOffline
        ? 'The ground link is down: your report can be saved and queued locally.'
        : 'They will see your daily trends and your note, and can contact you.',
      emphasised: true,
    })
  }
  if (!checkedInToday) {
    options.push({
      id: 'check_in',
      title: 'Note how you feel today',
      detail: 'Three quick questions on sleep, energy and mood, plus an optional note. It helps you and the team notice changes.',
      emphasised: changed,
    })
  }
  const toRepeat = evaluations.filter((e) => e.repeatSuggested)
  if (toRepeat.length) {
    options.push({
      id: 'repeat_measure',
      title: `Repeat today’s reading: ${joinNames(toRepeat.map((e) => DAILY_INDICATORS[e.series.indicator].label.toLowerCase()))}`,
      detail: isPastView() ? 'That day’s reading was missing or uncertain.' : 'Today’s reading is missing or uncertain. Take a new one from Take a measurement.',
      emphasised: false,
    })
  }
  options.push({
    id: 'procedures',
    title: 'Review the information checklist',
    detail: 'Learn how to check timestamp, signal quality and context before interpreting data. Not a medical procedure.',
    emphasised: false,
  })
  if (!changed) {
    options.push({
      id: 'share',
      title: 'Share your trends with the medical team',
      detail: linkOffline ? 'The ground link is down: you can queue your report for later sync.' : 'Optional: you can share at any time, with a note.',
      emphasised: false,
    })
  }
  return options
}

export function checkedInOn(checkIns: CheckIn[], dateIso: string): CheckIn | undefined {
  return checkIns.find((c) => c.date === dateIso.slice(0, 10))
}

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? ''
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

/** One-line summary of a check-in, in the words of its scales. */
export function describeCheckIn(c: CheckIn): string {
  const word = (id: 'sleepQuality' | 'energy' | 'mood') => CHECK_IN_QUESTIONS.find((q) => q.id === id)!.scale[c[id] - 1].toLowerCase()
  return `Sleep: ${word('sleepQuality')} · Energy: ${word('energy')} · Mood: ${word('mood')}${c.note ? ` · “${c.note}”` : ''}`
}
