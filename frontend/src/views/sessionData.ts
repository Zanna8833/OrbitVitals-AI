import type { DataSource } from '../data'
import type { ActivitySegment, MissionStatus, ParameterId, ReferenceBand, TimeSeries } from '../domain/types'
import { toIso, toMs } from '../domain/time'

export interface SessionData {
  mission: MissionStatus
  activities: ActivitySegment[]
  sessionStart: string
  domain: [number, number]
  series: Partial<Record<ParameterId, TimeSeries>>
  bands: Partial<Record<ParameterId, ReferenceBand | null>>
}

/** Loads everything needed to plot one crew member's current session. */
export async function loadSession(ds: DataSource, crewId: string, parameters: ParameterId[]): Promise<SessionData> {
  const mission = await ds.getMissionStatus()
  const nowMs = toMs(mission.now)
  const lookback = toIso(nowMs - 60 * 60 * 1000)
  const activities = await ds.getActivities(crewId, lookback, mission.now)
  const sessionStart = activities.length ? activities[0].start : lookback
  const protocolId = activities.find((a) => a.protocolId)?.protocolId ?? null
  const [seriesList, bandList] = await Promise.all([
    ds.getSeries(crewId, parameters, sessionStart, mission.now),
    protocolId ? Promise.all(parameters.map((p) => ds.getReferenceBand(crewId, p, protocolId))) : Promise.resolve(parameters.map(() => null)),
  ])
  const series: SessionData['series'] = {}
  for (const s of seriesList) series[s.parameter] = s
  const bands: SessionData['bands'] = {}
  parameters.forEach((p, i) => (bands[p] = bandList[i]))
  return { mission, activities, sessionStart, domain: [toMs(sessionStart), nowMs], series, bands }
}
