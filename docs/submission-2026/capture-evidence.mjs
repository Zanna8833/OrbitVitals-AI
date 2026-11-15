import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  buildNoorReplay,
  createOrbitVitalsClient,
  loadDemoMission,
} from '../../integrations/frontend-bridge/dist/index.js'

// Capture real contract payloads. This is documentation tooling, not a new API or algorithm.
const repoRoot = fileURLToPath(new URL('../../', import.meta.url))
const branch = execFileSync('git', ['branch', '--show-current'], {
  cwd: repoRoot,
  encoding: 'utf8',
}).trim()
assert.equal(
  branch,
  'feature/frontend-bridge',
  'Evidence must be captured in the authorized branch',
)
const commit = execFileSync('git', ['rev-parse', 'HEAD'], {
  cwd: repoRoot,
  encoding: 'utf8',
}).trim()
const output = new URL('./evidence/', import.meta.url)
const digest = (value) => createHash('sha256').update(value).digest('hex')

// The existing test helper expects frontend/ as its process working directory.
process.chdir(path.join(repoRoot, 'frontend'))
const { startApi, seedApi } = await import('../../frontend/tests/api-process.ts')
const server = await startApi()
try {
  assert.notEqual(new URL(server.baseUrl).port, '8000')
  const seeded = await seedApi(server.baseUrl)
  assert.equal(seeded.all_checks_passed, true)
  const crews = await loadDemoMission(createOrbitVitalsClient({ baseUrl: server.baseUrl }))
  for (const crew of crews) {
    assert.ok(crew.measurements.every((record) => record.source === 'simulated'))
    const seed = seeded.crews.find((row) => row.crew_member_id === crew.crew.id)
    for (const { result } of seed.evaluations) {
      assert.deepEqual(
        [...crew.sleepEvaluations, ...crew.activityEvaluations].find(
          (row) => row.evaluation_id === result.evaluation_id,
        ),
        result,
      )
    }
  }
  const noor = crews.find((crew) => crew.crew.id === 'sim-mission-v1-02')
  assert.ok(noor, 'The actual Noor collection is required')
  const steps = buildNoorReplay(noor)
  const evaluations = steps.map((step) => {
    assert.ok(step.evaluation, 'Every replay checkpoint must be stored')
    return step.evaluation
  })
  const baselineIds = new Set(
    evaluations.flatMap((result) =>
      result.findings
        .filter((finding) => finding.metric === 'sleep_duration')
        .map((finding) => finding.baseline_id),
    ),
  )
  const baselines = noor.baselines.filter((baseline) => baselineIds.has(baseline.baseline_id))
  const measurements = noor.measurements.filter((record) => record.metric === 'sleep_duration')
  await mkdir(output, { recursive: true })
  const files = {}
  async function save(name, value) {
    const text = JSON.stringify(value, null, 2) + '\n'
    await writeFile(new URL(name, output), text, 'utf8')
    files[name] = { sha256: digest(text), bytes: Buffer.byteLength(text) }
  }
  await save('noor-sleep-evaluations.json', { items: evaluations })
  await save('noor-sleep-baselines.json', { items: baselines })
  await save('noor-sleep-duration-measurements.json', { items: measurements })
  const last = steps.at(-1)
  const csv =
    'night_bucket_start_utc,observed_value_min,record_state\n' +
    last.duration.chart
      .map((point) => `${point.time},${point.value ?? ''},${point.kind}`)
      .join('\n') +
    '\n'
  await writeFile(new URL('noor-nine-night-observations.csv', output), csv, 'utf8')
  files['noor-nine-night-observations.csv'] = { sha256: digest(csv), bytes: Buffer.byteLength(csv) }
  const referenceIndex = process.argv.indexOf('--reference')
  const reference = referenceIndex >= 0 ? await readFile(process.argv[referenceIndex + 1]) : null
  const metadata = {
    artifact_kind: 'submission_evidence_manifest_not_an_api_contract',
    data_kind: 'simulated',
    review_date: '2026-11-15',
    captured_at_utc: new Date().toISOString(),
    source_commit: commit,
    branch,
    capture_command: 'node --experimental-strip-types docs/submission-2026/capture-evidence.mjs',
    api_mode: 'owned_ephemeral_loopback_fastapi',
    shared_port_8000_used: false,
    server_settings: {
      source: 'integrations/frontend-bridge/tests/server.py',
      env_file_loaded: false,
      data_quality_expected_intervals: {},
      sensor_ranges_configured: false,
      sleep_policy_source:
        'existing mission seeder; actual policy preserved in evaluation summaries',
    },
    seed_checks_passed: seeded.all_checks_passed,
    crew_resources: crews.map((crew) => ({
      crew_member_id: crew.crew.id,
      measurements: crew.measurements.length,
      baselines: crew.baselines.length,
      evaluations: crew.sleepEvaluations.length + crew.activityEvaluations.length,
    })),
    noor_checkpoints: steps.map((step) => ({
      checkpoint: step.checkpointId,
      window_end: step.windowEnd,
      evaluation_id: step.evaluation.evaluation_id,
      result_status: step.evaluation.status,
      included_nights_for_display: step.duration.chart.filter((point) => point.value !== null)
        .length,
      expected_nights_for_display: step.duration.chart.length,
      note: 'Night counts are bridge display diagnostics, not API Data Quality completeness.',
    })),
    approved_reference: {
      filename: 'OrbitVitals_Demo (6).html',
      sha256: reference ? digest(reference) : null,
      visual_acceptance: 'not_run',
    },
    ai_assistance:
      'OpenAI Codex assisted this capture script and submission text. The existing deterministic synthetic fixtures and code were developed in an AI-assisted workflow. Full team disclosures are recorded separately; no astronaut data or generated media are created by this capture.',
    files,
  }
  await writeFile(
    new URL('capture-manifest.json', output),
    JSON.stringify(metadata, null, 2) + '\n',
    'utf8',
  )
  console.log(
    JSON.stringify(
      {
        captured: Object.keys(files),
        seed_checks_passed: metadata.seed_checks_passed,
        checkpoints: metadata.noor_checkpoints,
        visual_acceptance: 'not_run',
      },
      null,
      2,
    ),
  )
} finally {
  await server.stop()
}
