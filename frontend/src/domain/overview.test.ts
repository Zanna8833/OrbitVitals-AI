import { describe, expect, it } from 'vitest'
import { initialsOf, summarizeOverview } from './overview'
import { MockDataSource } from '../data/mock/MockDataSource'

describe('summarizeOverview', () => {
  it('counts events to review and crew members with current data (Full session)', async () => {
    const ds = new MockDataSource('session', 0)
    const [mission, crew, events] = await Promise.all([ds.getMissionStatus(), ds.listCrew(), ds.listEvents()])
    const snapshots = await Promise.all(crew.map((c) => ds.getCrewSnapshot(c.id)))
    const s = summarizeOverview(snapshots, events, mission.now)
    expect(s).toMatchObject({ toReview: 3, inReview: 0, crewTotal: 3, upToDate: 2 })
    expect(s.notUpToDate).toEqual([{ name: 'Crew C', lastReceivedAt: '2026-11-14T10:22:00Z', freshness: 'stale' }])
  })

  it('excludes reviewed events and counts those in review', async () => {
    const ds = new MockDataSource('session', 0)
    await ds.updateEventStatus('EV-0142', 'reviewed')
    await ds.updateEventStatus('EV-0143', 'in_review')
    const s = summarizeOverview([], await ds.listEvents(), '2026-11-14T10:40:00Z')
    expect(s).toMatchObject({ toReview: 2, inReview: 1 })
  })
})

describe('initialsOf', () => {
  it('uses the pseudonym letter for "Crew X" and initials otherwise', () => {
    expect(initialsOf('Crew A')).toBe('A')
    expect(initialsOf('Maria Rossi')).toBe('MR')
    expect(initialsOf('Solo')).toBe('S')
  })
})
