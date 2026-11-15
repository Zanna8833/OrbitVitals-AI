import { describe, expect, it } from 'vitest'
import { BackendDataSource, baselineFrom } from './BackendDataSource'
import type { BackendMeasurement } from '../../domain/metricCatalog'

/** Shapes copied from real responses of the team's backend (demo seed). */
const meas = (metric: string, value: number, at: string, unit = 'bpm', extra: Partial<BackendMeasurement> = {}): BackendMeasurement => ({
  measurement_id: `${metric}-${at}`, crew_member_id: 'sim-1', metric, unit, value, measured_at: at, interval_end: null,
  source: 'simulated', device_id: 'dev', data_quality: { status: 'acceptable' }, ...extra,
})

function fakeBackend(items: BackendMeasurement[]) {
  const calls: { url: string; init?: RequestInit }[] = []
  const fetchFn = (async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
    if (url.endsWith('/health')) return json({ status: 'ok' })
    if (url.includes('/measurements') && !init?.method) return json({ items })
    if (url.includes('/baselines')) return json({ items: [] })
    if (url.includes('/evaluations')) return json({ items: [{ evaluation_id: 'e1', domain: 'sleep', status: 'attention', summary: 'x', findings: [], window_start: '', window_end: '', crew_member_id: 'sim-1' }] })
    if (init?.method === 'POST') return json({ items: JSON.parse(String(init.body)).measurements }, 201)
    return json({ detail: 'not found' }, 404)
  }) as unknown as typeof fetch
  return { calls, fetchFn }
}

const crew = [{ id: 'crew-a', backendId: 'sim-1', displayName: 'Vega' }]

describe('BackendDataSource', () => {
  const items = [
    meas('heart_rate', 60, '2026-10-01T08:00:00Z'),
    meas('heart_rate', 62, '2026-10-02T08:00:00Z'),
    meas('sleep_duration', 420, '2026-10-01T22:00:00Z', 'min', { interval_end: '2026-10-02T05:00:00Z' }),
  ]

  it('derives mission day 1 and "now" from the stored measurements', async () => {
    const { fetchFn } = fakeBackend(items)
    const ds = new BackendDataSource('http://api/api/v1/', crew, { fetchFn })
    const m = await ds.getMissionStatus()
    expect(m.missionStartDate).toBe('2026-10-01')
    expect(m.now.slice(0, 10)).toBe('2026-10-02')
    expect((await ds.listCrew())[0]).toMatchObject({ id: 'crew-a', displayName: 'Vega' })
  })

  it('builds daily series from backend metrics with canonical unit conversion', async () => {
    const { fetchFn } = fakeBackend(items)
    const ds = new BackendDataSource('http://api/api/v1', crew, { fetchFn })
    const daily = await ds.getDailyIndicators('crew-a')
    const hr = daily.find((s) => s.indicator === 'resting_hr')!
    expect(hr.days.map((d) => d.value)).toEqual([60, 62])
    expect(hr.origin).toBe('backend')
    expect(daily.find((s) => s.indicator === 'sleep_duration')!.days[1].value).toBe(7)
    expect(daily.find((s) => s.indicator === 'bp_systolic')!.days.every((d) => d.quality === 'missing')).toBe(true)
  })

  it('posts readings and intake as canonical measurements', async () => {
    const { fetchFn, calls } = fakeBackend(items)
    const ds = new BackendDataSource('http://api/api/v1', crew, { fetchFn })
    await ds.recordMeasurements('crew-a', [
      { id: 'r1', crewId: 'crew-a', indicator: 'sleep_duration', value: 7.5, quality: 'good', simulated: true, deviceLabel: 'x', acquiredAt: '2026-10-02T06:00:00Z', savedAtMs: 0, signal: 'clear', context: '', manual: true },
    ])
    const sent = JSON.parse(String(calls.find((c) => c.init?.method === 'POST')!.init!.body)).measurements[0]
    expect(sent).toMatchObject({ crew_member_id: 'sim-1', metric: 'sleep_duration', unit: 'min', value: 450, source: 'manual_entry', interval_end: '2026-10-02T06:00:00Z' })
    await ds.addIntake({ id: 'in1', crewId: 'crew-a', eatenAt: '2026-10-02T12:00:00Z', foodId: null, servings: 1, values: { fluid_intake: 500 }, label: 'Water' })
    const posts = calls.filter((c) => c.init?.method === 'POST')
    expect(JSON.parse(String(posts[1].init!.body)).measurements).toEqual([
      expect.objectContaining({ measurement_id: 'in1~fluid_intake', metric: 'fluid_intake', unit: 'mL', value: 500 }),
    ])
  })

  it('reads evaluations and turns an established baseline into a usual range', async () => {
    const { fetchFn } = fakeBackend(items)
    const ds = new BackendDataSource('http://api/api/v1', crew, { fetchFn })
    expect((await ds.listEvaluations('crew-a'))[0].status).toBe('attention')
    const b = baselineFrom('sleep_duration', [
      { baseline_id: 'b', crew_member_id: 'sim-1', metric: 'sleep_duration', unit: 'min', status: 'established', window_start: '2026-10-01T12:00:00Z', window_end: '2026-10-08T12:00:00Z', sample_count: 7, statistics: { mean: 420, standard_deviation: 5, median: 420, median_absolute_deviation: 6, minimum: 400, maximum: 440 } },
    ], '2026-10-01')!
    expect(b.median).toBe(7)
    expect(b.low).toBe(6.5) // minimum half-width 0.5 h wins over 2 × 1.4826 × 0.1 h
    expect(b.fromDay).toBe(1)
  })

  it('reports an unreachable backend', async () => {
    const ds = new BackendDataSource('http://api/api/v1', crew, { fetchFn: (async () => { throw new TypeError('down') }) as unknown as typeof fetch })
    await expect(ds.getMissionStatus()).rejects.toThrow(/not reachable/)
  })
})
