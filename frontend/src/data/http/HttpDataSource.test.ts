import { describe, expect, it } from 'vitest'
import { HttpDataSource } from './HttpDataSource'
import { DataSourceError } from '../DataSource'

/**
 * Contract tests: the adapter must speak the API described in
 * docs/FRONTEND_DATA_CONTRACT.md. They use a fake fetch, so they say nothing about a
 * real backend — they pin down what the frontend sends and how it reacts.
 */

interface Call {
  url: string
  method: string
  body: unknown
  headers: Record<string, string>
}

function fakeFetch(respond: (call: Call) => Response | Promise<Response>) {
  const calls: Call[] = []
  const fn: typeof fetch = async (input, init) => {
    const call: Call = {
      url: String(input),
      method: init?.method ?? 'GET',
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
      headers: (init?.headers ?? {}) as Record<string, string>,
    }
    calls.push(call)
    return respond(call)
  }
  return { fn, calls }
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const apiError = (status: number, code: string, message: string) => json({ error: { code, message, details: {} } }, status)

describe('HttpDataSource — requests', () => {
  it('builds URLs from the base URL (trailing slash ignored) and encodes path segments', async () => {
    const { fn, calls } = fakeFetch(() => json({}))
    const ds = new HttpDataSource('http://api.test/api/v1/', fn)
    await ds.getMissionStatus()
    await ds.getCrewSnapshot('crew a/1')
    expect(calls.map((c) => c.url)).toEqual(['http://api.test/api/v1/mission/status', 'http://api.test/api/v1/crew/crew%20a%2F1/snapshot'])
  })

  it('sends series and event filters as query parameters', async () => {
    const { fn, calls } = fakeFetch(() => json({ items: [] }))
    const ds = new HttpDataSource('/api/v1', fn)
    await ds.getSeries('crew-b', ['heart_rate', 'spo2'], '2026-11-14T10:00:00Z', '2026-11-14T10:40:00Z')
    await ds.listEvents({ crewId: 'crew-b', status: ['open', 'in_review'] })
    await ds.listEvents()
    const [series, filtered, all] = calls.map((c) => new URL(c.url, 'http://x'))
    expect(series.pathname).toBe('/api/v1/crew/crew-b/series')
    expect(Object.fromEntries(series.searchParams)).toEqual({ parameters: 'heart_rate,spo2', from: '2026-11-14T10:00:00Z', to: '2026-11-14T10:40:00Z' })
    expect(Object.fromEntries(filtered.searchParams)).toEqual({ crewId: 'crew-b', status: 'open,in_review' })
    expect([...all.searchParams]).toEqual([])
  })

  it('sends mutations with the contract method, JSON body and Content-Type', async () => {
    const { fn, calls } = fakeFetch(() => json({}))
    const ds = new HttpDataSource('/api/v1', fn)
    await ds.updateEventStatus('EV-1', 'in_review')
    await ds.addAnnotation('EV-1', 'checked sensor placement')
    await ds.sendCrewMessage('crew-a', 'review_after', 'EV-1')
    expect(calls.map(({ url, method, body }) => ({ url, method, body }))).toEqual([
      { url: '/api/v1/events/EV-1', method: 'PATCH', body: { status: 'in_review' } },
      { url: '/api/v1/events/EV-1/annotations', method: 'POST', body: { text: 'checked sensor placement' } },
      { url: '/api/v1/crew/crew-a/messages', method: 'POST', body: { templateId: 'review_after', relatedEventId: 'EV-1' } },
    ])
    expect(calls.every((c) => c.headers['Content-Type'] === 'application/json')).toBe(true)
  })

  it('does not send a Content-Type on reads', async () => {
    const { fn, calls } = fakeFetch(() => json({ items: [] }))
    await new HttpDataSource('/api/v1', fn).listCrew()
    expect(calls[0].headers['Content-Type']).toBeUndefined()
    expect(calls[0].headers.Accept).toBe('application/json')
  })
})

describe('HttpDataSource — responses', () => {
  it('unwraps { items } lists', async () => {
    const crew = [{ id: 'crew-a', displayName: 'Crew A', note: '' }]
    const { fn } = fakeFetch(() => json({ items: crew }))
    expect(await new HttpDataSource('/api/v1', fn).listCrew()).toEqual(crew)
  })

  it('treats 404 on /reference as "no history" (null), as the contract specifies', async () => {
    const { fn } = fakeFetch(() => apiError(404, 'not_found', 'No history'))
    expect(await new HttpDataSource('/api/v1', fn).getReferenceBand('crew-a', 'heart_rate', 'EX-CICLO-30')).toBeNull()
  })

  it('surfaces the backend error code and message elsewhere', async () => {
    const { fn } = fakeFetch(() => apiError(404, 'not_found', 'Event "EV-9" not found'))
    await expect(new HttpDataSource('/api/v1', fn).getEvent('EV-9')).rejects.toMatchObject({
      code: 'not_found',
      message: 'Event "EV-9" not found',
      status: 404,
    })
  })

  it('maps 503 to "unavailable" (e.g. a message sent with no ground link)', async () => {
    const { fn } = fakeFetch(() => apiError(503, 'unavailable', 'No link with the crew'))
    await expect(new HttpDataSource('/api/v1', fn).sendCrewMessage('crew-a', 'ack_no_action', null)).rejects.toMatchObject({ code: 'unavailable' })
  })

  it('maps a non-JSON error body by HTTP status', async () => {
    const { fn } = fakeFetch(() => new Response('<html>Bad gateway</html>', { status: 502 }))
    await expect(new HttpDataSource('/api/v1', fn).listCrew()).rejects.toMatchObject({ code: 'unavailable', message: 'Error 502' })
  })

  it('maps a network failure to "unavailable"', async () => {
    const { fn } = fakeFetch(() => Promise.reject(new TypeError('Failed to fetch')))
    const error = await new HttpDataSource('/api/v1', fn).getMissionStatus().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(DataSourceError)
    expect(error).toMatchObject({ code: 'unavailable', message: 'Service unreachable' })
  })

  it('reports an invalid success body as an internal error instead of crashing', async () => {
    const { fn } = fakeFetch(() => new Response('not json', { status: 200 }))
    await expect(new HttpDataSource('/api/v1', fn).getMissionStatus()).rejects.toMatchObject({ code: 'internal' })
  })
})
