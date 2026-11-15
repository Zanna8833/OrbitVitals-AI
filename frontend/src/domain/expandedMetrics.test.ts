import { describe, expect, it } from 'vitest'
import { DAILY_INDICATOR_ORDER, HEALTH_CATEGORIES } from './parameters'
import { measurementValue, withDemoMeasurements, type DeviceMeasurement } from './measurements'
import { generateDailyIndicators } from '../data/mock/daily'
import { getScenario } from '../data/mock/scenarios'

const day = '2026-11-14T10:40:00Z'
const testScenario = getScenario('session')

describe('expanded long-duration indicators', () => {
  it('keeps exactly three focused readings in every UX category', () => {
    expect(HEALTH_CATEGORIES.every((c) => c.indicators.length === 3)).toBe(true)
    for (const group of HEALTH_CATEGORIES) {
      expect(group.indicators.every((id) => DAILY_INDICATOR_ORDER.includes(id))).toBe(true)
    }
  })

  it('creates synthetic, timestamped, quality-labelled data without medical cutoffs', () => {
    const result = generateDailyIndicators('crew-a', day, testScenario.flags)
    expect(result).toHaveLength(DAILY_INDICATOR_ORDER.length)
    for (const item of result) {
      expect(item.simulated).toBe(true)
      expect(item.source).toMatch(/synthetic/i)
      expect(item.days).toHaveLength(15)
      expect(item.days.every((reading) => reading.quality && reading.date)).toBe(true)
      expect(item.baseline?.basis).toContain('not a clinical reference')
    }
  })

  it('supports paired cuff values and records both with the same acquisition timestamp', () => {
    const result = generateDailyIndicators('crew-a', day, testScenario.flags)
    const systolic = measurementValue('bp_systolic', result, 0)
    const diastolic = measurementValue('bp_diastolic', result, 0)
    const capture: DeviceMeasurement = {
      id: 'DEMO-BP', crewId: 'crew-a', indicator: 'bp_systolic',
      value: systolic, quality: 'good', simulated: true, deviceLabel: 'Demo cuff',
      acquiredAt: day, savedAtMs: 100, signal: 'clear', context: 'Scheduled test',
    }
    const updated = withDemoMeasurements(result, [capture, { ...capture, id: 'DEMO-BP-DIA', indicator: 'bp_diastolic', value: diastolic }], 15, '2026-11-14')
    const sys = updated.find((x) => x.indicator === 'bp_systolic')!
    const dia = updated.find((x) => x.indicator === 'bp_diastolic')!
    expect(sys.days.at(-1)?.value).toBe(systolic)
    expect(dia.days.at(-1)?.value).toBe(diastolic)
    expect(sys.days.at(-1)?.date).toBe(dia.days.at(-1)?.date)
  })
})
