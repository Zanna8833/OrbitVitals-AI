// Exports the synthetic observations of Silvio's approved frontend scenario, computed by
// the unchanged frontend generators (frontend/src/data/mock), as backend measurements.
//
// Run from the repository root:  node integrations/approved-demo/export_observations.mjs
// Output: backend/app/demo_seed/approved_observations.json (SIMULATED data only).
//
// The mapping from a daily value to a backend measurement is the frontend's own
// BackendDataSource.importDaily/addIntake mapping; nothing is recomputed or adjusted here.
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createRequire } from 'node:module'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const frontend = path.join(root, 'frontend')
const { createServer } = createRequire(path.join(frontend, 'package.json'))('vite')

// The generators read optional browser storage; an empty in-memory store keeps the defaults.
const memory = new Map()
globalThis.localStorage = {
  getItem: (k) => (memory.has(k) ? memory.get(k) : null),
  setItem: (k, v) => memory.set(k, String(v)),
  removeItem: (k) => memory.delete(k),
  clear: () => memory.clear(),
}
globalThis.window = globalThis

const server = await createServer({ root: frontend, configFile: false, logLevel: 'error', server: { middlewareMode: true, hmr: false }, appType: 'custom' })
try {
  const load = (p) => server.ssrLoadModule(p)
  const { MockDataSource } = await load('/src/data/mock/MockDataSource.ts')
  const { DEFAULT_SCENARIO_ID } = await load('/src/data/mock/scenarios.ts')
  const { fixedClock } = await load('/src/data/mock/clock.ts')
  const { INDICATOR_METRIC, NUTRIENT_UNIT } = await load('/src/domain/metricCatalog.ts')
  const { NUTRIENTS, entryValues } = await load('/src/domain/nutrition.ts')

  const ds = new MockDataSource(DEFAULT_SCENARIO_ID, 0, fixedClock, true)
  const crewMap = { 'crew-a': 'sim-mission-v1-01', 'crew-b': 'sim-mission-v1-02', 'crew-c': 'sim-mission-v1-03' }
  const status = await ds.getMissionStatus()
  const foods = await ds.listFoods()
  const measurements = []
  const daily = {}
  for (const crew of await ds.listCrew()) {
    const id = crewMap[crew.id]
    if (!id) continue
    daily[id] = {}
    for (const s of await ds.getDailyIndicators(crew.id)) {
      const map = INDICATOR_METRIC[s.indicator]
      const isSleep = map.metric === 'sleep_duration' || map.metric === 'sleep_efficiency'
      daily[id][s.indicator] = s.days.map((d) => ({ date: d.date, mission_day: d.missionDay, value: d.value, quality: d.quality }))
      for (const d of s.days) {
        if (d.value === null || d.quality === 'missing') continue
        const end = `${d.date}T07:00:00Z`
        const minutes = s.indicator === 'sleep_duration' ? d.value * 60 : 480
        measurements.push({
          measurement_id: `approved-${id}-${s.indicator}-${d.date}`,
          crew_member_id: id,
          metric: map.metric,
          unit: map.unit,
          value: Number((d.value / map.factor).toFixed(4)),
          measured_at: isSleep ? new Date(Date.parse(end) - minutes * 60_000).toISOString().replace('.000Z', 'Z') : `${d.date}T08:00:00Z`,
          interval_end: isSleep ? end : null,
          source: 'simulated',
          device_id: 'orbitvitals-approved-demo-v1',
        })
      }
    }
    for (const entry of await ds.listIntake(crew.id, '0000', '9999')) {
      const values = entryValues(entry, foods)
      for (const n of NUTRIENTS) {
        const v = values[n.id]
        if (v === null || v === undefined || !(v > 0)) continue
        measurements.push({
          measurement_id: `approved-${entry.id}~${n.id}`.slice(0, 128),
          crew_member_id: id,
          metric: n.id,
          unit: NUTRIENT_UNIT[n.id],
          value: Number(v.toFixed(3)),
          measured_at: entry.eatenAt,
          interval_end: null,
          source: 'simulated',
          device_id: 'orbitvitals-approved-demo-v1',
        })
      }
    }
  }
  const out = {
    dataset: 'orbitvitals-approved-frontend-demo-v1',
    notice: 'SIMULATED data from the approved frontend scenario generators; not astronaut records, not clinical data.',
    generator: { scenario: DEFAULT_SCENARIO_ID, now: status.now, mission_start: status.missionStartDate },
    daily_reference: daily,
    measurements,
  }
  writeFileSync(path.join(root, 'backend/app/demo_seed/approved_observations.json'), JSON.stringify(out, null, 1) + '\n')
  console.log(`now=${status.now} start=${status.missionStartDate} measurements=${measurements.length}`)
} finally {
  await server.close()
}
