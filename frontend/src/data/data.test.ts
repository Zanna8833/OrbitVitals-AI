import { describe, expect, it } from 'vitest'
import { MockDataSource } from './mock/MockDataSource'
import { SCENARIOS } from './mock/scenarios'
import { SESSION_START, SIM_NOW } from './mock/generator'
import { mapCode } from './http/HttpDataSource'
import { DataSourceError } from './DataSource'
import { compareWithBand, samplesInWindow } from '../domain/observations'

const ds = (id: string) => new MockDataSource(id, 0)

describe('MockDataSource', () => {
  it('is deterministic', async () => {
    const a = await ds('session').getSeries('crew-a', ['heart_rate'], SESSION_START, SIM_NOW)
    const b = await ds('session').getSeries('crew-a', ['heart_rate'], SESSION_START, SIM_NOW)
    expect(a).toEqual(b)
    expect(a[0].samples.length).toBe(241)
  })

  it('marks every dataset as simulated', async () => {
    const m = await ds('nominal').getMissionStatus()
    expect(m.simulated).toBe(true)
    const [s] = await ds('nominal').getSeries('crew-b', ['spo2'], SESSION_START, SIM_NOW)
    expect(s.source.simulated).toBe(true)
  })

  it('nominal scenario has no events and no poor samples', async () => {
    const d = ds('nominal')
    expect(await d.listEvents()).toEqual([])
    const all = await d.getSeries('crew-b', ['heart_rate', 'spo2', 'resp_rate'], SESSION_START, SIM_NOW)
    expect(all.flatMap((x) => x.samples).some((x) => x.quality === 'poor' || x.quality === 'missing')).toBe(false)
  })

  it('every scenario loads for every crew member', async () => {
    for (const sc of SCENARIOS) {
      const d = ds(sc.id)
      for (const c of await d.listCrew()) {
        const snap = await d.getCrewSnapshot(c.id)
        expect(snap.parameters).toHaveLength(4)
      }
    }
  })

  it('quality scenario flags SpO2 samples in the event window', async () => {
    const d = ds('quality')
    const [ev] = await d.listEvents()
    expect(ev.kind).toBe('signal_quality')
    const [s] = await d.getSeries(ev.crewId, ['spo2'], SESSION_START, SIM_NOW)
    const win = samplesInWindow(s.samples, ev.window.start, ev.window.end)
    expect(win.filter((x) => x.quality !== 'good').length).toBeGreaterThan(win.length / 2)
  })

  it('review event: Crew A heart rate exceeds own history with good quality', async () => {
    const d = ds('review')
    const [ev] = await d.listEvents()
    const [s] = await d.getSeries('crew-a', ['heart_rate'], SESSION_START, SIM_NOW)
    const band = await d.getReferenceBand('crew-a', 'heart_rate', 'EX-CICLO-30')
    const cmp = compareWithBand(samplesInWindow(s.samples, ev.window.start, ev.window.end), band!, SESSION_START)
    expect(cmp.above).toBeGreaterThan(cmp.compared / 3)
    // without the injected condition the same window stays mostly within the band
    const [base] = await ds('nominal').getSeries('crew-a', ['heart_rate'], SESSION_START, SIM_NOW)
    const cmp0 = compareWithBand(samplesInWindow(base.samples, ev.window.start, ev.window.end), band!, SESSION_START)
    expect(cmp0.above).toBeLessThan(cmp0.compared * 0.3)
  })

  it('stale scenario: Crew C stops at 10:22 and is not reporting', async () => {
    const snap = await ds('stale').getCrewSnapshot('crew-c')
    expect(snap.device.lastReceivedAt).toBe('2026-11-14T10:22:00Z')
    expect(snap.device.state).toBe('not_reporting')
  })

  it('offline scenario: link offline, data cut at 10:34, messages refused', async () => {
    const d = ds('offline')
    expect((await d.getMissionStatus()).link.state).toBe('offline')
    const snap = await d.getCrewSnapshot('crew-a')
    expect(snap.device.lastReceivedAt).toBe('2026-11-14T10:34:00Z')
    await expect(d.sendCrewMessage('crew-a', 'ack_no_action', null)).rejects.toMatchObject({ code: 'unavailable' })
  })

  it('updates status, annotations and messages in memory', async () => {
    const d = ds('session')
    const [ev] = await d.listEvents({ crewId: 'crew-a' })
    await d.updateEventStatus(ev.id, 'reviewed')
    await d.addAnnotation(ev.id, '  note  ')
    const after = await d.getEvent(ev.id)
    expect(after.status).toBe('reviewed')
    expect(after.annotations[0].text).toBe('note')
    await d.sendCrewMessage('crew-a', 'review_after', ev.id)
    expect(await d.listCrewMessages('crew-a')).toHaveLength(1)
    expect((await d.getCrewSnapshot('crew-a')).openEvents).toBe(0)
  })

  it('rejects unknown ids and empty notes', async () => {
    const d = ds('session')
    await expect(d.getEvent('nope')).rejects.toBeInstanceOf(DataSourceError)
    await expect(d.getCrewSnapshot('nope')).rejects.toMatchObject({ code: 'not_found' })
    const [ev] = await d.listEvents()
    await expect(d.addAnnotation(ev.id, '   ')).rejects.toMatchObject({ code: 'bad_request' })
  })

  it('returned data cannot mutate the store', async () => {
    const d = ds('session')
    const [ev] = await d.listEvents()
    ev.status = 'reviewed'
    expect((await d.getEvent(ev.id)).status).toBe('open')
  })
})

describe('HTTP error mapping', () => {
  it('maps status codes to UI error codes', () => {
    expect(mapCode(undefined, 404)).toBe('not_found')
    expect(mapCode(undefined, 422)).toBe('bad_request')
    expect(mapCode(undefined, 503)).toBe('unavailable')
    expect(mapCode('unauthorized', 200)).toBe('unauthorized')
    expect(mapCode(undefined, 500)).toBe('internal')
  })
})

describe('Sleep-aid plan (mock)', () => {
  it('seeds a demo plan with one uncovered night and keeps edits', async () => {
    const d = new MockDataSource('session', 0)
    const plan = await d.listSleepAidPlan('2026-11-10', '2026-11-30')
    const byNight = new Map<string, number>()
    for (const p of plan) byNight.set(p.night, (byNight.get(p.night) ?? 0) + 1)
    expect([...byNight.values()]).toContain(3)
    await d.setSleepAidPlan('crew-c', '2026-11-16', true)
    expect((await d.listSleepAidPlan('2026-11-16', '2026-11-16')).map((p) => p.crewId)).toContain('crew-c')
    await d.setSleepAidPlan('crew-c', '2026-11-16', false)
    expect((await d.listSleepAidPlan('2026-11-16', '2026-11-16')).map((p) => p.crewId)).not.toContain('crew-c')
  })

  it('rejects past nights and unknown crew', async () => {
    const d = new MockDataSource('session', 0)
    await expect(d.setSleepAidPlan('crew-a', '2026-11-01', true)).rejects.toMatchObject({ code: 'bad_request' })
    await expect(d.setSleepAidPlan('nobody', '2026-11-20', true)).rejects.toMatchObject({ code: 'not_found' })
  })
})
