import type { DataSource } from '../DataSource'
import { CREW_MESSAGE_TEMPLATES, DataSourceError } from '../DataSource'
import type {
  ActivitySegment,
  CheckIn,
  CheckInInput,
  CrewMember,
  CrewMessage,
  CrewSnapshot,
  DailyIndicatorSeries,
  DeviceState,
  EventStatus,
  MissionStatus,
  ParameterId,
  ReferenceBand,
  ReviewEvent,
  SleepAidPlanEntry,
  TimeSeries,
} from '../../domain/types'
import { PARAMETER_ORDER, PARAMETERS } from '../../domain/parameters'
import { computeFreshness } from '../../domain/freshness'
import { toIso, toMs } from '../../domain/time'
import {
  CREW_PROFILES,
  LINK_LOSS_OFFSET_S,
  SAMPLE_INTERVAL_S,
  SESSION_START,
  STALE_OFFSET_S,
  activitiesFor,
  buildReferenceBand,
  generateSamples,
  getProfile,
  receivedUntilOffset,
  sourceFor,
} from './generator'
import { getScenario, type Scenario } from './scenarios'
import { fixedClock, type SimClock } from './clock'
import { MISSION_START_DATE, generateDailyIndicators, missionDayOf, seedCheckIns } from './daily'
import { withDemoMeasurements, type DeviceMeasurement } from '../../domain/measurements'
import { storeCheckIns, storedCheckIns, storeCrewReport, storedCrewReports, measurementsFor, storeMeasurement, storeSleepAidPlan, storedSleepAidPlan, storedImports, storedIntake, storeIntake, storedCustomFoods, storeCustomFoods, storedProfiles, storeProfile, storeImport } from '../../state/crewLocal'
import { ISS_FOODS, type Food, type IntakeEntry, type NutritionProfile } from '../../domain/nutrition'
import { NUTRITION_PROFILES, seedIntake } from './nutrition'
import type { BackendEvaluation } from '../../domain/metricCatalog'

const PSEUDONYM_NOTE = 'Pseudonymised identity'

const at = (offsetS: number) => toIso(toMs(SESSION_START) + offsetS * 1000)

function initialEvents(s: Scenario): ReviewEvent[] {
  const events: ReviewEvent[] = []
  if (s.flags.reviewEvent) {
    events.push({
      id: 'EV-0142',
      crewId: 'crew-a',
      parameter: 'heart_rate',
      kind: 'outside_personal_range',
      detectedAt: at(930),
      window: { start: at(840), end: at(1210) },
      status: 'open',
      trigger: {
        ruleId: 'DEMO-PR-01',
        description:
          'Rule: 60 s median of good-quality samples above the upper limit (P90) of the personal historical range for the same protocol. This is not a clinical threshold.',
        simulated: true,
      },
      annotations: [],
    })
  }
  if (s.flags.uncertainQuality) {
    events.push({
      id: 'EV-0143',
      crewId: 'crew-b',
      parameter: 'spo2',
      kind: 'signal_quality',
      detectedAt: at(1150),
      window: { start: at(1080), end: at(1380) },
      status: 'open',
      trigger: {
        ruleId: 'DEMO-SQ-01',
        description:
          'Rule: more than 60 consecutive seconds of uncertain, poor or missing samples on the same parameter.',
        simulated: true,
      },
      annotations: [],
    })
  }
  if (s.flags.staleData) {
    events.push({
      id: 'EV-0144',
      crewId: 'crew-c',
      parameter: null,
      kind: 'data_stale',
      detectedAt: at(STALE_OFFSET_S + 300),
      // The end follows the simulated clock while the device stays silent (see liveView).
      window: { start: at(STALE_OFFSET_S), end: at(STALE_OFFSET_S) },
      status: 'open',
      trigger: {
        ruleId: 'DEMO-ST-01',
        description: 'Rule: no sample received from the device for more than 5 minutes.',
        simulated: true,
      },
      annotations: [],
    })
  }
  return events
}

/**
 * In-memory implementation of DataSource built on deterministic synthetic data.
 * Mutations (status, notes, messages) live only for the browser session.
 */
export class MockDataSource implements DataSource {
  readonly kind: 'mock' | 'http' = 'mock'
  readonly scenario: Scenario
  private events: ReviewEvent[]
  private messages: CrewMessage[] = []
  /** Self-reports submitted in this session, per crew member (seeded ones come from daily.ts). */
  private checkIns = new Map<string, CheckIn[]>()
  private seq = 0
  private latencyMs: number
  private clock: SimClock

  /** `clock` is the simulated server clock: fixed at 10:40 UTC by default, or a live replay. */
  /** false: no generated sample content (events, check-ins, sleep plan, food log); only what users enter. */
  protected readonly samples: boolean

  constructor(scenarioId: string, latencyMs = 60, clock: SimClock = fixedClock, samples = true) {
    this.scenario = getScenario(scenarioId)
    this.samples = samples
    this.events = [...(samples ? initialEvents(this.scenario) : []), ...storedCrewReports()]
    this.latencyMs = latencyMs
    this.clock = clock
  }

  protected delay<T>(value: T): Promise<T> {
    // structuredClone: callers must never mutate the store by reference.
    const copy = structuredClone(value)
    if (this.latencyMs <= 0) return Promise.resolve(copy)
    return new Promise((resolve) => setTimeout(() => resolve(copy), this.latencyMs))
  }

  protected requireCrew(crewId: string) {
    const p = getProfile(crewId)
    if (!p) throw new DataSourceError('not_found', `Crew member "${crewId}" not found`, 404)
    return p
  }

  private nextId(prefix: string) {
    this.seq++
    return `${prefix}-${String(this.seq).padStart(4, '0')}`
  }

  /** Simulated "now". Mutations are timestamped with it, never with the browser clock. */
  protected simNow() {
    return this.clock()
  }

  private linkLostAt(nowIso: string): string | null {
    const lossAt = at(LINK_LOSS_OFFSET_S)
    return this.scenario.flags.linkOffline && toMs(nowIso) >= toMs(lossAt) ? lossAt : null
  }

  /** An event exists only once the simulated clock has passed its detection time. */
  private isDetected(e: ReviewEvent, nowIso: string): boolean {
    return toMs(e.detectedAt) <= toMs(nowIso)
  }

  /** How an event reads at `nowIso`: a stale-data window stays open up to now. */
  private present(e: ReviewEvent, nowIso: string): ReviewEvent {
    return e.kind === 'data_stale' ? { ...e, window: { ...e.window, end: nowIso } } : e
  }

  private visibleEvents(): ReviewEvent[] {
    const now = this.simNow()
    return this.events.filter((e) => this.isDetected(e, now)).map((e) => this.present(e, now))
  }

  /** The stored (mutable) event, if it is visible at the simulated now. */
  private findEvent(eventId: string): ReviewEvent {
    const e = this.events.find((x) => x.id === eventId)
    if (!e || !this.isDetected(e, this.simNow())) throw new DataSourceError('not_found', `Event "${eventId}" not found in this scenario`, 404)
    return e
  }

  async getMissionStatus(): Promise<MissionStatus> {
    const now = this.simNow()
    const lostAt = this.linkLostAt(now)
    return this.delay({
      simulated: true,
      scenarioId: this.scenario.id,
      scenarioLabel: this.scenario.label,
      now,
      missionStartDate: MISSION_START_DATE,
      link: lostAt
        ? { state: 'offline', since: lostAt, lastContactAt: lostAt }
        : { state: 'connected', since: SESSION_START, lastContactAt: toIso(toMs(now) - 5000) },
    })
  }

  async listCrew(): Promise<CrewMember[]> {
    return this.delay(
      CREW_PROFILES.map((p) => {
        const imported = storedImports()[p.id]
        return imported?.displayName
          ? { id: p.id, displayName: imported.displayName, note: `Profile imported from ${imported.files[0] ?? 'a JSON file'}` }
          : { id: p.id, displayName: p.displayName, note: PSEUDONYM_NOTE }
      }),
    )
  }

  private series(crewId: string, parameter: ParameterId): TimeSeries {
    const profile = this.requireCrew(crewId)
    const until = receivedUntilOffset(crewId, this.scenario.flags, this.simNow())
    const samples = generateSamples({
      profile,
      parameter,
      seedKey: `${crewId}-${parameter}-today`,
      untilOffsetS: until,
      flags: this.scenario.flags,
    })
    return {
      crewId,
      parameter,
      unit: PARAMETERS[parameter].unit,
      source: sourceFor(crewId, parameter),
      samples,
      receivedAt: samples.length ? samples[samples.length - 1].t : null,
    }
  }

  async getSeries(crewId: string, parameters: ParameterId[], from: string, to: string): Promise<TimeSeries[]> {
    const a = toMs(from)
    const b = toMs(to)
    if (!(a <= b)) throw new DataSourceError('bad_request', 'Invalid time range', 400)
    const result = parameters.map((p) => {
      const s = this.series(crewId, p)
      return { ...s, samples: s.samples.filter((x) => toMs(x.t) >= a && toMs(x.t) <= b) }
    })
    return this.delay(result)
  }

  async getActivities(crewId: string, from: string, to: string): Promise<ActivitySegment[]> {
    this.requireCrew(crewId)
    const a = toMs(from)
    const b = toMs(to)
    return this.delay(activitiesFor(crewId).filter((s) => toMs(s.end) >= a && toMs(s.start) <= b))
  }

  async getCrewSnapshot(crewId: string): Promise<CrewSnapshot> {
    const profile = this.requireCrew(crewId)
    const parameters = PARAMETER_ORDER.map((p) => {
      const samples = this.series(crewId, p).samples
      const latest = samples[samples.length - 1] ?? null
      const lastValid = [...samples].reverse().find((s) => s.value !== null) ?? null
      return { parameter: p, latest, lastValidSample: lastValid }
    })
    const lastReceivedAt = parameters.reduce<string | null>((acc, p) => {
      const t = p.latest?.t ?? null
      return t && (!acc || t > acc) ? t : acc
    }, null)
    const now = this.simNow()
    const fresh = computeFreshness(lastReceivedAt, now, SAMPLE_INTERVAL_S)
    const state: DeviceState = fresh === 'current' ? 'streaming' : fresh === 'delayed' ? 'delayed' : 'not_reporting'
    const nowMs = toMs(now)
    const activity = activitiesFor(crewId).find((s) => toMs(s.start) <= nowMs && toMs(s.end) > nowMs) ?? null
    return this.delay({
      crew: { id: profile.id, displayName: profile.displayName, note: PSEUDONYM_NOTE },
      activity,
      device: { state, lastReceivedAt, expectedIntervalS: SAMPLE_INTERVAL_S },
      parameters,
      openEvents: this.visibleEvents().filter((e) => e.crewId === crewId && e.status !== 'reviewed').length,
    })
  }

  async getReferenceBand(crewId: string, parameter: ParameterId, protocolId: string): Promise<ReferenceBand | null> {
    const profile = this.requireCrew(crewId)
    if (profile.protocolId !== protocolId) return this.delay(null)
    return this.delay(buildReferenceBand(crewId, parameter))
  }

  async listEvents(filter?: { crewId?: string; status?: EventStatus[] }): Promise<ReviewEvent[]> {
    const list = this.visibleEvents()
      .filter((e) => !filter?.crewId || e.crewId === filter.crewId)
      .filter((e) => !filter?.status || filter.status.includes(e.status))
      .sort((a, b) => (a.detectedAt < b.detectedAt ? 1 : -1))
    return this.delay(list)
  }

  async getEvent(eventId: string): Promise<ReviewEvent> {
    return this.delay(this.present(this.findEvent(eventId), this.simNow()))
  }

  async updateEventStatus(eventId: string, status: EventStatus): Promise<ReviewEvent> {
    const e = this.findEvent(eventId)
    e.status = status
    if (e.kind === 'crew_report') storeCrewReport(e)
    return this.delay(this.present(e, this.simNow()))
  }

  async addAnnotation(eventId: string, text: string): Promise<ReviewEvent> {
    const e = this.findEvent(eventId)
    const clean = text.trim()
    if (!clean) throw new DataSourceError('bad_request', 'The note is empty', 400)
    e.annotations.push({
      id: this.nextId('NT'),
      authorRole: 'flight_surgeon',
      authorLabel: 'Flight Surgeon (demo)',
      createdAt: this.simNow(),
      text: clean.slice(0, 2000),
    })
    if (e.kind === 'crew_report') storeCrewReport(e)
    return this.delay(this.present(e, this.simNow()))
  }

  async listCrewMessages(crewId: string): Promise<CrewMessage[]> {
    this.requireCrew(crewId)
    return this.delay(this.messages.filter((m) => m.crewId === crewId).sort((a, b) => (a.id < b.id ? 1 : -1)))
  }

  async sendCrewMessage(crewId: string, templateId: string, relatedEventId: string | null): Promise<CrewMessage> {
    this.requireCrew(crewId)
    const tpl = CREW_MESSAGE_TEMPLATES.find((t) => t.id === templateId)
    if (!tpl) throw new DataSourceError('bad_request', 'Unknown message template', 400)
    if (this.linkLostAt(this.simNow())) {
      throw new DataSourceError('unavailable', 'No link with the crew: message not sent', 503)
    }
    const msg: CrewMessage = {
      id: this.nextId('MSG'),
      crewId,
      createdAt: this.simNow(),
      templateId,
      text: tpl.text,
      from: 'Ground medical team',
      relatedEventId,
    }
    this.messages.push(msg)
    return this.delay(msg)
  }

  /* ---------- long-duration mission ---------- */

  async getDailyIndicators(crewId: string): Promise<DailyIndicatorSeries[]> {
    this.requireCrew(crewId)
    // Day-to-day indicators imported from a CSV replace the synthetic ones for that crew member.
    const imported = storedImports()[crewId]
    if (imported?.series.length) return this.delay(imported.series)
    return this.delay(withDemoMeasurements(generateDailyIndicators(crewId, this.simNow(), this.scenario.flags), measurementsFor(crewId), missionDayOf(this.simNow()), this.simNow().slice(0, 10)))
  }

  private checkInsOf(crewId: string): CheckIn[] {
    if (!this.checkIns.has(crewId)) {
      const saved = storedCheckIns()[crewId]
      this.checkIns.set(crewId, saved ?? (this.samples ? seedCheckIns(crewId, this.simNow(), this.scenario.flags) : []))
    }
    return this.checkIns.get(crewId)!
  }

  async listCheckIns(crewId: string): Promise<CheckIn[]> {
    this.requireCrew(crewId)
    return this.delay(this.checkInsOf(crewId))
  }

  async submitCheckIn(crewId: string, input: CheckInInput): Promise<CheckIn> {
    this.requireCrew(crewId)
    const scores = [input.sleepQuality, input.energy, input.mood]
    if (!scores.every((v) => Number.isInteger(v) && v >= 1 && v <= 5)) throw new DataSourceError('bad_request', 'Each answer must be between 1 and 5', 400)
    const now = this.simNow()
    const checkIn: CheckIn = {
      ...input,
      note: input.note.trim().slice(0, 500),
      id: this.nextId('CI'),
      crewId,
      date: now.slice(0, 10),
      missionDay: missionDayOf(now),
      createdAt: now,
    }
    const list = this.checkInsOf(crewId).filter((c) => c.date !== checkIn.date)
    this.checkIns.set(crewId, [checkIn, ...list])
    storeCheckIns(crewId, [checkIn, ...list])
    return this.delay(checkIn)
  }

  async shareWithMedicalTeam(crewId: string, note: string): Promise<ReviewEvent> {
    const profile = this.requireCrew(crewId)
    const now = this.simNow()
    if (this.linkLostAt(now)) {
      throw new DataSourceError('unavailable', 'No link with the ground: not sent. Try again when the link is back', 503)
    }
    const clean = note.trim().slice(0, 500)
    const event: ReviewEvent = {
      // Continues the demo numbering (EV-0142…EV-0144 are the rule-generated events).
      id: `CR-${Date.now()}-${this.nextId('R')}`,
      crewId,
      parameter: null,
      kind: 'crew_report',
      detectedAt: now,
      window: { start: now, end: now },
      status: 'open',
      trigger: {
        ruleId: 'CREW-SHARE',
        description: clean
          ? `${profile.displayName} shared their daily trends from “My health” with this note: “${clean}”`
          : `${profile.displayName} shared their daily trends from “My health”.`,
        simulated: false,
      },
      annotations: [],
    }
    this.events.push(event)
    storeCrewReport(event)
    return this.delay(event)
  }

  /* ---------- sleep-aid schedule ---------- */

  private sleepPlan: SleepAidPlanEntry[] | null = null

  private plan(): SleepAidPlanEntry[] {
    if (!this.sleepPlan) this.sleepPlan = storedSleepAidPlan() ?? (this.samples ? seedSleepAidPlan(this.simNow()) : [])
    return this.sleepPlan
  }

  async listSleepAidPlan(from: string, to: string): Promise<SleepAidPlanEntry[]> {
    if (!(from <= to)) throw new DataSourceError('bad_request', 'Invalid date range', 400)
    return this.delay(this.plan().filter((e) => e.night >= from && e.night <= to).sort((a, b) => (a.night < b.night ? -1 : 1)))
  }

  async recordMeasurements(crewId: string, readings: DeviceMeasurement[]): Promise<void> {
    this.requireCrew(crewId)
    for (const r of readings) storeMeasurement(r)
    return this.delay(undefined)
  }

  async listEvaluations(crewId: string): Promise<BackendEvaluation[]> {
    this.requireCrew(crewId)
    return this.delay([])
  }

  /* ---------- nutrition ---------- */

  private intake: IntakeEntry[] | null = null

  private intakeLog(): IntakeEntry[] {
    if (!this.intake) this.intake = storedIntake() ?? (this.samples ? CREW_PROFILES.flatMap((p) => seedIntake(p.id, this.simNow(), missionDayOf(this.simNow()))) : [])
    return this.intake
  }

  async getNutritionProfile(crewId: string): Promise<NutritionProfile> {
    this.requireCrew(crewId)
    const daily = await this.getDailyIndicators(crewId)
    const latest = [...(daily.find((s) => s.indicator === 'body_mass')?.days ?? [])].reverse().find((d) => d.value !== null)?.value ?? null
    const saved = storedProfiles()[crewId]
    const mass = latest ?? saved?.bodyMassKg ?? 75
    if (saved) return this.delay({ ...saved, bodyMassKg: mass, source: latest !== null ? 'Your profile · latest body mass' : saved.bodyMassKg ? 'Your profile' : 'Your profile · no body-mass reading yet, 75 kg used' })
    const imported = storedImports()[crewId]?.nutrition
    const base = this.samples ? NUTRITION_PROFILES[crewId] : { sex: 'male' as const, ageYears: 40, heightM: 1.75, menstruating: false }
    return this.delay({ ...base, ...(imported ?? {}), bodyMassKg: mass, source: imported ? 'Imported profile' : this.samples ? 'Sample profile' : 'Profile not set: standard values' })
  }

  async saveNutritionProfile(crewId: string, profile: Omit<NutritionProfile, 'bodyMassKg' | 'source'>): Promise<void> {
    this.requireCrew(crewId)
    storeProfile(crewId, profile)
    return this.delay(undefined)
  }

  async importDaily(crewId: string, series: DailyIndicatorSeries[], meta: { displayName: string | null; files: string[] }): Promise<void> {
    this.requireCrew(crewId)
    storeImport({ crewId, displayName: meta.displayName, role: null, series, files: meta.files, importedAt: new Date().toISOString() })
    return this.delay(undefined)
  }

  async listIntake(crewId: string, from: string, to: string): Promise<IntakeEntry[]> {
    this.requireCrew(crewId)
    return this.delay(this.intakeLog().filter((e) => e.crewId === crewId && e.eatenAt >= from && e.eatenAt < to).sort((a, b) => (a.eatenAt < b.eatenAt ? -1 : 1)))
  }

  async addIntake(entry: IntakeEntry): Promise<IntakeEntry> {
    this.requireCrew(entry.crewId)
    this.intake = [...this.intakeLog(), entry]
    storeIntake(this.intake)
    return this.delay(entry)
  }

  async removeIntake(crewId: string, entryId: string): Promise<void> {
    this.intake = this.intakeLog().filter((e) => !(e.crewId === crewId && e.id === entryId))
    storeIntake(this.intake)
    return this.delay(undefined)
  }

  async listFoods(): Promise<Food[]> {
    return this.delay([...ISS_FOODS, ...storedCustomFoods()])
  }

  async saveCustomFood(food: Food): Promise<Food> {
    const saved = { ...food, custom: true }
    storeCustomFoods([...storedCustomFoods().filter((f) => f.id !== food.id), saved])
    return this.delay(saved)
  }

  async setSleepAidPlan(crewId: string, night: string, planned: boolean): Promise<SleepAidPlanEntry[]> {
    this.requireCrew(crewId)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(night)) throw new DataSourceError('bad_request', 'Invalid night', 400)
    if (night < this.simNow().slice(0, 10)) throw new DataSourceError('bad_request', 'Past nights cannot be changed', 400)
    const without = this.plan().filter((e) => !(e.crewId === crewId && e.night === night))
    this.sleepPlan = planned ? [...without, { crewId, night, updatedAt: this.simNow(), simulated: true }] : without
    storeSleepAidPlan(this.sleepPlan)
    return this.delay(this.sleepPlan.filter((e) => e.night === night))
  }
}

/**
 * Deterministic demo plan around "today". Night +4 is planned by every crew
 * member on purpose, so the coordination warning can be demonstrated.
 */
export function seedSleepAidPlan(nowIso: string): SleepAidPlanEntry[] {
  const day = (offset: number) => new Date(Date.parse(nowIso.slice(0, 10)) + offset * 86_400_000).toISOString().slice(0, 10)
  const plan: [string, number][] = [
    ['crew-a', -5], ['crew-b', -4], ['crew-c', -2], ['crew-a', -1],
    ['crew-b', 0], ['crew-a', 1], ['crew-c', 2], ['crew-b', 3],
    ['crew-a', 4], ['crew-b', 4], ['crew-c', 4],
    ['crew-c', 7], ['crew-b', 9],
  ]
  return plan.map(([crewId, offset]) => ({ crewId, night: day(offset), updatedAt: nowIso, simulated: true }))
}
