import { describe, expect, it } from 'vitest'
import { dailyFromMeasurements, indicatorOfMetric, qualityOfStatus, type BackendMeasurement } from './metricCatalog'

const m = (over: Partial<BackendMeasurement>): BackendMeasurement => ({
  measurement_id: 'x', crew_member_id: 'c', metric: 'heart_rate', unit: 'bpm', value: 60, measured_at: '2026-10-01T08:00:00Z',
  interval_end: null, source: 'simulated', device_id: null, data_quality: { status: 'acceptable' }, ...over,
})

describe('backend metric bridge', () => {
  it('maps names and quality', () => {
    expect(indicatorOfMetric('blood_oxygen_saturation')).toBe('resting_spo2')
    expect(qualityOfStatus('degraded')).toBe('uncertain')
    expect(qualityOfStatus('not_assessed')).toBe('uncertain')
  })
  it('converts sleep minutes to hours on the day the night ends', () => {
    const d = dailyFromMeasurements('sleep_duration', [m({ metric: 'sleep_duration', unit: 'min', value: 450, measured_at: '2026-10-01T22:30:00Z', interval_end: '2026-10-02T06:00:00Z' })])
    expect(d).toEqual([{ date: '2026-10-02', value: 7.5, quality: 'good', count: 1 }])
  })
  it('sums exercise sessions and keeps unusable readings out of the value', () => {
    const ex = dailyFromMeasurements('activity_minutes', [m({ metric: 'exercise_duration', value: 30 }), m({ metric: 'exercise_duration', value: 25, measured_at: '2026-10-01T15:00:00Z' })])
    expect(ex[0].value).toBe(55)
    const hr = dailyFromMeasurements('resting_hr', [m({ value: 60 }), m({ value: 250, data_quality: { status: 'unusable' } })])
    expect(hr[0]).toMatchObject({ value: 60, quality: 'uncertain' })
  })
})
