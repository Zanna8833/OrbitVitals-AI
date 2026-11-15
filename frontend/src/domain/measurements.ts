import type { DailyIndicatorId, DailyIndicatorSeries, QualityFlag } from './types'

/** Hardware models are illustrative: no device is paired or queried by the browser. */
export interface MeasurementDevice {
  indicator: DailyIndicatorId
  name: string
  kind: string
  expected: string
  preparation: string[]
  action: string
  duration: string
}

export const MEASUREMENT_DEVICES: MeasurementDevice[] = [
  {
    indicator: 'resting_spo2',
    name: 'Oxygen saturation',
    kind: 'Finger pulse oximeter',
    expected: 'SpO₂ (%)',
    preparation: ['Use the assigned device and follow its instructions.', 'Check that the sensor is positioned and reporting.', 'Remain still while the device acquires its reading.'],
    action: 'Simulate oximeter reading', duration: 'Short spot measurement',
  },
  {
    indicator: 'resting_hr',
    name: 'Resting heart rate',
    kind: 'Chest ECG / heart-rate sensor',
    expected: 'Heart rate (bpm)',
    preparation: ['Use the assigned sensor and follow its instructions.', 'Ensure the sensor reports contact and signal quality.', 'Record the activity context, particularly if you have been exercising.'],
    action: 'Simulate heart-rate reading', duration: 'Short resting measurement',
  },
  {
    indicator: 'bp_systolic',
    name: 'Blood pressure',
    kind: 'Digital blood pressure cuff',
    expected: 'Systolic / diastolic (mmHg)',
    preparation: ['Use the assigned cuff and its validated operating instructions.', 'Check fit, placement, and acquisition status.', 'Record whether this is a scheduled resting check or an additional reading.'],
    action: 'Simulate blood pressure capture', duration: 'Short paired measurement',
  },
  {
    indicator: 'body_temperature',
    name: 'Body temperature',
    kind: 'Digital thermometer',
    expected: 'Body temperature (°C)',
    preparation: ['Use the assigned thermometer and its operating instructions.', 'Check that the device confirms a completed reading.', 'Record the activity context with the result.'],
    action: 'Simulate thermometer capture', duration: 'Short spot measurement',
  },
  {
    indicator: 'body_mass',
    name: 'Body mass',
    kind: 'Assigned mass measurement device',
    expected: 'Mass (kg)',
    preparation: ['Follow the device-specific procedure approved for the mission.', 'Check that the instrument has completed its acquisition.', 'Review the saved result and its timestamp.'],
    action: 'Simulate mass capture', duration: 'Periodic measurement',
  },
  {
    indicator: 'sleep_duration',
    name: 'Sleep duration',
    kind: 'Wrist sleep wearable',
    expected: 'Estimated sleep (hours)',
    preparation: ['This is an import of last night’s wearable estimate, not a spot measurement.', 'Check that the wearable contains a completed night of data.', 'Review the timestamp and estimate quality before saving.'],
    action: 'Simulate wearable import', duration: 'Completed overnight recording',
  },
]

/** Never imply a numerical quality score or a clinical cut-off. */
export type DemoSignal = 'clear' | 'motion'

export interface DeviceMeasurement {
  id: string
  crewId: string
  indicator: DailyIndicatorId
  value: number
  quality: Exclude<QualityFlag, 'poor' | 'missing'>
  simulated: true
  deviceLabel: string
  acquiredAt: string
  savedAtMs: number
  signal: DemoSignal
  context: string
}

export function measurementValue(indicator: DailyIndicatorId, daily: DailyIndicatorSeries[], index: number): number {
  const series = daily.find((s) => s.indicator === indicator)
  const latest = [...(series?.days ?? [])].reverse().find((d) => d.value !== null)
  const fallback: Record<DailyIndicatorId, number> = {
    resting_hr: 62, resting_spo2: 98, sleep_duration: 7.1,
    resting_resp_rate: 15, hrv_rmssd: 45, bp_systolic: 116, bp_diastolic: 76,
    body_temperature: 36.6, activity_minutes: 60, body_mass: 74, sleep_efficiency: 85,
  }
  const value = latest?.value ?? fallback[indicator]
  const decimals = indicator === 'sleep_duration' || indicator === 'body_temperature' || indicator === 'body_mass' ? 1 : 0
  const jitter = decimals ? [0, 0.1, -0.1][index % 3] : [-1, 1, 0][index % 3]
  return Number(Math.max(0, Math.min(indicator === 'resting_spo2' || indicator === 'sleep_efficiency' ? 100 : Infinity, value + jitter)).toFixed(decimals))
}

/** Overlay demo device captures onto the daily trend without changing its personal baseline. */
export function withDemoMeasurements(series: DailyIndicatorSeries[], captures: DeviceMeasurement[], day: number, date: string): DailyIndicatorSeries[] {
  if (!captures.length) return series
  return series.map((s) => {
    const newest = captures.filter((m) => m.indicator === s.indicator && m.acquiredAt.slice(0, 10) === date)
      .sort((a, b) => b.savedAtMs - a.savedAtMs)[0]
    if (!newest) return s
    const days = s.days.filter((d) => d.missionDay !== day)
    days.push({ date, missionDay: day, value: newest.value, quality: newest.quality })
    days.sort((a, b) => a.missionDay - b.missionDay)
    return { ...s, days, source: `${newest.deviceLabel} · simulated capture in this browser` }
  })
}
