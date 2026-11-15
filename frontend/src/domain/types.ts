/**
 * Domain model shared by every view and by both data adapters.
 * Mirrors docs/FRONTEND_DATA_CONTRACT.md (a proposal to agree with the backend team).
 * Timestamps are ISO 8601 strings in UTC ("2026-11-14T10:15:20Z").
 */

export type ParameterId = 'heart_rate' | 'spo2' | 'resp_rate' | 'motion'

export type QualityFlag = 'good' | 'uncertain' | 'poor' | 'missing'

/** Why a sample was flagged. Produced by the acquisition/processing chain, never by the UI. */
export type QualityReason = 'motion' | 'contact' | 'not_received' | 'out_of_sensor_range'

export interface Sample {
  /** Acquisition time (device clock, UTC). */
  t: string
  /** null when no valid value exists (quality = "missing"). */
  value: number | null
  quality: QualityFlag
  reasons?: QualityReason[]
}

export interface DataSourceInfo {
  deviceId: string
  deviceLabel: string
  sensorType: string
  placement: string
  samplingIntervalS: number
  processing: string
  qualityMethod: string
  firmware: string
  /** true for every dataset produced by this prototype. */
  simulated: boolean
}

export interface TimeSeries {
  crewId: string
  parameter: ParameterId
  unit: string
  source: DataSourceInfo
  samples: Sample[]
  /** Last time the ground segment received data for this series. */
  receivedAt: string | null
}

export type LinkState = 'connected' | 'degraded' | 'offline'

export interface MissionStatus {
  simulated: true
  scenarioId: string
  scenarioLabel: string
  /** Reference "now" (simulated clock). The UI never uses the browser clock for data freshness. */
  now: string
  /** First day of the mission (YYYY-MM-DD, UTC) = mission day 1. */
  missionStartDate: string
  link: { state: LinkState; since: string; lastContactAt: string }
}

export type ActivityKind = 'rest' | 'warmup' | 'exercise' | 'recovery' | 'operational'

export interface ActivitySegment {
  start: string
  end: string
  kind: ActivityKind
  label: string
  protocolId: string | null
  /** true = scheduled in the mission timeline (not inferred from data). */
  scheduled: boolean
}

export interface CrewMember {
  id: string
  displayName: string
  /** Pseudonymised label; no real personal data. */
  note: string
}

export type DeviceState = 'streaming' | 'delayed' | 'not_reporting'

export interface ParameterSnapshot {
  parameter: ParameterId
  latest: Sample | null
  lastValidSample: Sample | null
}

export interface CrewSnapshot {
  crew: CrewMember
  activity: ActivitySegment | null
  device: { state: DeviceState; lastReceivedAt: string | null; expectedIntervalS: number }
  parameters: ParameterSnapshot[]
  openEvents: number
}

export interface HistoricalSession {
  id: string
  date: string
  protocolId: string
  /** Median of the parameter during the main phase of the protocol, good-quality samples only. */
  mainPhaseMedian: number
  goodQualityPct: number
}

export interface ReferencePoint {
  /** Seconds from the start of the protocol. */
  offsetS: number
  low: number
  median: number
  high: number
}

export interface ReferenceBand {
  crewId: string
  parameter: ParameterId
  protocolId: string
  /** Human-readable description of how the band was computed. */
  basis: string
  sessions: HistoricalSession[]
  points: ReferencePoint[]
}

/** `crew_report`: shared by the crew member from "My health" — raised by a person, not by a rule. */
export type EventKind = 'outside_personal_range' | 'signal_quality' | 'data_stale' | 'crew_report'
export type EventStatus = 'open' | 'in_review' | 'reviewed'

export interface Annotation {
  id: string
  authorRole: 'flight_surgeon'
  authorLabel: string
  createdAt: string
  text: string
}

export interface ReviewEvent {
  id: string
  crewId: string
  /** null when the event concerns the whole data feed (e.g. stale device). */
  parameter: ParameterId | null
  kind: EventKind
  detectedAt: string
  window: { start: string; end: string }
  status: EventStatus
  trigger: { ruleId: string; description: string; simulated: boolean }
  annotations: Annotation[]
}

export interface CrewMessage {
  id: string
  crewId: string
  createdAt: string
  templateId: string
  text: string
  from: string
  relatedEventId: string | null
}

/* ------------------------------------------------------------------ */
/* Long-duration mission: daily indicators and crew self-reports       */
/* ------------------------------------------------------------------ */

/** Indicators the crew member measures once a day (e.g. on waking). */
export type DailyIndicatorId =
  | 'resting_hr' | 'sleep_duration' | 'resting_spo2'
  | 'resting_resp_rate' | 'hrv_rmssd' | 'bp_systolic' | 'bp_diastolic'
  | 'body_temperature' | 'activity_minutes' | 'body_mass' | 'sleep_efficiency' | 'active_energy'

export interface DailyValue {
  /** Calendar day, UTC (YYYY-MM-DD). */
  date: string
  /** 1 = first day of the mission. */
  missionDay: number
  /** null when no valid value exists (quality = "missing"). */
  value: number | null
  quality: QualityFlag
}

/**
 * The crew member's own usual range for an indicator. Not a clinical
 * reference: a personal comparison point, computed from the first mission days.
 */
export interface PersonalBaseline {
  low: number
  median: number
  high: number
  fromDay: number
  toDay: number
  /** Human-readable description of how it was computed. */
  basis: string
}

export interface DailyIndicatorSeries {
  crewId: string
  indicator: DailyIndicatorId
  unit: string
  /** Ascending by missionDay. */
  days: DailyValue[]
  baseline: PersonalBaseline | null
  /** How the value is obtained (device / method), shown to the user. */
  source: string
  simulated: boolean
  /** Where the values come from: generated demo data, an imported file, or the backend. */
  origin?: 'demo' | 'import' | 'backend'
}

/** 1 (worst) … 5 (best) — higher is always better, on every question. */
export type CheckInScore = 1 | 2 | 3 | 4 | 5

export interface CheckInInput {
  sleepQuality: CheckInScore
  energy: CheckInScore
  mood: CheckInScore
  note: string
}

export interface CheckIn extends CheckInInput {
  id: string
  crewId: string
  date: string
  missionDay: number
  createdAt: string
}

/* ------------------------------------------------------------------ */
/* Sleep-aid schedule (crew coordination)                              */
/* ------------------------------------------------------------------ */

/**
 * A crew member plans to use a sleep aid on a given night. Only the plan is
 * recorded: no drug name and no dose (those belong to the medical record).
 * Purpose: make sure someone on board stays without a sleep aid every night,
 * ready for an emergency.
 */
export interface SleepAidPlanEntry {
  crewId: string
  /** The night that starts on this calendar day, UTC (YYYY-MM-DD). */
  night: string
  updatedAt: string
  simulated: boolean
}
