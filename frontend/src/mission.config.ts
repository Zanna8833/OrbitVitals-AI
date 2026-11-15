import type { MissionActivity, MissionPhase } from './domain/missionPlan'

/**
 * The mission's own plan, provided by mission control. The backend has no
 * mission timeline yet, so it lives here: fill it in to show the mission
 * phases in the header and the activities of the next morning in the
 * sleep plan. Empty = the interface shows only the mission day.
 */
export const MISSION_CONFIG: {
  /** Planned length in days, or null if not set. */
  lengthDays: number | null
  phases: MissionPhase[]
  /** Activities that matter when planning a night (spacewalks, dockings…), by mission day. */
  activities: MissionActivity[]
} = {
  lengthDays: null,
  phases: [],
  activities: [],
}
