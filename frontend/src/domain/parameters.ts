import type { ActivityKind, CheckInInput, DailyIndicatorId, EventKind, EventStatus, LinkState, ParameterId, QualityFlag, QualityReason } from './types'

export interface ParameterDef {
  id: ParameterId
  label: string
  shortLabel: string
  unit: string
  decimals: number
  /** Role in the UI: a vital parameter or a context signal used to judge artifacts. */
  role: 'vital' | 'context'
}

export const PARAMETERS: Record<ParameterId, ParameterDef> = {
  heart_rate: { id: 'heart_rate', label: 'Heart rate', shortLabel: 'HR', unit: 'bpm', decimals: 0, role: 'vital' },
  spo2: { id: 'spo2', label: 'O₂ saturation (SpO₂)', shortLabel: 'SpO₂', unit: '%', decimals: 0, role: 'vital' },
  resp_rate: { id: 'resp_rate', label: 'Respiratory rate', shortLabel: 'RR', unit: 'breaths/min', decimals: 0, role: 'vital' },
  motion: { id: 'motion', label: 'Motion (accelerometer, RMS)', shortLabel: 'Motion', unit: 'g', decimals: 2, role: 'context' },
}

export const PARAMETER_ORDER: ParameterId[] = ['heart_rate', 'spo2', 'resp_rate', 'motion']
export const VITAL_PARAMETERS: ParameterId[] = ['heart_rate', 'spo2', 'resp_rate']

export const QUALITY_FLAGS: readonly QualityFlag[] = ['good', 'uncertain', 'poor', 'missing']

/** "Good" rather than "reliable": the flag is simulated and carries no validated reliability claim. */
export const QUALITY_LABEL: Record<QualityFlag, string> = {
  good: 'Good',
  uncertain: 'Uncertain',
  poor: 'Poor',
  missing: 'Missing',
}

export const QUALITY_DESCRIPTION: Record<QualityFlag, string> = {
  good: 'The quality flag reports no acquisition issues.',
  uncertain: 'Possible acquisition disturbance: read the value together with its context.',
  poor: 'Acquisition compromised: the value should not be used on its own.',
  missing: 'No valid value received for this instant.',
}

export const REASON_LABEL: Record<QualityReason, string> = {
  motion: 'high motion during acquisition',
  contact: 'unstable sensor–skin contact',
  not_received: 'sample not received',
  out_of_sensor_range: 'value outside the sensor measuring range',
}

export const ACTIVITY_LABEL: Record<ActivityKind, string> = {
  rest: 'Rest',
  warmup: 'Warm-up',
  exercise: 'Exercise',
  recovery: 'Recovery',
  operational: 'Operational activity',
}

export const EVENT_KIND_LABEL: Record<EventKind, string> = {
  outside_personal_range: 'Value outside personal historical range',
  signal_quality: 'Signal quality to check',
  data_stale: 'Data not updated',
  crew_report: 'Shared by the crew member',
}

export const EVENT_STATUSES: readonly EventStatus[] = ['open', 'in_review', 'reviewed']

export const EVENT_STATUS_LABEL: Record<EventStatus, string> = {
  open: 'To review',
  in_review: 'In review',
  reviewed: 'Reviewed',
}

export const LINK_LABEL: Record<LinkState, string> = {
  connected: 'connected',
  degraded: 'degraded',
  offline: 'offline',
}

export function formatValue(parameter: ParameterId, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(PARAMETERS[parameter].decimals)
}

/* ---------- long-duration mission: daily indicators and check-in ---------- */

export interface DailyIndicatorDef {
  id: DailyIndicatorId
  label: string
  /** When/how it is measured, in plain language. */
  when: string
  unit: string
  decimals: number
}

export const DAILY_INDICATORS: Record<DailyIndicatorId, DailyIndicatorDef> = {
  resting_hr: { id: 'resting_hr', label: 'Resting heart rate', when: 'on waking', unit: 'bpm', decimals: 0 },
  sleep_duration: { id: 'sleep_duration', label: 'Sleep duration', when: 'last night', unit: 'h', decimals: 1 },
  resting_spo2: { id: 'resting_spo2', label: 'O₂ saturation', when: 'spot check', unit: '%', decimals: 0 },
  resting_resp_rate: { id: 'resting_resp_rate', label: 'Respiratory rate', when: 'resting capture', unit: 'breaths/min', decimals: 0 },
  hrv_rmssd: { id: 'hrv_rmssd', label: 'Heart-rate variability', when: 'resting ECG / PPG', unit: 'ms RMSSD', decimals: 0 },
  bp_systolic: { id: 'bp_systolic', label: 'Systolic pressure', when: 'cuff measurement', unit: 'mmHg', decimals: 0 },
  bp_diastolic: { id: 'bp_diastolic', label: 'Diastolic pressure', when: 'cuff measurement', unit: 'mmHg', decimals: 0 },
  body_temperature: { id: 'body_temperature', label: 'Body temperature', when: 'spot check', unit: '°C', decimals: 1 },
  activity_minutes: { id: 'activity_minutes', label: 'Exercise time', when: 'exercise log', unit: 'min', decimals: 0 },
  body_mass: { id: 'body_mass', label: 'Body mass', when: 'periodic check', unit: 'kg', decimals: 1 },
  sleep_efficiency: { id: 'sleep_efficiency', label: 'Sleep efficiency estimate', when: 'overnight wearable', unit: '%', decimals: 0 },
  active_energy: { id: 'active_energy', label: 'Active energy', when: 'exercise sessions', unit: 'kcal', decimals: 0 },
}

/** Additive, optional daily fields proposed to the backend. No clinical cutoffs. */
export const DAILY_INDICATOR_ORDER: DailyIndicatorId[] = [
  'resting_hr', 'sleep_duration', 'resting_spo2', 'resting_resp_rate', 'hrv_rmssd',
  'bp_systolic', 'bp_diastolic', 'body_temperature', 'activity_minutes', 'body_mass', 'sleep_efficiency', 'active_energy',
]

/** Three readings per pane. The first category remains deliberately minimal. */
export const HEALTH_CATEGORIES = [
  { id: 'today', label: 'Overview', indicators: ['resting_hr', 'sleep_duration', 'resting_spo2'] },
  { id: 'cardio', label: 'Heart', indicators: ['resting_hr', 'bp_systolic', 'hrv_rmssd'] },
  { id: 'breathing', label: 'Breathing', indicators: ['resting_spo2', 'resting_resp_rate', 'body_temperature'] },
  { id: 'recovery', label: 'Recovery', indicators: ['sleep_duration', 'sleep_efficiency', 'hrv_rmssd'] },
  { id: 'fitness', label: 'Physical health', indicators: ['activity_minutes', 'body_mass', 'resting_hr'] },
] as const satisfies ReadonlyArray<{ id: string; label: string; indicators: readonly DailyIndicatorId[] }>

export function formatDailyValue(indicator: DailyIndicatorId, value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(DAILY_INDICATORS[indicator].decimals)
}

type CheckInQuestion = keyof Omit<CheckInInput, 'note'>

/** Self-report questions. Every scale runs 1 (worst) → 5 (best). */
export const CHECK_IN_QUESTIONS: { id: CheckInQuestion; label: string; scale: [string, string, string, string, string] }[] = [
  { id: 'sleepQuality', label: 'How did you sleep?', scale: ['Very badly', 'Badly', 'OK', 'Well', 'Very well'] },
  { id: 'energy', label: 'How is your energy?', scale: ['Very low', 'Low', 'OK', 'Good', 'Very good'] },
  { id: 'mood', label: 'How is your mood?', scale: ['Very low', 'Low', 'OK', 'Good', 'Very good'] },
]
