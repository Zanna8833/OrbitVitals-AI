import { config } from '../config'
import { MISSION_CONFIG } from '../mission.config'
/**
 * Mission phases and activities. The real plan comes from mission control
 * (src/mission.config.ts); a sample plan is used only with offline sample data.
 */
export interface MissionPhase {
  id: string
  label: string
  fromDay: number
  toDay: number
}

const SAMPLE_PLAN: { lengthDays: number | null; phases: MissionPhase[] } = {
  lengthDays: 180,
  phases: [
    { id: 'launch', label: 'Launch & docking', fromDay: 1, toDay: 2 },
    { id: 'adaptation', label: 'Adaptation', fromDay: 3, toDay: 14 },
    { id: 'operations', label: 'Science operations', fromDay: 15, toDay: 150 },
    { id: 'return', label: 'Return preparation', fromDay: 151, toDay: 180 },
  ],
}

/** Sample plan only with the offline sample data (development); otherwise the mission's own plan (mission.config.ts). */
export const MISSION_PLAN = config.dataSource === 'mock' ? SAMPLE_PLAN : { lengthDays: MISSION_CONFIG.lengthDays, phases: MISSION_CONFIG.phases }

export function phaseOf(day: number): MissionPhase | null {
  const phases = MISSION_PLAN.phases
  if (!phases.length) return null
  return phases.find((p) => day >= p.fromDay && day <= p.toDay) ?? phases[phases.length - 1]
}

/**
 * Simulated activities that matter when planning a night: the activity is on
 * the morning AFTER the night shown. Mission control would provide the real
 * timeline; nothing here is a medical rule.
 */
export interface MissionActivity {
  day: number
  label: string
  short: string
  /** UTC start time of the activity. */
  startUtc: string
  /** Crew ids taking part; empty = the whole crew. */
  crew: string[]
}

const SAMPLE_ACTIVITIES: MissionActivity[] = [
  { day: 17, label: 'Spacewalk', short: 'EVA', startUtc: '06:00', crew: ['crew-a', 'crew-b'] },
  { day: 20, label: 'Cargo vehicle docking', short: 'Dock', startUtc: '04:40', crew: [] },
  { day: 23, label: 'Periodic medical checks', short: 'Med', startUtc: '08:30', crew: [] },
  { day: 25, label: 'Spacewalk', short: 'EVA', startUtc: '05:30', crew: ['crew-b', 'crew-c'] },
]

export const MISSION_ACTIVITIES: MissionActivity[] = config.dataSource === 'mock' ? SAMPLE_ACTIVITIES : MISSION_CONFIG.activities

const DAY_MS = 86_400_000

/** The activity on the day after `night` (YYYY-MM-DD), if any. */
export function activityAfterNight(night: string, missionStartDate: string): MissionActivity | null {
  const nextDay = Math.round((Date.parse(`${night}T00:00:00Z`) + DAY_MS - Date.parse(`${missionStartDate}T00:00:00Z`)) / DAY_MS) + 1
  return MISSION_ACTIVITIES.find((a) => a.day === nextDay) ?? null
}

export const involves = (a: MissionActivity, crewId: string) => a.crew.length === 0 || a.crew.includes(crewId)
