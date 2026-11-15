import { describe, expect, it } from 'vitest'
import { pillarsOf } from './pillars'
import { evaluateIndicator } from './crewHealth'
import type { DailyIndicatorSeries } from './types'

const series = (values: (number | null)[], quality: ('good' | 'uncertain')[] = []): DailyIndicatorSeries => ({
  crewId: 'a',
  indicator: 'resting_hr',
  unit: 'bpm',
  source: 'test',
  simulated: true,
  baseline: { low: 56, median: 59, high: 62, fromDay: 1, toDay: 7, basis: '' },
  days: values.map((v, i) => ({ date: `2026-11-${String(i + 1).padStart(2, '0')}`, missionDay: i + 1, value: v, quality: v === null ? 'missing' : (quality[i] ?? 'good') })),
})

describe('pillars', () => {
  it('counts reliable, uncertain and missing days', () => {
    const s = series([58, 59, null, 60, 61], ['good', 'uncertain'])
    const p = pillarsOf(s, evaluateIndicator(s, 5))
    expect(p.quality).toMatchObject({ reliable: 3, total: 5, uncertainDays: 1, missingDays: 1, latestQuality: 'good' })
  })

  it('reports a sustained change and its size against the usual median', () => {
    const s = series([58, 59, 60, 64, 65, 67, 65])
    const p = pillarsOf(s, evaluateIndicator(s, 7))
    expect(p.trend).toMatchObject({ position: 'above', streakDays: 4, delta: 6, sustained: true })
    expect(p.baseline).toMatchObject({ low: 56, high: 62, fromDay: 1, toDay: 7 })
  })

  it('does not call a single day a sustained change', () => {
    const s = series([58, 59, 60, 59, 64])
    expect(pillarsOf(s, evaluateIndicator(s, 5)).trend.sustained).toBe(false)
  })
})
