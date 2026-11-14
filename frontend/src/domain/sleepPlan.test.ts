import { describe, expect, it } from 'vitest'
import { addDays, coverageOf, isPlanned, nightLabel, nightsFrom, wouldUncover } from './sleepPlan'
import type { SleepAidPlanEntry } from './types'

const e = (crewId: string, night: string): SleepAidPlanEntry => ({ crewId, night, updatedAt: '', simulated: true })
const crew = ['a', 'b', 'c']

describe('sleep-aid coordination', () => {
  it('lists consecutive nights across a month boundary', () => {
    expect(nightsFrom('2026-11-29', 3)).toEqual(['2026-11-29', '2026-11-30', '2026-12-01'])
    expect(addDays('2026-11-14', -1)).toBe('2026-11-13')
  })

  it('counts who stays without a sleep aid', () => {
    const c = coverageOf([e('a', '2026-11-14'), e('b', '2026-11-14'), e('a', '2026-11-15')], crew, '2026-11-14')
    expect(c).toMatchObject({ planned: ['a', 'b'], available: 1, total: 3, uncovered: false })
  })

  it('flags a night when everyone planned a sleep aid', () => {
    const all = crew.map((id) => e(id, '2026-11-18'))
    expect(coverageOf(all, crew, '2026-11-18').uncovered).toBe(true)
  })

  it('warns before the last available crew member adds the same night', () => {
    const plan = [e('a', '2026-11-16'), e('b', '2026-11-16')]
    expect(wouldUncover(plan, crew, 'c', '2026-11-16')).toBe(true)
    expect(wouldUncover(plan, crew, 'c', '2026-11-17')).toBe(false)
    // already planned: no new warning
    expect(wouldUncover([...plan, e('c', '2026-11-16')], crew, 'c', '2026-11-16')).toBe(false)
    expect(isPlanned(plan, 'a', '2026-11-16')).toBe(true)
  })

  it('labels nights in UTC', () => {
    expect(nightLabel('2026-11-14')).toEqual({ weekday: 'Sat', day: '14', month: 'Nov' })
  })
})
