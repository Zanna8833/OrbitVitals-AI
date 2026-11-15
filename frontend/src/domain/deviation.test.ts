import { describe, expect, it } from 'vitest'
import { completeness, deviationsOf, latestCell, rangeUnits } from './deviation'
import type { DailyIndicatorSeries } from './types'

const series = (values: (number | null)[], baseline = { low: 50, median: 60, high: 70, fromDay: 1, toDay: 7, basis: '' }): DailyIndicatorSeries => ({
  crewId: 'c', indicator: 'resting_hr', unit: 'bpm', source: '', simulated: false, baseline,
  days: values.map((v, i) => ({ date: `2026-10-${String(i + 1).padStart(2, '0')}`, missionDay: i + 1, value: v, quality: v === null ? 'missing' : 'good' })),
})

describe('range units', () => {
  it('maps the usual range to ±1', () => {
    const s = series([60])
    expect(rangeUnits(60, s)).toBe(0)
    expect(rangeUnits(70, s)).toBe(1)
    expect(rangeUnits(40, s)).toBe(-2)
  })
  it('is unknown without a baseline', () => {
    expect(rangeUnits(60, { ...series([60]), baseline: null })).toBeNull()
  })
  it('lists each day, gaps included', () => {
    expect(deviationsOf(series([60, null, 75])).map((d) => d.units)).toEqual([0, null, 1.5])
  })
})

describe('latest cell', () => {
  it('counts consecutive reliable days on the same side', () => {
    const c = latestCell(series([60, 72, 74, 75]))
    expect(c).toMatchObject({ value: 75, units: 1.5, streak: 3 })
  })
  it('falls back to the last value when none is reliable', () => {
    const s = series([61])
    s.days[0].quality = 'uncertain'
    expect(latestCell(s)).toMatchObject({ value: 61, quality: 'uncertain', units: null })
  })
})

describe('completeness', () => {
  it('only counts indicators measured at least once', () => {
    const a = series([60, null, 62])
    const never = { ...series([null, null, null]), indicator: 'body_mass' as const }
    expect(completeness([a, never], 3, 3).map((d) => d.share)).toEqual([1, 0, 1])
  })
})
