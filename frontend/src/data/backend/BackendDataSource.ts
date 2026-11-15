import { DataSourceError, type DataSource } from '../DataSource'
import type { BackendCrew } from '../../config'
import type { CrewMember, DailyIndicatorSeries, DailyValue, MissionStatus, PersonalBaseline } from '../../domain/types'
import { DAILY_INDICATOR_ORDER, DAILY_INDICATORS } from '../../domain/parameters'
import {
  INDICATOR_METRIC,
  NUTRIENT_UNIT,
  dailyFromMeasurements,
  type BackendBaseline,
  type BackendEvaluation,
  type BackendMeasurement,
} from '../../domain/metricCatalog'
import { NUTRIENTS, entryValues, type Food, type IntakeEntry, type NutrientId } from '../../domain/nutrition'
import type { DeviceMeasurement } from '../../domain/measurements'
import { MockDataSource } from '../mock/MockDataSource'
import { MIN_HALF_WIDTH, baselineOf } from '../mock/daily'
import { missionDayOf } from '../../domain/time'

/**
 * Adapter for the team's FastAPI backend (backend/, /api/v1; docs/frontend-integration.md).
 *
 * From the backend: measurements (read and write), personal baselines,
 * evaluations, nutrition intake (stored as nutrition-domain measurements).
 * The backend has no crew directory, mission timeline, sessions, review
 * events, messages, check-ins or sleep plan yet: those stay local, inherited
 * from the demo implementation, and the interface keeps labelling them.
 */
export class BackendDataSource extends MockDataSource implements DataSource {
  override readonly kind = 'http' as const
  private readonly base: string
  private readonly crewMap: BackendCrew[]
  private readonly fetchFn: typeof fetch
  private nowIso = '2026-11-14T10:40:00Z'
  private startDate = '2026-10-31'
  private readonly ready: Promise<void>
  private cache = new Map<string, Promise<BackendMeasurement[]>>()

  constructor(
    baseUrl: string,
    crewMap: BackendCrew[],
    options: { asOf?: string; missionStart?: string; fetchFn?: typeof fetch; latencyMs?: number } = {},
  ) {
    super('nominal', options.latencyMs ?? 0, () => this.nowIso, false)
    this.base = baseUrl.replace(/\/$/, '')
    this.crewMap = crewMap
    this.fetchFn = options.fetchFn ?? ((input, init) => globalThis.fetch(input, init))
    this.ready = this.init(options.asOf, options.missionStart)
    // Every read waits until "now" and mission day 1 are known.
    for (const name of WAIT_FOR_READY) {
      const self = this as unknown as Record<string, (...a: unknown[]) => Promise<unknown>>
      const original = self[name].bind(this)
      self[name] = async (...args: unknown[]) => {
        await this.ready
        return original(...args)
      }
    }
  }

  /* ---------- HTTP ---------- */

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response
    try {
      res = await this.fetchFn(`${this.base}${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}) },
      })
    } catch {
      throw new DataSourceError('unavailable', `OrbitVitals backend not reachable at ${this.base}`)
    }
    if (!res.ok) {
      let message = `Backend error ${res.status}`
      try {
        const body = (await res.json()) as { detail?: unknown }
        if (typeof body.detail === 'string') message = body.detail
        else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join('; ') || message
      } catch {
        /* not JSON */
      }
      const code = res.status === 404 ? 'not_found' : res.status === 422 || res.status === 409 ? 'bad_request' : res.status >= 500 ? 'unavailable' : 'internal'
      throw new DataSourceError(code, message, res.status)
    }
    return (await res.json()) as T
  }

  private backendId(crewId: string): string {
    const c = this.crewMap.find((x) => x.id === crewId)
    if (!c) throw new DataSourceError('not_found', `Crew member "${crewId}" is not mapped to the backend`, 404)
    return c.backendId
  }

  private measurements(crewId: string): Promise<BackendMeasurement[]> {
    const id = this.backendId(crewId)
    if (!this.cache.has(id)) {
      const p = this.request<{ items: BackendMeasurement[] }>(`/crew-members/${encodeURIComponent(id)}/measurements`).then((r) => r.items)
      p.catch(() => this.cache.delete(id))
      this.cache.set(id, p)
    }
    return this.cache.get(id)!
  }

  private async post(items: object[]) {
    if (!items.length) return
    await this.request('/measurements', { method: 'POST', body: JSON.stringify({ measurements: items }) })
    this.cache.clear()
  }

  /** "Now" = configured, or the latest stored measurement; day 1 = configured, or the earliest one. */
  private async init(asOf?: string, missionStart?: string) {
    const all = (await Promise.all(this.crewMap.map((c) => this.measurements(c.id).catch(() => [] as BackendMeasurement[])))).flat()
    const physiological = all.filter((m) => !(m.metric in NUTRIENT_UNIT))
    const times = physiological.map((m) => m.measured_at).sort()
    if (asOf) this.nowIso = new Date(asOf).toISOString()
    else if (times.length) this.nowIso = `${times[times.length - 1].slice(0, 10)}T20:00:00Z`
    if (missionStart) this.startDate = missionStart
    else if (times.length) this.startDate = physiological.map((m) => m.measured_at).sort()[0].slice(0, 10)
    // Fail visibly if the backend is down.
    await this.request('/health')
  }

  /* ---------- overrides ---------- */

  override async getMissionStatus(): Promise<MissionStatus> {
    const local = await super.getMissionStatus()
    return { ...local, now: this.nowIso, missionStartDate: this.startDate, scenarioLabel: 'OrbitVitals backend', link: { state: 'connected', since: this.nowIso, lastContactAt: this.nowIso } }
  }

  override async getCrewSnapshot(crewId: string) {
    const [snap, items] = await Promise.all([super.getCrewSnapshot(crewId), this.measurements(crewId)])
    const c = this.crewMap.find((x) => x.id === crewId)
    // Freshness from the latest stored physiological measurement (daily cadence).
    const last = items.filter((m) => !(m.metric in NUTRIENT_UNIT) && m.measured_at <= this.nowIso).map((m) => m.measured_at).sort().pop() ?? null
    return {
      ...snap,
      crew: c ? { ...snap.crew, displayName: c.displayName, note: `Backend crew member ${c.backendId}` } : snap.crew,
      device: { ...snap.device, lastReceivedAt: last, expectedIntervalS: 86_400 },
    }
  }

  override async listCrew(): Promise<CrewMember[]> {
    return this.crewMap.map((c) => ({ id: c.id, displayName: c.displayName, note: `Backend crew member ${c.backendId}` }))
  }

  override async getDailyIndicators(crewId: string): Promise<DailyIndicatorSeries[]> {
    const [items, baselines] = await Promise.all([
      this.measurements(crewId),
      this.request<{ items: BackendBaseline[] }>(`/crew-members/${encodeURIComponent(this.backendId(crewId))}/baselines`).then((r) => r.items),
    ])
    const todayDay = missionDayOf(this.nowIso, this.startDate)
    const dateOf = (day: number) => new Date(Date.parse(`${this.startDate}T00:00:00Z`) + (day - 1) * 86_400_000).toISOString().slice(0, 10)
    return DAILY_INDICATOR_ORDER.map((indicator) => {
      const map = INDICATOR_METRIC[indicator]
      const points = dailyFromMeasurements(indicator, items)
      const byDate = new Map(points.map((p) => [p.date, p]))
      const days: DailyValue[] = []
      for (let d = 1; d <= todayDay; d++) {
        const date = dateOf(d)
        const p = byDate.get(date)
        days.push(p ? { date, missionDay: d, value: Number.isNaN(p.value) ? null : round(indicator, p.value), quality: p.quality } : { date, missionDay: d, value: null, quality: 'missing' })
      }
      const sources = new Set(items.filter((m) => m.metric === map.metric).map((m) => m.source))
      return {
        crewId,
        indicator,
        unit: DAILY_INDICATORS[indicator].unit,
        days,
        baseline: baselineFrom(indicator, baselines, this.startDate) ?? relabel(baselineOf(indicator, days)),
        source: `OrbitVitals backend · ${map.metric} (${map.unit})${sources.size ? ` · source: ${[...sources].join(', ')}` : ' · no readings stored'}`,
        simulated: sources.size === 0 || sources.has('simulated'),
        origin: 'backend',
      } satisfies DailyIndicatorSeries
    })
  }

  override async recordMeasurements(crewId: string, readings: DeviceMeasurement[]): Promise<void> {
    const id = this.backendId(crewId)
    await this.post(
      readings.map((r) => {
        const map = INDICATOR_METRIC[r.indicator]
        const isSleep = map.metric === 'sleep_duration' || map.metric === 'sleep_efficiency'
        const end = r.acquiredAt
        const minutes = r.indicator === 'sleep_duration' ? r.value * 60 : null
        return {
          measurement_id: r.id.slice(0, 120),
          crew_member_id: id,
          metric: map.metric,
          unit: map.unit,
          value: r.value / map.factor,
          // Overnight values cover the night that just ended.
          measured_at: isSleep ? new Date(Date.parse(end) - (minutes ?? 480) * 60_000).toISOString() : r.acquiredAt,
          interval_end: isSleep ? end : null,
          source: r.manual ? 'manual_entry' : 'simulated',
          device_id: r.manual ? 'orbitvitals-web-manual' : 'orbitvitals-web-simulated-device',
        }
      }),
    )
  }

  override async listEvaluations(crewId: string): Promise<BackendEvaluation[]> {
    return (await this.request<{ items: BackendEvaluation[] }>(`/crew-members/${encodeURIComponent(this.backendId(crewId))}/evaluations`)).items
  }

  /* ---------- nutrition: intake stored as nutrition-domain measurements ---------- */

  override async listIntake(crewId: string, from: string, to: string): Promise<IntakeEntry[]> {
    const items = (await this.measurements(crewId)).filter((m) => m.metric in NUTRIENT_UNIT && m.measured_at >= from && m.measured_at < to)
    const labels = intakeLabels()
    const byEntry = new Map<string, IntakeEntry>()
    for (const m of items) {
      const entryId = m.measurement_id.split('~')[0]
      if (!byEntry.has(entryId)) {
        byEntry.set(entryId, { id: entryId, crewId, eatenAt: m.measured_at, foodId: null, servings: 1, values: {}, label: labels[entryId] ?? 'Logged intake' })
      }
      byEntry.get(entryId)!.values[m.metric as NutrientId] = m.value
    }
    return [...byEntry.values()].sort((a, b) => (a.eatenAt < b.eatenAt ? -1 : 1))
  }

  override async addIntake(entry: IntakeEntry): Promise<IntakeEntry> {
    const foods = await this.listFoods()
    const values = entryValues(entry, foods)
    const id = this.backendId(entry.crewId)
    await this.post(
      NUTRIENTS.filter((d) => values[d.id] !== null && values[d.id] !== undefined && (values[d.id] as number) > 0).map((d) => ({
        measurement_id: `${entry.id}~${d.id}`,
        crew_member_id: id,
        metric: d.id,
        unit: NUTRIENT_UNIT[d.id],
        value: Number((values[d.id] as number).toFixed(3)),
        measured_at: entry.eatenAt,
        interval_end: null,
        source: 'manual_entry',
        device_id: 'orbitvitals-web-food-log',
      })),
    )
    rememberIntakeLabel(entry.id, entry.label)
    return entry
  }

  /** Imported days become manual-entry measurements on the backend (one per day and indicator). */
  override async importDaily(crewId: string, series: DailyIndicatorSeries[], meta: { displayName: string | null; files: string[] }): Promise<void> {
    const id = this.backendId(crewId)
    const items: object[] = []
    for (const s of series) {
      const map = INDICATOR_METRIC[s.indicator]
      const isSleep = map.metric === 'sleep_duration' || map.metric === 'sleep_efficiency'
      for (const d of s.days) {
        if (d.value === null || d.quality === 'missing') continue
        const end = `${d.date}T07:00:00Z`
        const minutes = s.indicator === 'sleep_duration' ? d.value * 60 : 480
        items.push({
          measurement_id: `import-${id}-${s.indicator}-${d.date}`.slice(0, 128),
          crew_member_id: id,
          metric: map.metric,
          unit: map.unit,
          value: Number((d.value / map.factor).toFixed(4)),
          measured_at: isSleep ? new Date(Date.parse(end) - minutes * 60_000).toISOString() : `${d.date}T08:00:00Z`,
          interval_end: isSleep ? end : null,
          source: 'manual_entry',
          device_id: `import:${(meta.files[0] ?? 'file').slice(0, 100)}`,
        })
      }
    }
    for (let i = 0; i < items.length; i += 1000) await this.post(items.slice(i, i + 1000))
  }

  override async removeIntake(): Promise<void> {
    throw new DataSourceError('bad_request', 'The backend keeps every logged entry: removing one is not supported yet.', 405)
  }

  override async listFoods(): Promise<Food[]> {
    return super.listFoods()
  }
}

/** Methods that must wait for the clock and mission start to be known. */
const WAIT_FOR_READY = [
  'getMissionStatus', 'listCrew', 'getCrewSnapshot', 'getSeries', 'getActivities', 'getReferenceBand', 'listEvents', 'getEvent',
  'listCrewMessages', 'getDailyIndicators', 'listCheckIns', 'listSleepAidPlan', 'getNutritionProfile', 'listIntake', 'listEvaluations',
] as const

function round(indicator: DailyIndicatorSeries['indicator'], v: number) {
  const k = 10 ** DAILY_INDICATORS[indicator].decimals
  return Math.round(v * k) / k
}

/** Usual range from an ESTABLISHED backend baseline: median ± max(2 × 1.4826 × MAD, minimum half-width), as in the interface. */
export function baselineFrom(indicator: DailyIndicatorSeries['indicator'], baselines: BackendBaseline[], startDate: string): PersonalBaseline | null {
  const map = INDICATOR_METRIC[indicator]
  const b = baselines
    .filter((x) => x.metric === map.metric && x.status === 'established' && x.statistics?.median != null && x.statistics.median_absolute_deviation != null)
    .sort((a, b) => (a.window_end < b.window_end ? 1 : -1))[0]
  if (!b || !b.statistics) return null
  const median = b.statistics.median! * map.factor
  const half = Math.max(2 * 1.4826 * b.statistics.median_absolute_deviation! * map.factor, MIN_HALF_WIDTH[indicator])
  const k = 10 ** DAILY_INDICATORS[indicator].decimals
  const r = (v: number) => Math.round(v * k) / k
  return {
    low: r(median - half),
    median: r(median),
    high: r(median + half),
    fromDay: missionDayOf(b.window_start, startDate),
    toDay: Math.max(missionDayOf(b.window_start, startDate), missionDayOf(b.window_end, startDate) - 1),
    basis: `Established by the OrbitVitals backend (${b.algorithm?.name ?? 'personal_baseline'} ${b.algorithm?.version ?? ''}) from ${b.sample_count} readings, ${b.window_start.slice(0, 10)} → ${b.window_end.slice(0, 10)}. Usual range = median ± max(2 × robust SD, minimum margin). A personal comparison, not a clinical reference.`,
  }
}

function relabel(b: PersonalBaseline | null): PersonalBaseline | null {
  return b && { ...b, basis: b.basis.replace('Reference data set.', 'Computed in the interface: the backend has no established baseline for this metric yet.') }
}

const LABELS_KEY = 'orbitvitals-intake-labels'
function intakeLabels(): Record<string, string> {
  try {
    return JSON.parse(window.localStorage.getItem(LABELS_KEY) ?? '{}') as Record<string, string>
  } catch {
    return {}
  }
}
function rememberIntakeLabel(id: string, label: string) {
  try {
    window.localStorage.setItem(LABELS_KEY, JSON.stringify({ ...intakeLabels(), [id]: label }))
  } catch {
    /* labels are a convenience only */
  }
}
