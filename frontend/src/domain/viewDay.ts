import type { DailyIndicatorSeries, MissionStatus } from './types'
import { missionDayOf } from './time'

/**
 * Looking back at a past mission day: everything is read as it was at the end
 * of that day, from data already stored. Days after the selected one are cut,
 * never extrapolated; future days cannot be selected.
 */
export function viewMission(mission: MissionStatus, viewDay: number | null): { mission: MissionStatus; actualDay: number; day: number; past: boolean } {
  const actualDay = missionDayOf(mission.now, mission.missionStartDate)
  if (viewDay === null || viewDay >= actualDay) return { mission, actualDay, day: actualDay, past: false }
  const day = Math.max(1, viewDay)
  const date = new Date(Date.parse(`${mission.missionStartDate}T00:00:00Z`) + (day - 1) * 86_400_000).toISOString().slice(0, 10)
  return { mission: { ...mission, now: `${date}T20:00:00Z` }, actualDay, day, past: true }
}

export function sliceToDay(daily: DailyIndicatorSeries[], day: number): DailyIndicatorSeries[] {
  return daily.map((s) => ({ ...s, days: s.days.filter((d) => d.missionDay <= day) }))
}
