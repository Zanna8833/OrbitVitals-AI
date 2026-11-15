import { describe, expect, it } from 'vitest'
import { describeActivityProgress, describeNextStep, type NextStepInput } from './crewGuidance'
import type { CollectionStatus, SensorStatus } from './crewStatus'
import type { ActivitySegment, CrewMessage } from './types'

const collection = (level: CollectionStatus['level']): CollectionStatus => ({ level, headline: '', detail: '' })
const sensor = (deviceId: string, label: string, placement: string, signalDisturbed = false, level: SensorStatus['level'] = 'good'): SensorStatus => ({
  deviceId,
  deviceLabel: label,
  placement,
  parameters: [],
  level,
  text: '',
  earlierNote: null,
  signalDisturbed,
})
const message = (templateId: string, createdAt = '2026-11-14T10:38:00Z'): CrewMessage => ({
  id: templateId,
  crewId: 'crew-b',
  createdAt,
  templateId,
  text: '',
  from: 'Ground medical team',
  relatedEventId: null,
})
const base: NextStepInput = {
  messages: [],
  collection: collection('good'),
  sensors: [sensor('CHEST', 'Chest strap (simulated)', 'Chest'), sensor('PPG', 'Pulse oximeter (simulated)', 'Finger')],
  linkOffline: false,
}

describe('describeNextStep (crew view)', () => {
  it('by default asks for nothing and reassures about data collection', () => {
    const step = describeNextStep(base)
    expect(step).toMatchObject({ kind: 'none', title: 'Nothing to do — carry on with your activity', sensorsToCheck: [] })
    expect(step.detail).toBe('Your data is reaching the medical team.')
  })

  it('never turns a data problem into an instruction on its own', () => {
    const step = describeNextStep({ ...base, collection: collection('poor'), sensors: [sensor('PPG', 'Pulse oximeter', 'Finger', true, 'poor')] })
    expect(step.kind).toBe('none')
    expect(step.detail).toContain('The medical team can see this interruption')
  })

  it('shows an after-activity check only when the medical team asked, naming the disturbed sensor', () => {
    const sensors = [sensor('CHEST', 'Chest strap (simulated)', 'Chest'), sensor('PPG', 'Pulse oximeter (simulated)', 'Finger', true)]
    const step = describeNextStep({ ...base, sensors, messages: [message('check_sensor_after')] })
    expect(step.kind).toBe('after_activity')
    expect(step.title).toBe('After this activity: check the placement of your pulse oximeter (finger)')
    expect(step.detail).toContain('10:38 UTC')
    expect(step.detail).toContain('Nothing to do while the activity is in progress')
    expect(step.sensorsToCheck).toEqual(['PPG'])
  })

  it('names every sensor when none was flagged', () => {
    const step = describeNextStep({ ...base, messages: [message('check_sensor_after')] })
    expect(step.title).toBe('After this activity: check the placement of your chest strap (chest) and pulse oximeter (finger)')
  })

  it('only the latest message counts', () => {
    const step = describeNextStep({ ...base, messages: [message('ack_no_action', '2026-11-14T10:39:00Z'), message('check_sensor_after')] })
    expect(step.kind).toBe('none')
  })

  it('explains a lost link and a planned contact', () => {
    expect(describeNextStep({ ...base, linkOffline: true }).kind).toBe('link_paused')
    expect(describeNextStep({ ...base, messages: [message('contact_planned')] }).kind).toBe('await_contact')
  })
})

describe('describeActivityProgress', () => {
  const seg = (start: string, end: string, label: string): ActivitySegment => ({
    start: `2026-11-14T${start}:00Z`,
    end: `2026-11-14T${end}:00Z`,
    kind: 'exercise',
    label,
    protocolId: 'P',
    scheduled: true,
  })
  const plan = [seg('10:00', '10:05', 'Rest'), seg('10:05', '10:10', 'Warm-up'), seg('10:10', '10:30', 'Exercise'), seg('10:30', '10:40', 'Recovery')]

  it('marks done, current and upcoming phases and the time left', () => {
    const p = describeActivityProgress(plan, '2026-11-14T10:25:00Z')!
    expect(p.phases.map((x) => x.state)).toEqual(['done', 'done', 'current', 'upcoming'])
    expect(p.current?.label).toBe('Exercise')
    expect(p.next?.label).toBe('Recovery')
    expect(p.remainingMs).toBe(5 * 60 * 1000)
    expect(p.nowShare).toBeCloseTo(25 / 40)
    expect(p.phases.reduce((sum, x) => sum + x.share, 0)).toBeCloseTo(1)
  })

  it('has no current phase after the plan ends, and null for an empty plan', () => {
    const p = describeActivityProgress(plan, '2026-11-14T10:45:00Z')!
    expect(p.current).toBeNull()
    expect(p.remainingMs).toBeNull()
    expect(p.nowShare).toBe(1)
    expect(describeActivityProgress([], '2026-11-14T10:45:00Z')).toBeNull()
  })
})
