/**
 * Demo scenarios. Each one switches on a set of injected conditions on top of
 * the same deterministic baseline session. Nothing here is real data.
 */
export interface ScenarioFlags {
  /** Crew A: heart rate above the personal historical range, with good signal quality. */
  reviewEvent: boolean
  /** Crew B: SpO₂ samples with uncertain/poor quality during exercise + a respiratory-rate gap. */
  uncertainQuality: boolean
  /** Crew C: device stops reporting at 10:22 UTC. */
  staleData: boolean
  /** Ground link lost at 10:34 UTC for everyone. */
  linkOffline: boolean
}

export interface Scenario {
  id: string
  label: string
  description: string
  flags: ScenarioFlags
}

const none: ScenarioFlags = { reviewEvent: false, uncertainQuality: false, staleData: false, linkOffline: false }

export const SCENARIOS: Scenario[] = [
  {
    id: 'session',
    label: 'Full session',
    description: 'Combines an event to review (Crew A), uncertain quality (Crew B) and data not updated (Crew C).',
    flags: { reviewEvent: true, uncertainQuality: true, staleData: true, linkOffline: false },
  },
  {
    id: 'mission-offline',
    label: 'Long mission · Changed trend + no ground link',
    description: 'Crew A has a sustained personal trend change while ground contact is unavailable. Queue a report, then switch to Full session to reconnect.',
    flags: { reviewEvent: true, uncertainQuality: false, staleData: false, linkOffline: true },
  },
  {
    id: 'nominal',
    label: '1 · Data available and consistent',
    description: 'All measurements arrive with good quality; no events.',
    flags: none,
  },
  {
    id: 'quality',
    label: '2 · Uncertain quality',
    description: 'Crew B: uncertain SpO₂ samples during exercise, with high motion, and a gap in respiratory rate.',
    flags: { ...none, uncertainQuality: true },
  },
  {
    id: 'stale',
    label: '3 · Data not updated',
    description: 'Crew C: the device has not sent data since 10:22 UTC.',
    flags: { ...none, staleData: true },
  },
  {
    id: 'offline',
    label: '4 · No connection',
    description: 'Ground link lost since 10:34 UTC: only the last data received is shown.',
    flags: { ...none, linkOffline: true },
  },
  {
    id: 'review',
    label: '5 · Event to review',
    description: 'Crew A: heart rate above the personal historical range during exercise, with good signal quality.',
    flags: { ...none, reviewEvent: true },
  },
]

export const DEFAULT_SCENARIO_ID = 'session'

export function getScenario(id: string): Scenario {
  return SCENARIOS.find((s) => s.id === id) ?? SCENARIOS[0]
}
