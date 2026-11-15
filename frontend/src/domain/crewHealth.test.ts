import { describe, expect, it } from 'vitest'
import { checkedInOn, evaluateIndicator, healthOptions, summarizeHealth } from './crewHealth'
import type { DailyIndicatorSeries, DailyValue } from './types'
import { MockDataSource } from '../data/mock/MockDataSource'
import { missionDayOf } from '../data/mock/daily'

const day = (missionDay: number, value: number | null, quality: DailyValue['quality'] = 'good'): DailyValue => ({
  date: `2026-11-${String(missionDay).padStart(2, '0')}`,
  missionDay,
  value,
  quality: value === null ? 'missing' : quality,
})
const series = (days: DailyValue[]): DailyIndicatorSeries => ({
  crewId: 'x',
  indicator: 'resting_hr',
  unit: 'bpm',
  days,
  baseline: { low: 56, median: 58, high: 60, fromDay: 1, toDay: 7, basis: '' },
  source: '',
  simulated: true,
})

describe('evaluateIndicator', () => {
  it('reports values within the usual range', () => {
    const e = evaluateIndicator(series([day(1, 58), day(2, 59)]), 2)
    expect(e).toMatchObject({ position: 'within', streakDays: 0, headline: 'Within your usual range', measuredToday: true, repeatSuggested: false })
  })

  it('counts consecutive days on the same side, skipping missing days', () => {
    const e = evaluateIndicator(series([day(1, 58), day(2, 63), day(3, null), day(4, 65), day(5, 66)]), 5)
    expect(e).toMatchObject({ position: 'above', streakDays: 3, headline: 'Higher than your usual for 3 days' })
  })

  it('suggests repeating an uncertain or missing reading today', () => {
    expect(evaluateIndicator(series([day(1, 58), day(2, 59, 'uncertain')]), 2)).toMatchObject({ repeatSuggested: true, latest: { value: 58 }, position: 'within' })
    expect(evaluateIndicator(series([day(1, 58)]), 2)).toMatchObject({ measuredToday: false, repeatSuggested: true })
  })

  it('speaks to the crew member ("your") or about them ("their")', () => {
    const s = series([day(1, 58), day(2, 63), day(3, 64)])
    expect(evaluateIndicator(s, 3, 'their').headline).toBe('Higher than their usual for 2 days')
  })

  it('says so when there is no usual range yet', () => {
    const e = evaluateIndicator({ ...series([day(1, 58)]), baseline: null }, 1)
    expect(e.position).toBeNull()
    expect(e.headline).toBe('Your usual range is not available yet')
  })
})

describe('summarizeHealth and healthOptions', () => {
  it('a sustained change puts "share with the medical team" first; nothing is ordered', () => {
    const changed = evaluateIndicator(series([day(1, 58), day(2, 63), day(3, 64), day(4, 63)]), 4)
    const summary = summarizeHealth([changed])
    expect(summary.title).toBe('Different from your usual: resting heart rate')
    expect(summary.detail).toContain('not a diagnosis')
    const options = healthOptions({ evaluations: [changed], summary, checkedInToday: false, linkOffline: false })
    expect(options[0]).toMatchObject({ id: 'share', emphasised: true })
    expect(options.map((o) => o.id)).toEqual(['share', 'check_in', 'procedures'])
  })

  it('one or two days outside the usual range are not called a change', () => {
    const blip = evaluateIndicator(series([day(1, 58), day(2, 63), day(3, 64)]), 3)
    expect(blip.headline).toBe('Higher than your usual for 2 days')
    expect(summarizeHealth([blip]).changed).toHaveLength(0)
  })

  it('without changes, sharing stays available but optional, and an existing check-in is not asked again', () => {
    const ok = evaluateIndicator(series([day(1, 58)]), 1)
    const options = healthOptions({ evaluations: [ok], summary: summarizeHealth([ok]), checkedInToday: true, linkOffline: false })
    expect(options.map((o) => o.id)).toEqual(['procedures', 'share'])
    expect(options.every((o) => !o.emphasised)).toBe(true)
  })
})

describe('mock long-duration data', () => {
  it('Crew A (event scenario) shows a sustained change in resting HR and sleep; Crew B and C do not', async () => {
    const ds = new MockDataSource('session', 0)
    const today = missionDayOf((await ds.getMissionStatus()).now)
    expect(today).toBe(15)
    const evalA = (await ds.getDailyIndicators('crew-a')).map((s) => evaluateIndicator(s, today))
    const changedA = summarizeHealth(evalA).changed.map((e) => e.series.indicator)
    expect(changedA).toEqual(expect.arrayContaining(['resting_hr', 'sleep_duration']))
    const evalB = (await ds.getDailyIndicators('crew-b')).map((s) => evaluateIndicator(s, today))
    expect(summarizeHealth(evalB).changed).toHaveLength(0)
    const evalC = (await ds.getDailyIndicators('crew-c')).map((s) => evaluateIndicator(s, today))
    expect(summarizeHealth(evalC).changed).toHaveLength(0)
    // Without the injected condition Crew A stays within the usual range too.
    const nominalA = (await new MockDataSource('nominal', 0).getDailyIndicators('crew-a')).map((s) => evaluateIndicator(s, today))
    expect(summarizeHealth(nominalA).changed).toHaveLength(0)
  })

  it('check-ins: one per day, newest first, validated', async () => {
    const ds = new MockDataSource('session', 0)
    const before = await ds.listCheckIns('crew-a')
    expect(checkedInOn(before, '2026-11-14')).toBeUndefined()
    await ds.submitCheckIn('crew-a', { sleepQuality: 2, energy: 2, mood: 3, note: ' tired ' })
    await ds.submitCheckIn('crew-a', { sleepQuality: 3, energy: 2, mood: 3, note: '' })
    const after = await ds.listCheckIns('crew-a')
    expect(after).toHaveLength(before.length + 1)
    expect(after[0]).toMatchObject({ date: '2026-11-14', missionDay: 15, sleepQuality: 3 })
    await expect(ds.submitCheckIn('crew-a', { sleepQuality: 9 as never, energy: 2, mood: 3, note: '' })).rejects.toMatchObject({ code: 'bad_request' })
  })

  it('sharing creates a crew_report event for the Flight Surgeon, and fails with no link', async () => {
    const ds = new MockDataSource('session', 0)
    const ev = await ds.shareWithMedicalTeam('crew-a', 'Sleeping badly since day 12.')
    expect(ev).toMatchObject({ kind: 'crew_report', crewId: 'crew-a', status: 'open', parameter: null })
    expect(ev.trigger.description).toContain('Sleeping badly since day 12.')
    expect((await ds.listEvents({ crewId: 'crew-a' })).map((e) => e.id)).toContain(ev.id)
    await expect(new MockDataSource('offline', 0).shareWithMedicalTeam('crew-a', '')).rejects.toMatchObject({ code: 'unavailable' })
  })
})
