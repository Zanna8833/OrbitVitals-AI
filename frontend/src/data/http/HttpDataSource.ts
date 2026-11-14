import type { DataSource } from '../DataSource'
import { DataSourceError } from '../DataSource'
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
} from '../../domain/types'

/**
 * HTTP adapter for the endpoints proposed in docs/API_CONTRACT.md.
 * NOT yet tested against a real backend: the backend does not exist yet.
 */
export class HttpDataSource implements DataSource {
  readonly kind = 'http' as const
  private readonly baseUrl: string
  private readonly fetchFn: typeof fetch

  /** `fetchFn` is injectable so the adapter can be contract-tested without a server. */
  constructor(baseUrl: string, fetchFn: typeof fetch = (input, init) => globalThis.fetch(input, init)) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
    this.fetchFn = fetchFn
  }

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    let res: Response
    try {
      res = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...init,
        headers: { Accept: 'application/json', ...(init?.body ? { 'Content-Type': 'application/json' } : {}), ...init?.headers },
      })
    } catch {
      throw new DataSourceError('unavailable', 'Service unreachable')
    }
    if (!res.ok) {
      let message = `Error ${res.status}`
      let code: DataSourceError['code'] = 'internal'
      try {
        const body = (await res.json()) as { error?: { code?: string; message?: string } }
        if (body.error?.message) message = body.error.message
        if (body.error?.code) code = mapCode(body.error.code, res.status)
      } catch {
        code = mapCode(undefined, res.status)
      }
      throw new DataSourceError(code, message, res.status)
    }
    try {
      return (await res.json()) as T
    } catch {
      throw new DataSourceError('internal', 'Invalid response from the service', res.status)
    }
  }

  getMissionStatus() {
    return this.request<MissionStatus>('/mission/status')
  }
  async listCrew() {
    return (await this.request<{ items: CrewMember[] }>('/crew')).items
  }
  getCrewSnapshot(crewId: string) {
    return this.request<CrewSnapshot>(`/crew/${encodeURIComponent(crewId)}/snapshot`)
  }
  async getSeries(crewId: string, parameters: ParameterId[], from: string, to: string) {
    const q = new URLSearchParams({ parameters: parameters.join(','), from, to })
    return (await this.request<{ items: TimeSeries[] }>(`/crew/${encodeURIComponent(crewId)}/series?${q}`)).items
  }
  async getActivities(crewId: string, from: string, to: string) {
    const q = new URLSearchParams({ from, to })
    return (await this.request<{ items: ActivitySegment[] }>(`/crew/${encodeURIComponent(crewId)}/activities?${q}`)).items
  }
  async getReferenceBand(crewId: string, parameter: ParameterId, protocolId: string) {
    const q = new URLSearchParams({ parameter, protocolId })
    try {
      return await this.request<ReferenceBand>(`/crew/${encodeURIComponent(crewId)}/reference?${q}`)
    } catch (e) {
      // 404 = no history for this protocol: an expected, empty state.
      if (e instanceof DataSourceError && e.code === 'not_found') return null
      throw e
    }
  }
  async listEvents(filter?: { crewId?: string; status?: EventStatus[] }) {
    const q = new URLSearchParams()
    if (filter?.crewId) q.set('crewId', filter.crewId)
    if (filter?.status?.length) q.set('status', filter.status.join(','))
    return (await this.request<{ items: ReviewEvent[] }>(`/events?${q}`)).items
  }
  getEvent(eventId: string) {
    return this.request<ReviewEvent>(`/events/${encodeURIComponent(eventId)}`)
  }
  updateEventStatus(eventId: string, status: EventStatus) {
    return this.request<ReviewEvent>(`/events/${encodeURIComponent(eventId)}`, { method: 'PATCH', body: JSON.stringify({ status }) })
  }
  addAnnotation(eventId: string, text: string) {
    return this.request<ReviewEvent>(`/events/${encodeURIComponent(eventId)}/annotations`, { method: 'POST', body: JSON.stringify({ text }) })
  }
  async listCrewMessages(crewId: string) {
    return (await this.request<{ items: CrewMessage[] }>(`/crew/${encodeURIComponent(crewId)}/messages`)).items
  }
  sendCrewMessage(crewId: string, templateId: string, relatedEventId: string | null) {
    return this.request<CrewMessage>(`/crew/${encodeURIComponent(crewId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ templateId, relatedEventId }),
    })
  }
  async getDailyIndicators(crewId: string) {
    return (await this.request<{ items: DailyIndicatorSeries[] }>(`/crew/${encodeURIComponent(crewId)}/daily-indicators`)).items
  }
  async listCheckIns(crewId: string) {
    return (await this.request<{ items: CheckIn[] }>(`/crew/${encodeURIComponent(crewId)}/check-ins`)).items
  }
  submitCheckIn(crewId: string, input: CheckInInput) {
    return this.request<CheckIn>(`/crew/${encodeURIComponent(crewId)}/check-ins`, { method: 'POST', body: JSON.stringify(input) })
  }
  shareWithMedicalTeam(crewId: string, note: string) {
    return this.request<ReviewEvent>(`/crew/${encodeURIComponent(crewId)}/reports`, { method: 'POST', body: JSON.stringify({ note }) })
  }
  async listSleepAidPlan(from: string, to: string) {
    const q = new URLSearchParams({ from, to })
    return (await this.request<{ items: SleepAidPlanEntry[] }>(`/sleep-aid-plan?${q}`)).items
  }
  async setSleepAidPlan(crewId: string, night: string, planned: boolean) {
    return (
      await this.request<{ items: SleepAidPlanEntry[] }>(`/crew/${encodeURIComponent(crewId)}/sleep-aid-plan/${encodeURIComponent(night)}`, {
        method: 'PUT',
        body: JSON.stringify({ planned }),
      })
    ).items
  }
}

export function mapCode(code: string | undefined, status: number): DataSourceError['code'] {
  if (code === 'not_found' || status === 404) return 'not_found'
  if (code === 'bad_request' || code === 'validation_error' || status === 400 || status === 422) return 'bad_request'
  if (code === 'unauthorized' || status === 401 || status === 403) return 'unauthorized'
  if (code === 'unavailable' || status === 502 || status === 503 || status === 504) return 'unavailable'
  return 'internal'
}
