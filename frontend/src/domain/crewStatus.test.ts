import { describe, expect, it } from 'vitest'
import { describeCollection, describeSensors } from './crewStatus'
import { MockDataSource } from '../data/mock/MockDataSource'
import { SESSION_START, SIM_NOW } from '../data/mock/generator'
import { PARAMETER_ORDER } from './parameters'

const NOW = '2026-11-14T10:40:00Z'

describe('describeCollection (crew view)', () => {
  it('reports active collection for current data', () => {
    expect(describeCollection('2026-11-14T10:39:50Z', NOW, 10, false)).toMatchObject({ level: 'good', headline: 'Data collection active' })
  })
  it('reports a delay without asking for action', () => {
    const s = describeCollection('2026-11-14T10:38:30Z', NOW, 10, false)
    expect(s.level).toBe('uncertain')
    expect(s.detail).toContain('No action needed')
  })
  it('reports a device that stopped sending, with the time of the last data', () => {
    const s = describeCollection('2026-11-14T10:22:00Z', NOW, 10, false)
    expect(s).toMatchObject({ level: 'poor', headline: 'The device is not sending data' })
    expect(s.detail).toContain('10:22 UTC')
  })
  it('distinguishes "never received" from "stopped"', () => {
    expect(describeCollection(null, NOW, 10, false).level).toBe('missing')
  })
  it('a lost ground link takes precedence over freshness', () => {
    expect(describeCollection('2026-11-14T10:39:50Z', NOW, 10, true).headline).toBe('Transmission to ground paused')
  })
})

describe('describeSensors (crew view)', () => {
  const sensorsFor = async (scenario: string, crewId: string) => {
    const series = await new MockDataSource(scenario, 0).getSeries(crewId, PARAMETER_ORDER, SESSION_START, SIM_NOW)
    return describeSensors(series, SIM_NOW)
  }

  it('groups parameters by physical device', async () => {
    const sensors = await sensorsFor('nominal', 'crew-a')
    expect(sensors.map((s) => s.parameters)).toEqual([['heart_rate', 'resp_rate', 'motion'], ['spo2']])
    expect(sensors.every((s) => s.level === 'good' && s.earlierNote === null)).toBe(true)
  })

  it('mentions an earlier, resolved disturbance once and quietly', async () => {
    const sensors = await sensorsFor('quality', 'crew-b')
    const oximeter = sensors.find((s) => s.parameters.includes('spo2'))!
    expect(oximeter.level).toBe('good')
    expect(oximeter.earlierNote).toMatch(/^Signal disturbed between \d\d:\d\d and \d\d:\d\d UTC\. No action needed/)
  })

  it('tells a disturbed signal apart from a reception gap', async () => {
    const sensors = await sensorsFor('quality', 'crew-b')
    const byLabel = Object.fromEntries(sensors.map((s) => [s.parameters.includes('spo2') ? 'oximeter' : 'strap', s]))
    expect(byLabel.oximeter.signalDisturbed).toBe(true)
    // The chest strap only had a short respiratory-rate gap: data not received, signal not disturbed.
    expect(byLabel.strap.earlierNote).toMatch(/^Data not received/)
    expect(byLabel.strap.signalDisturbed).toBe(false)
  })

  it('reports no recent data for a device that stopped', async () => {
    const sensors = await sensorsFor('stale', 'crew-c')
    expect(sensors.every((s) => s.level === 'missing')).toBe(true)
  })
})
