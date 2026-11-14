import type { DailyIndicatorId, ReviewEvent } from '../domain/types'
import type { DeviceMeasurement } from '../domain/measurements'

/**
 * Offline-only DEMO persistence. This is NOT secure storage and MUST NOT be used
 * with real health information. All entries in the prototype are synthetic.
 */
const prefix = 'orbitvitals-demo-v2:'
const memoryFallback = new Map<string, string>()

export function localPersistenceAvailable(): boolean {
  try {
    const key = prefix + 'storage-check'
    window.localStorage.setItem(key, '1')
    window.localStorage.removeItem(key)
    return true
  } catch { return false }
}

export interface QueuedShare {
  id: string
  crewId: string
  note: string
  queuedAt: string
}

export interface Recheck {
  id: string
  crewId: string
  indicator: DailyIndicatorId
  createdAt: string
  completedAt: string | null
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(prefix + key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    try {
      const item = memoryFallback.get(prefix + key)
      return item ? JSON.parse(item) as T : fallback
    } catch { return fallback }
  }
}

function write<T>(key: string, value: T) {
  try {
    window.localStorage.setItem(prefix + key, JSON.stringify(value))
  } catch {
    // When storage is blocked, keep the demo working only for this open page.
    memoryFallback.set(prefix + key, JSON.stringify(value))
  }
}

function makeId() {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export function queuedShares(): QueuedShare[] {
  const entries = read<QueuedShare[]>('outbox', [])
  return Array.isArray(entries) ? entries : []
}

export function enqueueShare(crewId: string, note: string, queuedAt: string): QueuedShare {
  const item = { id: makeId(), crewId, note: note.trim().slice(0, 500), queuedAt }
  write('outbox', [...queuedShares(), item])
  return item
}

export function removeQueuedShare(id: string) {
  write('outbox', queuedShares().filter((e) => e.id !== id))
}

export function rechecksFor(crewId: string): Recheck[] {
  const items = read<Recheck[]>('rechecks', [])
  return Array.isArray(items) ? items.filter((e) => e.crewId === crewId) : []
}

export function scheduleRecheck(crewId: string, indicator: DailyIndicatorId, createdAt: string): Recheck {
  const item: Recheck = { id: makeId(), crewId, indicator, createdAt, completedAt: null }
  const existing = read<Recheck[]>('rechecks', [])
  write('rechecks', [...(Array.isArray(existing) ? existing : []), item])
  return item
}

export function completeRecheck(id: string, completedAt: string) {
  const existing = read<Recheck[]>('rechecks', [])
  if (!Array.isArray(existing)) return
  write('rechecks', existing.map((r) => (r.id === id ? { ...r, completedAt } : r)))
}

/** Simulated medical-team inbox survives reloads and scenario changes on this browser only. */
export function storedCrewReports(): ReviewEvent[] {
  const items = read<ReviewEvent[]>('crew-reports', [])
  return Array.isArray(items) ? items : []
}

export function storeCrewReport(event: ReviewEvent) {
  const without = storedCrewReports().filter((x) => x.id !== event.id)
  write('crew-reports', [...without, event])
}

export function resetCrewDemoData() {
  for (const key of ['outbox', 'rechecks', 'crew-reports', 'check-ins', 'device-measurements', 'sleep-aid-plan']) {
    try { window.localStorage.removeItem(prefix + key) } catch { /* unavailable */ }
    memoryFallback.delete(prefix + key)
  }
}

export function storedCheckIns(): Record<string, import('../domain/types').CheckIn[]> {
  return read('check-ins', {})
}

export function storeCheckIns(crewId: string, list: import('../domain/types').CheckIn[]) {
  const all = storedCheckIns()
  write('check-ins', { ...all, [crewId]: list })
}

/** Device readings captured by the mock simulation; never a real hardware feed. */
export function measurementsFor(crewId: string): DeviceMeasurement[] {
  const entries = read<DeviceMeasurement[]>('device-measurements', [])
  return Array.isArray(entries) ? entries.filter((item) => item.crewId === crewId).sort((a, b) => b.savedAtMs - a.savedAtMs) : []
}

export function storeMeasurement(capture: DeviceMeasurement) {
  const entries = read<DeviceMeasurement[]>('device-measurements', [])
  write('device-measurements', [...(Array.isArray(entries) ? entries : []), capture])
}

/** Demo-only sleep-aid schedule edits. `null` = nothing saved yet (use the seeded plan). */
export function storedSleepAidPlan(): import('../domain/types').SleepAidPlanEntry[] | null {
  const v = read<import('../domain/types').SleepAidPlanEntry[] | null>('sleep-aid-plan', null)
  return Array.isArray(v) ? v : null
}

export function storeSleepAidPlan(entries: import('../domain/types').SleepAidPlanEntry[]) {
  write('sleep-aid-plan', entries)
}
