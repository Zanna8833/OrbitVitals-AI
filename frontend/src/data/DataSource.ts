import type {
  ActivitySegment,
  CheckIn,
  CheckInInput,
  CrewMember,
  CrewMessage,
  CrewSnapshot,
  DailyIndicatorSeries,
  EventStatus,
  MissionStatus,
  ParameterId,
  ReferenceBand,
  ReviewEvent,
  SleepAidPlanEntry,
  TimeSeries,
} from '../domain/types'

/**
 * Single seam between the UI and the data. Views only talk to this interface,
 * so the mock implementation can be replaced by the HTTP one (see
 * docs/API_CONTRACT.md) without touching components.
 */
export interface DataSource {
  readonly kind: 'mock' | 'http'
  getMissionStatus(): Promise<MissionStatus>
  listCrew(): Promise<CrewMember[]>
  getCrewSnapshot(crewId: string): Promise<CrewSnapshot>
  getSeries(crewId: string, parameters: ParameterId[], from: string, to: string): Promise<TimeSeries[]>
  getActivities(crewId: string, from: string, to: string): Promise<ActivitySegment[]>
  getReferenceBand(crewId: string, parameter: ParameterId, protocolId: string): Promise<ReferenceBand | null>
  listEvents(filter?: { crewId?: string; status?: EventStatus[] }): Promise<ReviewEvent[]>
  getEvent(eventId: string): Promise<ReviewEvent>
  updateEventStatus(eventId: string, status: EventStatus): Promise<ReviewEvent>
  addAnnotation(eventId: string, text: string): Promise<ReviewEvent>
  listCrewMessages(crewId: string): Promise<CrewMessage[]>
  sendCrewMessage(crewId: string, templateId: string, relatedEventId: string | null): Promise<CrewMessage>

  /* Long-duration mission: the crew member's own evaluation ("My health"). */
  getDailyIndicators(crewId: string): Promise<DailyIndicatorSeries[]>
  /** Newest first. */
  listCheckIns(crewId: string): Promise<CheckIn[]>
  /** One per day: a second submission on the same day replaces the first. */
  submitCheckIn(crewId: string, input: CheckInInput): Promise<CheckIn>
  /** The crew member shares their trends with the medical team; creates a `crew_report` event. */
  shareWithMedicalTeam(crewId: string, note: string): Promise<ReviewEvent>

  /* Sleep-aid schedule: who plans to use one, on which night. */
  /** Planned nights for the whole crew, `from`/`to` inclusive (YYYY-MM-DD). */
  listSleepAidPlan(from: string, to: string): Promise<SleepAidPlanEntry[]>
  /** Add (planned = true) or remove a crew member's planned night. */
  setSleepAidPlan(crewId: string, night: string, planned: boolean): Promise<SleepAidPlanEntry[]>
}

/** Errors surfaced to the UI, aligned with the error codes in the API contract. */
export class DataSourceError extends Error {
  readonly code: 'not_found' | 'unavailable' | 'bad_request' | 'unauthorized' | 'internal'
  readonly status?: number
  constructor(code: DataSourceError['code'], message: string, status?: number) {
    super(message)
    this.code = code
    this.status = status
  }
}

/**
 * Pre-approved, non-clinical messages the Flight Surgeon can send to the crew.
 * Free text is intentionally not offered in the MVP (to be discussed with experts).
 */
export const CREW_MESSAGE_TEMPLATES: { id: string; text: string }[] = [
  { id: 'ack_no_action', text: 'Data received by the medical team. No action needed.' },
  { id: 'review_after', text: 'The medical team will review the data after the session.' },
  { id: 'check_sensor_after', text: 'After the activity, please check the placement of the sensor shown in your view.' },
  { id: 'contact_planned', text: 'The medical team will contact you in the next scheduled communication window.' },
]
