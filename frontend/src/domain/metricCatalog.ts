import type { DailyIndicatorId, QualityFlag } from './types'
import type { NutrientId } from './nutrition'

/**
 * Bridge between the interface's indicators and the backend metric catalog
 * (schemas/metric_catalog.json, GET /api/v1/metrics). The catalog is the
 * source of truth for names and canonical units.
 */
export type BackendMetric =
  | 'heart_rate' | 'heart_rate_variability_rmssd' | 'respiratory_rate' | 'blood_oxygen_saturation' | 'body_temperature'
  | 'systolic_blood_pressure' | 'diastolic_blood_pressure' | 'sleep_duration' | 'sleep_efficiency'
  | 'exercise_duration' | 'active_energy_expenditure' | 'body_mass' | NutrientId

export interface IndicatorMapping {
  metric: BackendMetric
  /** Canonical unit in the backend catalog. */
  unit: string
  /** backend value × factor = value shown in the interface. */
  factor: number
  /** How several readings of one UTC day become the daily value. */
  daily: 'median' | 'sum' | 'last'
}

export const INDICATOR_METRIC: Record<DailyIndicatorId, IndicatorMapping> = {
  resting_hr: { metric: 'heart_rate', unit: 'bpm', factor: 1, daily: 'median' },
  hrv_rmssd: { metric: 'heart_rate_variability_rmssd', unit: 'ms', factor: 1, daily: 'median' },
  resting_resp_rate: { metric: 'respiratory_rate', unit: 'breaths/min', factor: 1, daily: 'median' },
  resting_spo2: { metric: 'blood_oxygen_saturation', unit: '%', factor: 1, daily: 'median' },
  body_temperature: { metric: 'body_temperature', unit: 'degC', factor: 1, daily: 'median' },
  bp_systolic: { metric: 'systolic_blood_pressure', unit: 'mmHg', factor: 1, daily: 'median' },
  bp_diastolic: { metric: 'diastolic_blood_pressure', unit: 'mmHg', factor: 1, daily: 'median' },
  sleep_duration: { metric: 'sleep_duration', unit: 'min', factor: 1 / 60, daily: 'sum' },
  sleep_efficiency: { metric: 'sleep_efficiency', unit: '%', factor: 1, daily: 'median' },
  activity_minutes: { metric: 'exercise_duration', unit: 'min', factor: 1, daily: 'sum' },
  active_energy: { metric: 'active_energy_expenditure', unit: 'kcal', factor: 1, daily: 'sum' },
  body_mass: { metric: 'body_mass', unit: 'kg', factor: 1, daily: 'last' },
}

export const NUTRIENT_UNIT: Record<NutrientId, string> = {
  energy_intake: 'kcal', protein_intake: 'g', fluid_intake: 'mL',
  vitamin_a_intake: 'ug', vitamin_c_intake: 'mg', vitamin_d_intake: 'ug', vitamin_k_intake: 'ug', vitamin_b12_intake: 'ug', folate_intake: 'ug',
  calcium_intake: 'mg', phosphorus_intake: 'mg', sodium_intake: 'mg', potassium_intake: 'mg', iron_intake: 'mg', magnesium_intake: 'mg', zinc_intake: 'mg',
}

export function indicatorOfMetric(metric: string): DailyIndicatorId | null {
  for (const [id, m] of Object.entries(INDICATOR_METRIC)) if (m.metric === metric) return id as DailyIndicatorId
  return null
}

/** Backend data-quality status → the interface's quality flag. */
export function qualityOfStatus(status: string | undefined): QualityFlag {
  if (status === 'acceptable') return 'good'
  if (status === 'unusable') return 'poor'
  if (status === 'degraded') return 'uncertain'
  return 'uncertain' // not_assessed: never shown as reliable
}

/** One backend measurement (PhysiologicalMeasurement). */
export interface BackendMeasurement {
  measurement_id: string
  crew_member_id: string
  metric: string
  unit: string
  value: number
  measured_at: string
  interval_end: string | null
  source: 'wearable' | 'medical_device' | 'manual_entry' | 'simulated'
  device_id: string | null
  data_quality?: { status?: string; flags?: string[]; notes?: string | null } | null
}

export interface DailyPoint {
  date: string
  value: number
  quality: QualityFlag
  count: number
}

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2
}

const QUALITY_RANK: Record<QualityFlag, number> = { good: 0, uncertain: 1, poor: 2, missing: 3 }

/**
 * Daily values for one indicator from raw backend measurements. Unusable
 * readings are kept out of the value but mark the day; sleep belongs to the
 * day it ends. Days without readings are simply absent (never zero).
 */
export function dailyFromMeasurements(indicator: DailyIndicatorId, items: BackendMeasurement[]): DailyPoint[] {
  const map = INDICATOR_METRIC[indicator]
  const byDay = new Map<string, BackendMeasurement[]>()
  for (const m of items) {
    if (m.metric !== map.metric) continue
    const at = map.metric === 'sleep_duration' || map.metric === 'sleep_efficiency' ? (m.interval_end ?? m.measured_at) : m.measured_at
    const day = at.slice(0, 10)
    if (!byDay.has(day)) byDay.set(day, [])
    byDay.get(day)!.push(m)
  }
  const out: DailyPoint[] = []
  for (const [date, ms] of [...byDay.entries()].sort(([a], [b]) => (a < b ? -1 : 1))) {
    const usable = ms.filter((m) => qualityOfStatus(m.data_quality?.status) !== 'poor')
    const quality = usable.map((m) => qualityOfStatus(m.data_quality?.status)).reduce((w, q) => (QUALITY_RANK[q] > QUALITY_RANK[w] ? q : w), 'good' as QualityFlag)
    if (!usable.length) {
      out.push({ date, value: NaN, quality: 'poor', count: ms.length })
      continue
    }
    const vals = usable.sort((a, b) => (a.measured_at < b.measured_at ? -1 : 1)).map((m) => m.value * map.factor)
    const value = map.daily === 'sum' ? vals.reduce((a, b) => a + b, 0) : map.daily === 'last' ? vals[vals.length - 1] : median(vals)
    out.push({ date, value, quality: usable.length < ms.length && quality === 'good' ? 'uncertain' : quality, count: ms.length })
  }
  return out
}

/** EvaluationResult from the backend (schemas/evaluation_result.schema.json), fields used by the interface. */
export interface BackendEvaluation {
  evaluation_id: string
  crew_member_id: string
  domain: 'vital_signs' | 'sleep' | 'physical_activity' | 'nutrition' | 'cognition' | string
  mission_phase?: string | null
  window_start: string
  window_end: string
  evaluated_at?: string
  status: 'nominal' | 'attention' | 'alert' | 'insufficient_data' | string
  summary: string
  data_quality?: { status?: string; completeness?: number | null; flags?: string[]; notes?: string | null } | null
  findings: {
    metric: string
    unit: string
    status: string
    observed_value?: number | null
    baseline_value?: number | null
    absolute_deviation?: number | null
    relative_deviation?: number | null
    explanation: string
  }[]
  algorithm?: { name: string; version: string } | null
}

/** PersonalBaseline from the backend (schemas/personal_baseline.schema.json). */
export interface BackendBaseline {
  baseline_id: string
  crew_member_id: string
  metric: string
  unit: string
  status: 'established' | 'provisional' | 'insufficient_data' | string
  window_start: string
  window_end: string
  sample_count: number
  statistics: { mean: number | null; standard_deviation: number | null; median: number | null; median_absolute_deviation: number | null; minimum: number | null; maximum: number | null } | null
  algorithm?: { name: string; version: string } | null
}
