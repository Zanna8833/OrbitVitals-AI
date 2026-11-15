import { describe, expect, it } from 'vitest'
import { REPLAY, replayClock } from './clock'
import { MockDataSource } from './MockDataSource'
import { SESSION_START } from './generator'

const START_MS = 1_000_000
/** A replay clock whose "real" time is controlled by the test. */
function controlledReplay() {
  let realMs = START_MS
  const clock = replayClock(START_MS, () => realMs)
  return { clock, advanceSeconds: (s: number) => (realMs += s * 1000) }
}

describe('replayClock', () => {
  it('starts at 10:30 UTC and advances one 10 s sample per 10 s of real time', () => {
    const { clock, advanceSeconds } = controlledReplay()
    expect(clock()).toBe('2026-11-14T10:30:00Z')
    advanceSeconds(9)
    expect(clock()).toBe('2026-11-14T10:30:00Z')
    advanceSeconds(1)
    expect(clock()).toBe('2026-11-14T10:30:10Z')
  })

  it('stops at the end of the scheduled session (10:45 UTC)', () => {
    const { clock, advanceSeconds } = controlledReplay()
    advanceSeconds(3600)
    expect(clock()).toBe('2026-11-14T10:45:00Z')
    expect(REPLAY.endOffsetS).toBeGreaterThan(REPLAY.startOffsetS)
  })
})

describe('MockDataSource with a live replay clock', () => {
  it('receives new samples as the simulated clock advances', async () => {
    const { clock, advanceSeconds } = controlledReplay()
    const ds = new MockDataSource('nominal', 0, clock)
    const count = async () => (await ds.getSeries('crew-a', ['heart_rate'], SESSION_START, '2026-11-14T11:00:00Z'))[0].samples.length
    const before = await count()
    advanceSeconds(60)
    expect((await count()) - before).toBe(6)
    expect((await ds.getMissionStatus()).now).toBe('2026-11-14T10:31:00Z')
  })

  it('offline scenario: the link is up before 10:34 and drops live at 10:34', async () => {
    const { clock, advanceSeconds } = controlledReplay()
    const ds = new MockDataSource('offline', 0, clock)
    expect((await ds.getMissionStatus()).link.state).toBe('connected')
    await expect(ds.sendCrewMessage('crew-a', 'ack_no_action', null)).resolves.toBeTruthy()
    advanceSeconds(4 * 60)
    const status = await ds.getMissionStatus()
    expect(status.link).toMatchObject({ state: 'offline', since: '2026-11-14T10:34:00Z' })
    await expect(ds.sendCrewMessage('crew-a', 'ack_no_action', null)).rejects.toMatchObject({ code: 'unavailable' })
  })

  it('stale scenario: the open stale-data window follows the simulated clock', async () => {
    const { clock, advanceSeconds } = controlledReplay()
    const ds = new MockDataSource('stale', 0, clock)
    expect((await ds.getEvent('EV-0144')).window.end).toBe('2026-11-14T10:30:00Z')
    advanceSeconds(120)
    expect((await ds.getEvent('EV-0144')).window.end).toBe('2026-11-14T10:32:00Z')
    expect((await ds.getCrewSnapshot('crew-c')).device.lastReceivedAt).toBe('2026-11-14T10:22:00Z')
  })
})
