/**
 * Mission phases for the timeline in the header. SIMULATED demo plan: a real
 * mission plan would come from mission control (see API_CONTRACT addendum).
 */
export interface MissionPhase {
  id: string
  label: string
  fromDay: number
  toDay: number
}

export const MISSION_PLAN: { lengthDays: number; phases: MissionPhase[]; simulated: true } = {
  lengthDays: 180,
  simulated: true,
  phases: [
    { id: 'launch', label: 'Launch & docking', fromDay: 1, toDay: 2 },
    { id: 'adaptation', label: 'Adaptation', fromDay: 3, toDay: 14 },
    { id: 'operations', label: 'Science operations', fromDay: 15, toDay: 150 },
    { id: 'return', label: 'Return preparation', fromDay: 151, toDay: 180 },
  ],
}

export function phaseOf(day: number): MissionPhase {
  return MISSION_PLAN.phases.find((p) => day >= p.fromDay && day <= p.toDay) ?? MISSION_PLAN.phases[MISSION_PLAN.phases.length - 1]
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

export const MISSION_ACTIVITIES: MissionActivity[] = [
  { day: 17, label: 'Spacewalk', short: 'EVA', startUtc: '06:00', crew: ['crew-a', 'crew-b'] },
  { day: 20, label: 'Cargo vehicle docking', short: 'Dock', startUtc: '04:40', crew: [] },
  { day: 23, label: 'Periodic medical checks', short: 'Med', startUtc: '08:30', crew: [] },
  { day: 25, label: 'Spacewalk', short: 'EVA', startUtc: '05:30', crew: ['crew-b', 'crew-c'] },
]

const DAY_MS = 86_400_000

/** The activity on the day after `night` (YYYY-MM-DD), if any. */
export function activityAfterNight(night: string, missionStartDate: string): MissionActivity | null {
  const nextDay = Math.round((Date.parse(`${night}T00:00:00Z`) + DAY_MS - Date.parse(`${missionStartDate}T00:00:00Z`)) / DAY_MS) + 1
  return MISSION_ACTIVITIES.find((a) => a.day === nextDay) ?? null
}

export const involves = (a: MissionActivity, crewId: string) => a.crew.length === 0 || a.crew.includes(crewId)
