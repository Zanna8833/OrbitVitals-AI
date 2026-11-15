import { describe, expect, it } from 'vitest'
import { sliceToDay, viewMission } from './viewDay'
import type { MissionStatus } from './types'

const mission = { now: '2026-10-25T20:00:00Z', missionStartDate: '2026-09-28' } as MissionStatus

describe('view day', () => {
  it('moves "now" to the end of a past day and never into the future', () => {
    expect(viewMission(mission, 10)).toMatchObject({ day: 10, actualDay: 28, past: true, mission: { now: '2026-10-07T20:00:00Z' } })
    expect(viewMission(mission, 40)).toMatchObject({ day: 28, past: false })
    expect(viewMission(mission, null).mission).toBe(mission)
  })
  it('cuts the days after the selected one', () => {
    const s = { indicator: 'resting_hr', days: [1, 2, 3].map((d) => ({ missionDay: d, date: '', value: 60, quality: 'good' })) } as never
    expect(sliceToDay([s], 2)[0].days).toHaveLength(2)
  })
})
