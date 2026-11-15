import type { CheckIn, CheckInScore, DailyIndicatorId, DailyIndicatorSeries, DailyValue, PersonalBaseline, QualityFlag } from '../../domain/types'
import { DAILY_INDICATORS, DAILY_INDICATOR_ORDER } from '../../domain/parameters'
import { missionDayOf as dayOf } from '../../domain/time'
import { gaussian, hashSeed, mulberry32 } from './rng'
import type { ScenarioFlags } from './scenarios'

/**
 * Simulated long-duration mission timeline: one measurement per indicator per
 * day, plus seeded self-reports. Deterministic. Nothing here is real data.
 */

/** Mission day 1. With the demo clock on 14 Nov 2026, today is mission day 15. */
export const MISSION_START_DATE = '2026-10-31'
/** The personal baseline is computed from these mission days. */
export const BASELINE_DAYS = { from: 1, to: 7 } as const

const DAY_MS = 24 * 60 * 60 * 1000

export function missionDayOf(dateIso: string): number {
  return dayOf(dateIso, MISSION_START_DATE)
}

export function dateOfMissionDay(day: number): string {
  return new Date(Date.parse(MISSION_START_DATE) + (day - 1) * DAY_MS).toISOString().slice(0, 10)
}

interface DailyProfile {
  base: Record<DailyIndicatorId, number>
  noise: Record<DailyIndicatorId, number>
  /** Mission days without any measurement (device not worn). */
  notWorn: number[]
}

const PROFILES: Record<string, DailyProfile> = {
  'crew-a': {
    base: { resting_hr:58, sleep_duration:7.1, resting_spo2:98, resting_resp_rate:15, hrv_rmssd:46,
      bp_systolic:115, bp_diastolic:75, body_temperature:36.6, activity_minutes:62, body_mass:74.5, sleep_efficiency:85 },
    noise: { resting_hr:1.4, sleep_duration:0.3, resting_spo2:0.4, resting_resp_rate:0.8, hrv_rmssd:3.5,
      bp_systolic:2.8, bp_diastolic:2, body_temperature:0.13, activity_minutes:6, body_mass:0.18, sleep_efficiency:2.5 },
    notWorn: [],
  },
  'crew-b': {
    base: { resting_hr:62, sleep_duration:6.8, resting_spo2:97.6, resting_resp_rate:16, hrv_rmssd:41,
      bp_systolic:119, bp_diastolic:76, body_temperature:36.7, activity_minutes:57, body_mass:68.3, sleep_efficiency:82 },
    noise: { resting_hr:1.5, sleep_duration:0.35, resting_spo2:0.4, resting_resp_rate:0.9, hrv_rmssd:3,
      bp_systolic:3, bp_diastolic:2.2, body_temperature:0.13, activity_minutes:7, body_mass:0.2, sleep_efficiency:3 },
    notWorn: [],
  },
  'crew-c': {
    base: { resting_hr:60, sleep_duration:7.3, resting_spo2:97.8, resting_resp_rate:15, hrv_rmssd:43,
      bp_systolic:117, bp_diastolic:74, body_temperature:36.5, activity_minutes:65, body_mass:78.2, sleep_efficiency:86 },
    noise: { resting_hr:1.4, sleep_duration:0.3, resting_spo2:0.4, resting_resp_rate:0.9, hrv_rmssd:3.5,
      bp_systolic:3, bp_diastolic:2, body_temperature:0.14, activity_minutes:6, body_mass:0.19, sleep_efficiency:2.5 },
    notWorn: [9, 13],
  },
}

/** Demo story (Crew A, when the scenario has the "event to review" condition): a change over the last days. */
const DRIFT: Partial<Record<DailyIndicatorId, Record<number, number>>> = {
  resting_hr: { 12: 4, 13: 6, 14: 8, 15: 9 },
  sleep_duration: { 12: -0.7, 13: -1.0, 14: -1.3, 15: -1.4 },
}

const SOURCE: Record<DailyIndicatorId, string> = {
  resting_hr: 'ECG chest sensor · synthetic resting reading',
  sleep_duration: 'Wrist wearable · synthetic overnight estimate',
  resting_spo2: 'Finger pulse oximeter · synthetic spot reading',
  resting_resp_rate: 'Respiration sensor · synthetic resting estimate; motion artifacts possible',
  hrv_rmssd: 'ECG/PPG-derived HRV · synthetic RMSSD estimate, not a diagnosis',
  bp_systolic: 'Blood pressure cuff · synthetic systolic reading',
  bp_diastolic: 'Blood pressure cuff · synthetic diastolic reading',
  body_temperature: 'Digital thermometer · synthetic spot reading',
  activity_minutes: 'Exercise machine / wearable · synthetic minutes',
  body_mass: 'Body mass measurement device · synthetic reading',
  sleep_efficiency: 'Wrist wearable · synthetic sleep efficiency estimate; not EEG staging',
}

function round(indicator: DailyIndicatorId, v: number): number {
  const k = Math.pow(10, DAILY_INDICATORS[indicator].decimals)
  return Math.round(v * k) / k
}

function median(sorted: number[]): number {
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
}

/**
 * Smallest half-width of the usual range, so that normal day-to-day variation
 * is not shown as a change. Design values for the demo, not clinical ones.
 */
export const MIN_HALF_WIDTH: Record<DailyIndicatorId, number> = {
  resting_hr: 3, sleep_duration: 0.5, resting_spo2: 1, resting_resp_rate: 2,
  hrv_rmssd: 7, bp_systolic: 6, bp_diastolic: 5, body_temperature: 0.4,
  activity_minutes: 16, body_mass: 0.6, sleep_efficiency: 6,
}

/**
 * Usual range = median of the good-quality baseline readings ± max(2 × robust SD, minimum
 * half-width). Robust SD = 1.4826 × median absolute deviation (insensitive to one odd day).
 * A P10–P90 band over 7 days was tried first and rejected: far too narrow, it labelled
 * normal variation as a change.
 */
export function baselineOf(indicator: DailyIndicatorId, days: DailyValue[]): PersonalBaseline | null {
  const values = days
    .filter((d) => d.missionDay >= BASELINE_DAYS.from && d.missionDay <= BASELINE_DAYS.to && d.quality === 'good' && d.value !== null)
    .map((d) => d.value as number)
    .sort((a, b) => a - b)
  if (values.length < 5) return null
  const m = median(values)
  const mad = median(values.map((v) => Math.abs(v - m)).sort((a, b) => a - b))
  const half = Math.max(2 * 1.4826 * mad, MIN_HALF_WIDTH[indicator])
  return {
    low: round(indicator, m - half),
    median: round(indicator, m),
    high: round(indicator, m + half),
    fromDay: BASELINE_DAYS.from,
    toDay: BASELINE_DAYS.to,
    basis: `Your usual range: the middle value of your good-quality readings on mission days ${BASELINE_DAYS.from}–${BASELINE_DAYS.to}, plus or minus a margin for normal day-to-day variation. A personal comparison, not a clinical reference. Simulated data.`,
  }
}

/** Daily indicators for one crew member up to (and including) `todayIso`'s mission day. */
export function generateDailyIndicators(crewId: string, todayIso: string, flags: ScenarioFlags): DailyIndicatorSeries[] {
  const profile = PROFILES[crewId]
  if (!profile) return []
  const today = missionDayOf(todayIso)
  return DAILY_INDICATOR_ORDER.map((indicator) => {
    const rand = mulberry32(hashSeed(`${crewId}-${indicator}-daily`))
    const days: DailyValue[] = []
    for (let day = 1; day <= today; day++) {
      const noise = gaussian(rand)
      const flagDraw = rand()
      const date = dateOfMissionDay(day)
      if (profile.notWorn.includes(day)) {
        days.push({ date, missionDay: day, value: null, quality: 'missing' })
        continue
      }
      let value = profile.base[indicator] + profile.noise[indicator] * noise
      if (flags.reviewEvent && crewId === 'crew-a') value += DRIFT[indicator]?.[day] ?? 0
      if (indicator === 'resting_spo2' || indicator === 'sleep_efficiency') value = Math.min(100, Math.max(0, value))
      if (indicator === 'activity_minutes') value = Math.max(0, value)
      const quality: QualityFlag = flagDraw < 0.07 ? 'uncertain' : 'good'
      days.push({ date, missionDay: day, value: round(indicator, value), quality })
    }
    return {
      crewId,
      indicator,
      unit: DAILY_INDICATORS[indicator].unit,
      days,
      baseline: baselineOf(indicator, days),
      source: SOURCE[indicator],
      simulated: true,
    }
  })
}

/** Self-reports already submitted before today (seeded for the demo). */
export function seedCheckIns(crewId: string, todayIso: string, flags: ScenarioFlags): CheckIn[] {
  const today = missionDayOf(todayIso)
  const s = (n: number) => n as CheckInScore
  const plan: Record<string, { day: number; sleep: number; energy: number; mood: number; note?: string }[]> = {
    'crew-a': flags.reviewEvent
      ? [
          { day: 10, sleep: 4, energy: 4, mood: 4 },
          { day: 11, sleep: 4, energy: 4, mood: 4 },
          { day: 12, sleep: 3, energy: 3, mood: 4 },
          { day: 13, sleep: 2, energy: 3, mood: 3, note: 'Woke up several times.' },
          { day: 14, sleep: 2, energy: 2, mood: 3 },
        ]
      : [
          { day: 12, sleep: 4, energy: 4, mood: 4 },
          { day: 13, sleep: 4, energy: 4, mood: 4 },
          { day: 14, sleep: 4, energy: 4, mood: 5 },
        ],
    'crew-b': [
      { day: 11, sleep: 4, energy: 4, mood: 4 },
      { day: 12, sleep: 3, energy: 4, mood: 4 },
      { day: 13, sleep: 4, energy: 4, mood: 4 },
      { day: 14, sleep: 4, energy: 5, mood: 4 },
    ],
    'crew-c': [
      { day: 12, sleep: 4, energy: 3, mood: 4 },
      { day: 14, sleep: 4, energy: 4, mood: 4 },
    ],
  }
  return (plan[crewId] ?? [])
    .filter((p) => p.day < today)
    .map((p) => ({
      id: `CI-${crewId}-${p.day}`,
      crewId,
      date: dateOfMissionDay(p.day),
      missionDay: p.day,
      createdAt: `${dateOfMissionDay(p.day)}T07:30:00Z`,
      sleepQuality: s(p.sleep),
      energy: s(p.energy),
      mood: s(p.mood),
      note: p.note ?? '',
    }))
    .reverse()
}
