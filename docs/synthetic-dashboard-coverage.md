# Synthetic backend coverage for the final React dashboard

Reviewed frontend: `origin/main` at `14125559a1a1b64c54ec86214d858296a73075a8`.
Seed revision: **`dashboard-acquisition-v2`**, in the existing mission-demo namespace.
This is deterministic engineering demonstration data, not a physiological simulator
or a validated assessment. No NASA original, participant export or authentic
observation enters generation, ingestion, baselines or the synthetic crew charts.

Mapping sources are [metricCatalog.ts](../frontend/src/domain/metricCatalog.ts),
[parameters.ts](../frontend/src/domain/parameters.ts) and
[BackendDataSource.ts](../frontend/src/data/backend/BackendDataSource.ts).
The backend [catalog](../backend/app/models/metrics.py) remains authoritative for units.
Neither frontend, agent, shared contracts nor scientific algorithms are changed.

## Daily physiological indicators

Counts are raw records for **Vega / Noor / Chen**, including retained corrupt or
duplicate records. They are not usable-day counts. Reference dates are September
28-October 11, 2026; current dates are October 12-25. **B** means a real established
backend personal baseline for each crew, using the unchanged demo policy.

| Frontend indicator | Backend metric | Canonical unit -> display | Records A/B/C | Acquisition / daily display | Quality treatment | Baseline / evaluation |
| --- | --- | --- | --- | --- | --- | --- |
| `resting_hr` | `heart_rate` | bpm | 28 / 28 / 23 | 07:05 seated resting spot check after declared 07:00 waking; median | Original negative decoder records remain unusable; gaps retained | B; no vital evaluation |
| `hrv_rmssd` | `heart_rate_variability_rmssd` | ms -> ms RMSSD | 28 / 28 / 23 | 07:00-07:05 resting PPG context; authored scalar, daily median | Existing engine, no configured sensor limits; gaps retained | B; no vital evaluation |
| `resting_resp_rate` | `respiratory_rate` | breaths/min | 28 / 28 / 23 | 07:05 seated resting spot check; median | Existing engine; gaps retained | B; no vital evaluation |
| `resting_spo2` | `blood_oxygen_saturation` | % | 28 / 28 / 23 | 07:05 seated optical spot check; median | Original 125% decoder failure remains unusable; gaps retained | B; no vital evaluation |
| `body_temperature` | `body_temperature` | degC -> degrees C | 28 / 28 / 23 | 07:10 oral spot check; median, no core-temperature claim | Existing engine; gaps retained | B; no vital evaluation |
| `bp_systolic` | `systolic_blood_pressure` | mmHg | 28 / 28 / 23 | 07:10 seated cuff; median | Same instant/device as diastolic; no clinical cutoff | B; no vital evaluation |
| `bp_diastolic` | `diastolic_blood_pressure` | mmHg | 28 / 28 / 23 | Same cuff pair; median | Pair consistency checked by the existing engine; both absent together | B; no vital evaluation |
| `sleep_duration` | `sleep_duration` | min -> h (divide by 60) | 28 / 21 / 22 | Existing overnight intervals; sum assigned to interval-end date | Original negative/duplicate records, Noor's two gaps and Chen's later missing nights retained | B; existing sleep evaluation |
| `sleep_efficiency` | `sleep_efficiency` | % | 28 / 21 / 21 | Existing overnight summaries; median assigned to interval-end date | Original invalid percentage and all missing nights retained | B; existing sleep evaluation |
| `activity_minutes` | `exercise_duration` | min | 24 / 23 / 14 | Existing 09:00-10:00 session records; sum | Rest declarations, unconfirmed coverage and corrupt duration retained | B on complete active-day totals; existing activity evaluation |
| `active_energy` | `active_energy_expenditure` | kcal | 24 / 22 / 13 | Independent existing session-energy inputs; sum | Missing energy is not inferred from minutes or fabricated as zero | B on complete active-day totals; existing activity evaluation |
| `body_mass` | `body_mass` | kg | 28 / 28 / 23 | 07:15 morning mass check; last observation of date | Existing engine; no spacecraft instrument or hydration claim | B; no nutrition evaluation |

Each added metric contributes **28 / 28 / 23** records. The original **498** records
become **893** (328 / 311 / 254), and baseline requests increase from 21 to **36**.
The same **13** sleep/activity evaluations are genuinely computed. Exact original
domain inputs, commands, reference commands and scientific result payloads are
regression-pinned. Only evaluation IDs change because the existing integration
service fingerprints the entire crew history. No findings are preassigned.

## Context, missingness and quality boundaries

The [manifest](mission-demo-manifest.json) includes protocol definitions, stable
device-key resolution, counts, policies and the input-plan digest. The measurement
contract has no acquisition-context field. The seeder encodes a protocol key in
`device_id`, with the authored interpretation in `acquisition.protocols`. This
does not add an API contract or verify real-world posture, waking or modality.
It also cannot make the frontend filter arbitrary user-imported contexts.

Newly generated HR/RR/SpO2 preserve their IDs and values but use 07:05 and explicit
resting devices instead of generic 08:00 acquisitions. The fictional waking
schedule is explicit; it is not reconstructed from sleep efficiency/duration.
Existing sleep recording envelopes stay unchanged. Missing sleep does not imply
an actual wake observation. New cuff channels share crew, source, timestamp,
interval and device so the real engine can assess pair consistency.

Chen omits all eight morning metric captures at current offsets 2, 6, 10, 11 and
12 (October 14, 18, 22, 23 and 24). No observations are interpolated. The seven
original unusable records remain; evaluation-level degraded/insufficient states
remain distinct from record quality and physiological screening. Default device
ranges and expected cadence remain unconfigured, so completeness and score are
not manufactured. Acceptable quality does not mean medically normal.

The frontend maps acceptable/degraded/unusable/unassessed to good/uncertain/poor/
uncertain. It excludes unusable values from daily summaries, retains poor/null
days, and fills absent daily points with null/missing. Its activity chart does
not consume backend rest/coverage declarations: an explicitly planned rest day
with no stored measurement remains a chart gap, while the existing activity
evaluation can interpret confirmed rest. The seeder does not insert fake zeros
to hide this distinction. Missing energy stays missing even when duration exists.

The frontend derives display bands from backend median/MAD and its own minimum
margins, and can compute local fallback bands. Those bands, headings and any
frontend comparison are not backend vital evaluations or clinical thresholds.
This seed supplies established backend references for all 12 metrics; the
evaluation API still supports only sleep and physical activity.

## Other final frontend surfaces

| Surface | Backend / seed coverage | Boundary |
| --- | --- | --- |
| Nutrient food/intake log: energy, protein, fluid, vitamins A/C/D/K/B12, folate, calcium, phosphorus, sodium, potassium, iron, magnesium, zinc | All 16 intake metrics are catalog-supported and HTTP-readable; not populated by this physiological-trend revision | Logged consumption is a separate user-input workflow. No invented dietary prescription, intake history, hydration status or nutrition evaluation. |
| Live traces: HR, SpO2, respiration and motion | Existing frontend `getSeries` remains inherited local demonstration behavior; no backend motion metric or waveform route | Daily backend coverage does not establish live sensor streaming. |
| Mission/activity timeline, messages, review events, check-ins, sleep plan and profiles | Existing local/mock behavior remains | No new backend persistence or workflow is claimed. |
| Cognition battery and results | Separate frontend battery; no supported backend cognition measurement/evaluation contract | No synthetic cognitive assessment is fabricated. |
| NASA context and assistant | Existing separate pipelines/agent preserved | No NASA participant measurements or generated AI values become crew telemetry. |

All **12 daily physiological** series now have backend records. The separate
surfaces above are explicitly outside that coverage, rather than silently filled
with unrelated physiological readings.

## Run and inspect

Use a fresh, dedicated single-worker API; an already populated generic v1 API
fails preflight without writes. Stop only your own presentation server with
Ctrl+C and restart it if needed. Shared servers are not reset by this tool.
From the Exercise worktree, with the backend development environment active:

```powershell
Set-Location -LiteralPath 'C:\Users\Andrea\Desktop\OrbitVitals AI\OrbitVitals-Codex-Exercise\backend'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell terminal with the same environment and directory:

```powershell
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1'
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1'
$apiBase = 'http://127.0.0.1:8000/api/v1'
$metricNames = 'heart_rate_variability_rmssd','systolic_blood_pressure','diastolic_blood_pressure','body_temperature','body_mass'
foreach ($crewIndex in 1..3) {
    $crewId = 'sim-mission-v1-{0:00}' -f $crewIndex
    foreach ($metricName in $metricNames) {
        $records = Invoke-RestMethod "$apiBase/crew-members/$crewId/measurements?metric=$metricName"
        $records.items | Select-Object measurement_id,metric,value,unit,measured_at,interval_end,source,device_id
        Invoke-RestMethod "$apiBase/crew-members/$crewId/baselines?metric=$metricName" | ConvertTo-Json -Depth 20
    }
}
```

The existing frontend defaults map Crew A/B/C to these same backend IDs. Its
HTTP clock derives from the latest stored measurement; the fixed seed is not
moved to today's date. Optional presentation settings are
`VITE_MISSION_START=2026-09-28` and `VITE_AS_OF=2026-10-25T20:00:00Z`; these are
configuration instructions, not frontend edits.

The last stored sleep interval starts October 25 and ends October 26 at 07:00.
Because sleep is displayed on its interval-end date, that final point falls
outside the default October 25 view. Choosing October 26 as the display date
reveals it and correctly shows absent October 26 morning captures; it does not
authorize filling those gaps. Stored availability and current-screen visibility
are different questions.

## Publication safeguards

Fetched main introduced four explicitly invented frontend sample CSV paths that
the unchanged history audit rejected. The authorized supporting fix adds only
their exact, case-sensitive path/digest pairs to the existing pinned mechanism.
Each path had one historical byte version, introduced in
`13660fab606f3430f344be092f030f8a00c1fbcb`; both source headers and the frontend
contract identify invented examples. No sample is modified or copied.

| Paths under `frontend/` | Approved exact Git-blob SHA-256 |
| --- | --- |
| `docs/samples/measurements.sample.csv`, `src/data/import/samples/measurements.sample.csv` | `da572991538502aa682bd075fe6bd5857733633f28f55b3568cba1352b833ec6` |
| `docs/samples/measurements-long.sample.csv`, `src/data/import/samples/measurements-long.sample.csv` | `dbad79029a53e441c6d6b7fca86744920866612757a09a35269f73db48be9455` |

Every historical version is still checked without newline normalization. Changed
content, restoration after changes, aliases, swapped formats and CRLF variants
fail. Source names/digests, NASA exports and private caches remain forbidden,
including at approved synthetic paths. The original Noor exception stays intact.
Original NASA bytes and individual derivatives remain local and excluded.

## Verification record

Final backend verification on November 15, 2026:

- `python -m pytest -q`: **1,082 passed** in 64.11 seconds. This includes the
  expanded socket HTTP smoke test: start an isolated Uvicorn server, seed twice,
  compare complete reports, GET every crew collection and GET each new metric's
  exact records, metadata and real engine quality. The test stops only its own server.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: **140 files** already formatted.
- `python -m scripts.export_schemas --check`: shared schemas up to date.
- `python -m scripts.audit_nasa_history`: passed on the pre-commit base history,
  **47 commits, 44 trees, 813 blobs, zero violations**. The committed branch is
  audited again after the local commit; final counts are reported with delivery.
- Offline manifest equality, per-metric counts, acquisition fingerprint, seven
  local documentation links and source-exclusion/scope checks passed.

The original 13 scientific evaluation payloads match their pre-change hashes
after excluding only `evaluation_id`. Existing sleep/activity input and command
hashes also match. The new records receive actual baseline/quality computations;
no vital/nutrition evaluation was introduced. Software tests and synthetic
demonstration behavior establish no clinical validity or flight qualification.
