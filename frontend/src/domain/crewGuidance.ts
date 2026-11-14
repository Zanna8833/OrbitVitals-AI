import type { ActivitySegment, CrewMessage } from './types'
import type { CollectionStatus, SensorStatus } from './crewStatus'
import { formatClock, toMs } from './time'

/**
 * "What do I need to do?" for the CREW view.
 *
 * Boundaries (see docs/UX_ANALYSIS.md):
 * - an action is only ever shown because a PERSON on the medical team asked
 *   for it (a predefined message) — never inferred automatically from data;
 * - actions are never requested during the activity: at most "after it";
 * - no clinical content.
 */

export type NextStepKind = 'none' | 'after_activity' | 'await_contact' | 'link_paused'

export interface NextStep {
  kind: NextStepKind
  title: string
  detail: string
  /** Sensors the crew member is asked to check (device ids), when relevant. */
  sensorsToCheck: string[]
}

export interface NextStepInput {
  /** Newest first, as returned by the data source. */
  messages: CrewMessage[]
  collection: CollectionStatus
  sensors: SensorStatus[]
  linkOffline: boolean
}

export function describeNextStep({ messages, collection, sensors, linkOffline }: NextStepInput): NextStep {
  const latest = messages[0]

  if (latest?.templateId === 'check_sensor_after') {
    // The template refers to "the sensor shown in your view": point at the ones whose
    // signal was disturbed (a mere reception gap is not a placement problem).
    const flagged = sensors.filter((s) => s.signalDisturbed)
    const targets = flagged.length ? flagged : sensors
    const names = targets.map((s) => `${s.deviceLabel.replace(/\s*\(simulated\)$/, '').toLowerCase()} (${s.placement.toLowerCase()})`)
    return {
      kind: 'after_activity',
      title: `After this activity: check the placement of your ${joinNames(names)}`,
      detail: `Requested by the medical team at ${formatClock(latest.createdAt, false)} UTC. Nothing to do while the activity is in progress.`,
      sensorsToCheck: targets.map((s) => s.deviceId),
    }
  }

  if (linkOffline) {
    return {
      kind: 'link_paused',
      title: 'Nothing to do — carry on with your activity',
      detail: 'The link with the ground is down. Messages from the medical team will arrive when it is back.',
      sensorsToCheck: [],
    }
  }

  if (latest?.templateId === 'contact_planned') {
    return {
      kind: 'await_contact',
      title: 'Nothing to do — carry on with your activity',
      detail: 'The medical team will contact you in the next scheduled communication window.',
      sensorsToCheck: [],
    }
  }

  return {
    kind: 'none',
    title: 'Nothing to do — carry on with your activity',
    detail: COLLECTION_REASSURANCE[collection.level],
    sensorsToCheck: [],
  }
}

const COLLECTION_REASSURANCE: Record<CollectionStatus['level'], string> = {
  good: 'Your data is reaching the medical team.',
  uncertain: 'Your data is arriving with a delay. The medical team can see this.',
  poor: 'Your device is not sending data right now. The medical team can see this interruption.',
  missing: 'No data has been received yet. The medical team can see this.',
}

function joinNames(names: string[]): string {
  if (names.length <= 1) return names[0] ?? 'sensors'
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
}

/* ------------------------------------------------------------------ */

export type PhaseState = 'done' | 'current' | 'upcoming'

export interface PhaseProgress {
  segment: ActivitySegment
  state: PhaseState
  /** Share (0–1) of the whole scheduled session taken by this phase. */
  share: number
}

export interface ActivityProgress {
  phases: PhaseProgress[]
  current: ActivitySegment | null
  next: ActivitySegment | null
  /** Milliseconds left in the current phase; null when no phase is in progress. */
  remainingMs: number | null
  /** Position of "now" within the whole session, 0–1. */
  nowShare: number
}

/** Where the crew member is in the scheduled activity plan. Pure; times from the server clock. */
export function describeActivityProgress(activities: ActivitySegment[], nowIso: string): ActivityProgress | null {
  if (!activities.length) return null
  const now = toMs(nowIso)
  const start = toMs(activities[0].start)
  const end = toMs(activities[activities.length - 1].end)
  const total = Math.max(1, end - start)
  const phases = activities.map((segment) => {
    const a = toMs(segment.start)
    const b = toMs(segment.end)
    const state: PhaseState = now >= b ? 'done' : now >= a ? 'current' : 'upcoming'
    return { segment, state, share: (b - a) / total }
  })
  const currentIdx = phases.findIndex((p) => p.state === 'current')
  const current = currentIdx >= 0 ? phases[currentIdx].segment : null
  const next = phases.find((p) => p.state === 'upcoming')?.segment ?? null
  return {
    phases,
    current,
    next,
    remainingMs: current ? toMs(current.end) - now : null,
    nowShare: Math.min(1, Math.max(0, (now - start) / total)),
  }
}
