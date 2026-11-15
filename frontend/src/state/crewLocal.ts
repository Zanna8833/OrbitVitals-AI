import type { DailyIndicatorId, ReviewEvent } from '../domain/types'
import type { DeviceMeasurement } from '../domain/measurements'

/**
 * Offline-only DEMO persistence. This is NOT secure storage and MUST NOT be used
 * with real health information. All entries in the prototype are synthetic.
 */
// Separate stores: sample data (development) never mixes with what users enter on the platform.
// Separate stores: demo-mode sample data never mixes with what users enter on the platform.
const prefix = () => (demoModeOn() ? 'orbitvitals-demo-v2:' : 'orbitvitals:')
import { demoModeOn } from './demoMode'
const memoryFallback = new Map<string, string>()

export function localPersistenceAvailable(): boolean {
  try {
    const key = prefix() + 'storage-check'
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
    const raw = window.localStorage.getItem(prefix() + key)
    return raw ? (JSON.parse(raw) as T) : fallback
  } catch {
    try {
      const item = memoryFallback.get(prefix() + key)
      return item ? JSON.parse(item) as T : fallback
    } catch { return fallback }
  }
}

function write<T>(key: string, value: T) {
  try {
    window.localStorage.setItem(prefix() + key, JSON.stringify(value))
  } catch {
    // When storage is blocked, keep the demo working only for this open page.
    memoryFallback.set(prefix() + key, JSON.stringify(value))
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
  for (const key of ['outbox', 'rechecks', 'crew-reports', 'check-ins', 'device-measurements', 'sleep-aid-plan', 'imports', 'intake', 'custom-foods', 'profiles']) {
    try { window.localStorage.removeItem(prefix() + key) } catch { /* unavailable */ }
    memoryFallback.delete(prefix() + key)
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

/** Crew data imported from the team's files (profile JSON + measurements CSV). Demo storage only. */
export interface ImportedCrewData {
  crewId: string
  displayName: string | null
  role: string | null
  series: import('../domain/types').DailyIndicatorSeries[]
  /** Sex, age, height from the profile JSON, when given (nutrition requirements). */
  nutrition?: Partial<Omit<import('../domain/nutrition').NutritionProfile, 'bodyMassKg' | 'source'>>
  files: string[]
  importedAt: string
}

export function storedImports(): Record<string, ImportedCrewData> {
  const v = read<Record<string, ImportedCrewData>>('imports', {})
  return v && typeof v === 'object' ? v : {}
}

export function storeImport(data: ImportedCrewData) {
  write('imports', { ...storedImports(), [data.crewId]: data })
}

export function removeImport(crewId: string) {
  const all = storedImports()
  delete all[crewId]
  write('imports', all)
}

/** Demo-only nutrition log. `null` = nothing saved yet (use the seeded log). */
export function storedIntake(): import('../domain/nutrition').IntakeEntry[] | null {
  const v = read<import('../domain/nutrition').IntakeEntry[] | null>('intake', null)
  return Array.isArray(v) ? v : null
}

export function storeIntake(entries: import('../domain/nutrition').IntakeEntry[]) {
  write('intake', entries)
}

/** Foods created by the crew, shared by everyone on board in this demo. */
export function storedCustomFoods(): import('../domain/nutrition').Food[] {
  const v = read<import('../domain/nutrition').Food[]>('custom-foods', [])
  return Array.isArray(v) ? v : []
}

export function storeCustomFoods(foods: import('../domain/nutrition').Food[]) {
  write('custom-foods', foods)
}

/** Body profile for the nutrition requirements, entered by the crew or imported from the profile JSON. */
export type StoredProfile = Omit<import('../domain/nutrition').NutritionProfile, 'bodyMassKg' | 'source'> & { bodyMassKg?: number }

export function storedProfiles(): Record<string, StoredProfile> {
  const v = read<Record<string, StoredProfile>>('profiles', {})
  return v && typeof v === 'object' ? v : {}
}

export function storeProfile(crewId: string, profile: StoredProfile) {
  write('profiles', { ...storedProfiles(), [crewId]: profile })
}
