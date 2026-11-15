// Compares what the dashboard plots in Demo mode (frontend generators) and with Demo off
// (FastAPI seeded by app.demo_seed.approved), through the frontend's own data adapters.
//
//   node integrations/approved-demo/compare_sources.mjs http://127.0.0.1:8000/api/v1
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createRequire } from 'node:module'

const base = process.argv[2] ?? 'http://127.0.0.1:8000/api/v1'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const frontend = path.join(root, 'frontend')
const { createServer } = createRequire(path.join(frontend, 'package.json'))('vite')
const memory = new Map()
globalThis.localStorage = { getItem: (k) => memory.get(k) ?? null, setItem: (k, v) => memory.set(k, String(v)), removeItem: (k) => memory.delete(k), clear: () => memory.clear() }
globalThis.window = globalThis

const server = await createServer({ root: frontend, configFile: false, logLevel: 'error', server: { middlewareMode: true, hmr: false }, appType: 'custom' })
let failures = 0
try {
  const load = (p) => server.ssrLoadModule(p)
  const { MockDataSource } = await load('/src/data/mock/MockDataSource.ts')
  const { BackendDataSource } = await load('/src/data/backend/BackendDataSource.ts')
  const { DEFAULT_SCENARIO_ID } = await load('/src/data/mock/scenarios.ts')
  const { fixedClock } = await load('/src/data/mock/clock.ts')
  const { parseBackendCrew } = await load('/src/config.ts')
  const { entryValues } = await load('/src/domain/nutrition.ts')

  const mock = new MockDataSource(DEFAULT_SCENARIO_ID, 0, fixedClock, true)
  const http = new BackendDataSource(base, parseBackendCrew(undefined), { asOf: '2026-11-14T10:40:00Z', missionStart: '2026-10-31' })
  const ms = await mock.getMissionStatus()
  const hs = await http.getMissionStatus()
  console.log(`mission: demo now=${ms.now} start=${ms.missionStartDate} | server now=${hs.now} start=${hs.missionStartDate}`)
  const DAYS = [1, 5, 6, 8, 15]
  const foods = await mock.listFoods()
  for (const crew of ['crew-a', 'crew-b', 'crew-c']) {
    const [a, b] = await Promise.all([mock.getDailyIndicators(crew), http.getDailyIndicators(crew)])
    let points = 0, valueDiff = [], qualityDiff = [], bandDiff = []
    for (const sa of a) {
      const sb = b.find((x) => x.indicator === sa.indicator)
      for (const da of sa.days) {
        const db = sb?.days.find((x) => x.missionDay === da.missionDay)
        points++
        if ((da.value ?? null) !== (db?.value ?? null)) valueDiff.push(`${sa.indicator} d${da.missionDay}: ${da.value} vs ${db?.value}`)
        if (da.quality !== db?.quality) qualityDiff.push(`${sa.indicator} d${da.missionDay}: ${da.quality} vs ${db?.quality}`)
      }
      const ba = sa.baseline, bb = sb?.baseline
      if (JSON.stringify([ba?.low, ba?.median, ba?.high, ba?.fromDay, ba?.toDay]) !== JSON.stringify([bb?.low, bb?.median, bb?.high, bb?.fromDay, bb?.toDay]))
        bandDiff.push(`${sa.indicator}: ${ba ? `${ba.low}-${ba.high} (d${ba.fromDay}-${ba.toDay})` : 'none'} vs ${bb ? `${bb.low}-${bb.high} (d${bb.fromDay}-${bb.toDay})` : 'none'}`)
    }
    const sel = (series, ind, d) => series.find((s) => s.indicator === ind)?.days.find((x) => x.missionDay === d)?.value
    const table = DAYS.map((d) => `d${d}: HR ${sel(a, 'resting_hr', d)}/${sel(b, 'resting_hr', d)} HRV ${sel(a, 'hrv_rmssd', d)}/${sel(b, 'hrv_rmssd', d)} sleep ${sel(a, 'sleep_duration', d)}/${sel(b, 'sleep_duration', d)}`).join(' | ')
    // Nutrition per mission day: total energy and fluid of the food log.
    let intakeDiff = []
    for (const d of DAYS) {
      const date = new Date(Date.parse('2026-10-31T00:00:00Z') + (d - 1) * 86_400_000).toISOString().slice(0, 10)
      const next = new Date(Date.parse(`${date}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10)
      const [ia, ib] = await Promise.all([mock.listIntake(crew, date, next), http.listIntake(crew, date, next)])
      const tot = (es, n, values) => Math.round(es.reduce((s, e) => s + ((values(e)[n]) ?? 0), 0))
      const ea = tot(ia, 'energy_intake', (e) => entryValues(e, foods)), eb = tot(ib, 'energy_intake', (e) => e.values)
      const fa = tot(ia, 'fluid_intake', (e) => entryValues(e, foods)), fb = tot(ib, 'fluid_intake', (e) => e.values)
      if (ea !== eb || fa !== fb || ia.length !== ib.length) intakeDiff.push(`d${d}: entries ${ia.length}/${ib.length} kcal ${ea}/${eb} mL ${fa}/${fb}`)
    }
    failures += valueDiff.length + intakeDiff.length
    console.log(`\n${crew}: ${points} plotted points, value differences ${valueDiff.length}, quality differences ${qualityDiff.length}, band differences ${bandDiff.length}, nutrition-day differences ${intakeDiff.length}`)
    console.log(`  ${table}`)
    for (const x of [...valueDiff, ...qualityDiff, ...bandDiff, ...intakeDiff].slice(0, 40)) console.log('   - ' + x)
  }
} finally {
  await server.close()
}
console.log(`\nVALUE/NUTRITION DIFFERENCES: ${failures}`)
process.exitCode = failures ? 1 : 0
