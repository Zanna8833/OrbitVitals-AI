# Mission presentation data seeder

This CLI populates a running local OrbitVitals API with **SYNTHETIC** histories and
actual computed scientific results. Every ingested measurement has canonical
`source="simulated"`, a reserved `sim-mission-v1-*` crew ID, a synthetic measurement
ID and a synthetic device ID. Display names, mission timeline, recording declarations,
targets and policies are fictional presentation inputs. No result is a clinically
validated assessment, NASA health standard, diagnosis or medical recommendation.

The current revision, **`dashboard-acquisition-v2`**, covers all 12 final React daily
physiological indicators. See the [coverage and integration matrix](synthetic-dashboard-coverage.md).
Start a **fresh dedicated API process** when replacing the earlier 498-record seed;
its generic vital acquisitions are deliberately incompatible with this revision.

## Quick start in Windows PowerShell

Use the Python environment that already runs the backend's requirements and tests.
In one terminal, start a dedicated single-worker presentation API:

```powershell
Set-Location -LiteralPath 'C:\Users\Andrea\Desktop\OrbitVitals AI\OrbitVitals-Codex-Exercise\backend'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, populate it:

```powershell
Set-Location -LiteralPath 'C:\Users\Andrea\Desktop\OrbitVitals AI\OrbitVitals-Codex-Exercise\backend'
python -m app.demo_seed seed --base-url 'http://127.0.0.1:8000/api/v1' --report '.\mission-demo-report.json'
```

The default console output is concise and explicitly simulated. The report contains
the complete returned baselines/evaluations, actual quality counts, the manifest and
expected-versus-actual checks. Add `--json` for JSON-only stdout. `--report` is optional;
the CLI writes no files unless that option is supplied. Diagnostics go to stderr.

Inspect the report and live API:

```powershell
$apiBase = 'http://127.0.0.1:8000/api/v1'
$seedReport = Get-Content -LiteralPath '.\mission-demo-report.json' -Raw | ConvertFrom-Json
$seedReport.all_checks_passed
$seedReport.crews | Select-Object crew_member_id, stored_measurement_count, quality_status_counts

Invoke-RestMethod "$apiBase/metrics" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$apiBase/crew-members/sim-mission-v1-01/evaluations" | ConvertTo-Json -Depth 30
Invoke-RestMethod "$apiBase/crew-members/sim-mission-v1-02/evaluations?domain=sleep" | ConvertTo-Json -Depth 30
Invoke-RestMethod "$apiBase/crew-members/sim-mission-v1-02/evaluations?domain=physical_activity" | ConvertTo-Json -Depth 30
Invoke-RestMethod "$apiBase/crew-members/sim-mission-v1-03/measurements?metric=blood_oxygen_saturation" | ConvertTo-Json -Depth 20
Invoke-RestMethod "$apiBase/crew-members/sim-mission-v1-01/baselines?metric=heart_rate" | ConvertTo-Json -Depth 20
```

Open `http://127.0.0.1:8000/docs` for interactive requests. There is no crew-creation
endpoint: canonical measurements establish each crew history, and the local manifest
maps IDs to fictional display names. No public contract or endpoint is added.

## Presentation manifest and profiles

[mission-demo-manifest.json](mission-demo-manifest.json) is the concise machine-readable
mapping of crew IDs, scenarios, HTTP paths, fixed dates, exact policies, input fingerprint
and separately authored expected behaviors. It contains no precomputed evaluation.
It can also be generated offline:

```powershell
python -m app.demo_seed manifest
```

| Synthetic crew | Presentation profile | Measurements | Expected demonstration |
| --- | --- | --- | --- |
| `sim-mission-v1-01`, SIMULATED Vega | Stable monitoring | 328 | Variable historical references, stable sleep, alternating exercise amounts, explicit rest and met personal targets; nominal screens mean no configured signal |
| `sim-mission-v1-02`, SIMULATED Noor | Declining sleep and activity | 311 | Early sleep insufficiency, later actual duration-reduction signals, decreasing activity, complete daily misses and incomplete later weekly adherence |
| `sim-mission-v1-03`, SIMULATED Chen | Sensor failures and missing data | 254 | Mathematical definition violations, a redundant sleep copy, vital telemetry gaps, a known activity subtotal without completeness, and later insufficient evaluations |

The standard run loads **893 measurements**, computes **36 baselines** (12 per crew),
and requests **13 sleep/activity evaluations**. The current default API returns seven
unusable measurements for the telemetry profile. These are observed results checked
in tests; the seeder does not assign engine statuses, statistics, quality scores or
baseline/evaluation IDs.

The telemetry profile's seven-night sleep screen can be nominal after unusable records
are excluded: the remaining usable values pass the configured sufficiency gates and
have no configured statistical signal. This does not cancel the quality failures or
establish healthy sleep. The longer window fails coverage/missing-run gates and is
insufficient. Keep data quality, recording completeness and physiological screening
labels separate during the presentation.

## Fixed dates and measurement protocol

- Historical recording dates are `2026-09-28` through `2026-10-11`.
- Current recording dates are `2026-10-12` through `2026-10-25`.
- Every baseline uses a prior historical window and is computed at
  `2026-10-12T12:00:00Z`. Sleep reference buckets begin/end at 12:00 UTC; activity and
  vital reference dates use UTC midnight boundaries.
- The latest requested evaluation horizon is `2026-10-26T12:00:00Z`. The server clock
  must be at or after that instant. The CLI checks the health timestamp before writes.
  Dates are not silently moved to the current day.
- Sleep observations start at 22:00 UTC inside nine-hour recording envelopes. These
  envelopes are not an assertion of nine hours spent in bed. Duration and efficiency
  are independently authored canonical measurements; no missing metric or time-in-bed
  value is reconstructed.
- Exercise sessions run inside 09:00–10:00 UTC recording intervals. Active kcal values
  are independently authored, never estimated from minutes. Rest days are explicit
  workflow declarations; complete empty rest dates can represent zero. Unconfirmed
  empty dates remain unknown.
- The new fictional acquisition schedule declares waking at 07:00 UTC, followed by
  five minutes of seated quiet rest. Heart rate (`bpm`), respiratory rate (`breaths/min`)
  and SpO2 (`%`) are spot records at 07:05. This supports resting/post-waking labels by
  explicit generation intent, not by inference from their values or timestamps.
- RMSSD (`ms`) is an authored scalar for a simulated resting PPG interval 07:00-07:05;
  no beat intervals, waveform processing or validated HRV estimation are claimed.
  A seated cuff pair (`mmHg`) and an oral temperature spot check (`degC`) occur at
  07:10. Daily mass (`kg`) is captured at 07:15. These precede 09:00 exercise.
- These are synthetic schedule assumptions, not evidence of actual waking, posture,
  calibrated devices or flight feasibility. Missing sleep records stay missing;
  no wake time, sleep duration or other observation is reconstructed from this schedule.
- The existing measurement contract has no context field. Each generated morning
  vital/mass record carries a stable `device_id` protocol key, resolved in the
  manifest's `acquisition.protocols` ledger. It is a seeder convention, not a new
  API field or a claim that the frontend enforces acquisition-context compatibility.
- All 12 metrics support real quality assessments and personal baselines. The API
  evaluates only sleep and physical activity; no vital, nutrition or cognition
  evaluation is fabricated or requested.

The fictional timeline is one in-flight phase covering these windows. The same device
and protocol are declared within each crew's reference/current data, permitting the
explicit activity-baseline compatibility confirmation. This is a controlled fixture
assumption, not evidence of a spaceflight calibration or physiological dynamics model.

## Fixture reuse and additional authored inputs

The seeder imports the existing `app.scenarios.fixtures` factories and policies. It
does not copy scientific estimators or import scenario replay results:

| Existing fixture | Reuse |
| --- | --- |
| `simulated_measurement` | Canonical source, units and original unassessed measurement construction |
| `sleep_records` | Paired primary summaries and explicit omissions |
| `restriction_records` | Noor's nine-night reduction sequence and two absent nights, unchanged values |
| `sensor_failure_records` | Chen's seven-night negative duration, invalid efficiency and distinct-ID duplicate, unchanged values |
| `activity_inputs` | Noor's complete 14-day activity/rest/partial/missing sequence and the explicit personal plans used for all profiles |
| `baseline_inputs` | The authored pre-flight/in-flight heart-rate sequences, reused as fictional reference/current patterns |
| `sleep_policy`, `baseline_policy` | Exact existing demonstration settings, recorded in the manifest and submitted commands |

Existing fixture files are unchanged. Crew IDs, device IDs, session links and timestamps
are remapped consistently into this dataset's reserved namespace and historical UTC
windows. An existing duplicate remains a distinct ID for the same observation.

Additional authored inputs are engineering presentation choices documented here:

- Reference sleep duration repeats `(475,480,485,480,475,485,480)` min twice; efficiency
  repeats `(91,92,93,92,91,93,92)` percent. Vega's current values are 480 min and 92%.
- Complete reference activity and Vega's current activity repeat
  `(50,55,50,55,50,0,55)` min and independent `(220,250,230,260,240,0,250)` kcal cycles.
  Offsets 5 and 12 are scheduled rest, with no additive records and confirmed coverage.
  Alternation avoids scripting a progressive reduction into the stable profile.
- Chen has a 30-min current activity subtotal on offset 0, injected -10-min/-50-kcal
  corrupted records on offset 6, and no complete current activity confirmations.
- Reference heart-rate values use the existing pre-flight sequence with crew offsets
  of 0, 4 and 8 bpm. Noor/Chen current values use the existing in-flight sequence. Its
  negative corruption is replaced by 64 before the crew offset only for Noor; Chen
  retains the negative value as a deliberate failure.
- Respiratory values repeat `(12,13,14,13,12,14,13)` with crew offsets 0, 1 and 2.
  Oxygen percentages repeat `(98,97,99,98,97,99,98)`. Chen omits current vital dates
  at offsets 2, 6, 10, 11 and 12, and has an injected 125% decoder failure at offset 4.
- Stable/telemetry sleep checkpoints are 7 and 14 complete operational nights;
  restriction checkpoints reuse 2, 5 and 9 nights. Activity checkpoints are 7 and 14 days.

The five added dashboard sequences are authored in `_dashboard_measurements`:

| Input | Repeated seven-day pattern | Profile variation |
| --- | --- | --- |
| RMSSD, ms | `(54,56,55,57,53,58,55)` | Subtract 4 times crew index; Noor's current pattern additionally subtracts 0.5 times current day offset. |
| Systolic, mmHg | `(116,118,117,119,115,120,117)` | Add 3 times crew index; Noor's current pattern adds integer day offset divided by 4. |
| Diastolic, mmHg | `(74,75,73,76,74,77,75)` | Add 2 times crew index; Noor's current pattern adds integer day offset divided by 6. |
| Oral temperature, degC | `(36.6,36.7,36.5,36.6,36.8,36.7,36.6)` | No crew or trend adjustment. |
| Body mass, kg | `(72.0,72.1,71.9,72.2,72.0,71.8,72.1)` | Add 4 times crew index. |

Crew index is 0/1/2 for Vega/Noor/Chen. Values are rounded to two decimals. Each
new metric has 28 records for Vega/Noor and 23 for Chen: the same five current
vital dates remain absent, including both cuff channels together. Every reference
has 14 variable samples, allowing the existing baseline policy to run. Systolic
exceeds diastolic by construction as a coherence condition, not a clinical limit.
The authored trends imply no causal association, disease, fatigue or diagnosis.

These sequences are not sampling from a validated distribution. No vital-range
health interpretation or cross-metric physiological correlation is claimed.

## Policies and real API execution

The explicit existing sleep policy uses four included nights, coverage 0.6, three
elapsed days, at most two consecutive missing nights, decreasing fraction 0.75 and
a 12:00 UTC boundary. Duration gates are 5 min/day, 30 min fitted change and 60 min
reference deviation; efficiency gates are 0.5 percentage points/day, 3 fitted points
and 5 reference-deviation points. These are documented demonstration choices only.

The reused establishment criterion is ten samples spanning nine elapsed days, with
the existing arithmetic minimum and report/keep outlier policy. The seeder submits
its synthetic documentary `policy_source`. Reference activity is aggregated to complete
active-day totals by the existing API, rather than comparing session means with daily
totals. Neither reference statistics nor establishment status are assigned by the CLI.

Activity plans reuse 40 min/200 kcal daily minimums and 240 min/1200 kcal weekly
minimums, with the existing reduction-run convention. No baseline-deviation tolerance
is invented; selected prior baselines can supply descriptive deviations. The recording
confirmations and rest calendar are passed explicitly. Do not reuse these presentation
inputs as mission exercise prescriptions.

The client reads health, metric catalog and reserved crew histories first. It then:

1. POSTs raw canonical records through `/api/v1/measurements`, allowing the real engine
   to assign quality. Default batch size 500 splits the 893-record revision into two batches;
   `--batch-size` accepts 1 through the existing API maximum of 1000.
2. Completes every ingestion batch before generating any derived results.
3. POSTs each historical baseline command through the existing crew baseline endpoint.
4. Fills evaluation `baseline_ids` only from those actual API responses, and POSTs the
   explicit sleep/activity commands with fixed windows, policies and computation times.
5. GETs all crew measurements, baselines and evaluations to verify identity, simulation
   labels, algorithm provenance and retention of the computed snapshots.

No repository, service or scientific engine is invoked directly by the seeder.
Existing Pydantic command/resource models validate its JSON. No new API contract,
shared schema, estimator, frontend code or Marco module is introduced or changed.

The CLI leaves server quality configuration intact. Default API settings have no
invented device bounds or sampling cadence. Missing sleep nights remain visible in
the sleep module's selection diagnostics; timestamp-presence completeness is not
fabricated where no cadence is configured. Custom server quality settings may change
actual outcomes. The report preserves those outcomes and separately fails a mismatched
presentation expectation.

## Idempotence, reset and errors

All input IDs, measurement values, UTC dates, policies, command order and computation
horizons are fixed. No random generator, local timezone, current-day date shifting or
client-generated result ID is used. The manifest fingerprints the complete input plan.
For the same backend/configuration, rerunning the command uses the API's idempotent
measurement handling and deterministic computed snapshots: there are still 893
measurements, 36 baselines and 13 evaluations. Server-assigned ingestion assessment
timestamps can differ after a restart; fixed-horizon scientific results and the report
remain reproducible. Unrelated crew records are preserved.

The preflight refuses unexpected/conflicting measurements in reserved crew histories
before writes. A global ID conflict is also protected by the API's atomic `409`.
There is no transaction spanning all HTTP commands: a failure after an earlier command
can leave a partial seed. Correct the connection issue and rerun; identical data resumes
safely. Changing fixture values, policies or server quality settings calls for a clean
dedicated presentation instance.

The earlier seed had 498 measurements and 21 baselines. This revision adds 395
records and 15 baseline requests. Original crew identities, vital values/IDs,
all sleep/activity inputs and their policies remain intact. Only newly generated
legacy vital acquisition timestamps (08:00 to 07:05) and device protocol IDs change
to make context explicit. An existing generic record is rejected before any POST;
the seeder never updates, deletes or retrospectively labels it as resting.

All 13 original scientific evaluation payloads are regression-checked unchanged
except `evaluation_id`. The integration service includes the entire crew history
in that identity, so added records legitimately change IDs. Rerunning this same
revision remains idempotent. Ingest all batches before computing snapshots; the
existing API invalidates overlapping results when new records arrive.

To reset the dedicated in-memory API, press **Ctrl+C in its server terminal**, then run
the same Uvicorn command and seed again. Restarting clears all records in that process;
keep other work in a separate API instance. The CLI provides no reset endpoint and
does not delete records.

Exit codes are `0` for a completed seed with all checks passing, `1` for completed
seeding with actual/expected behavior differences, and `2` for invalid usage,
connection errors, incompatible contracts/catalog, namespace conflicts or report-write
errors. A mismatch prints/preserves the real outputs; it never changes a result to
match an expectation. Targets must be loopback HTTP(S) URLs ending in `/api/v1`.

## Verification

```powershell
python -m pytest tests/demo_seed -q
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
python -m scripts.audit_nasa_history
```

Tests cover source labels, units and committed schemas; scenario/policy reuse;
reproducibility across processes/timezones and API restarts; identity, batching and
idempotence; conflict/clock/catalog preflight; CLI output, reports and failures;
and a real HTTP smoke test that launches an isolated Uvicorn process, executes the CLI
twice, retrieves every collection, and stops only its own server process. A counterexample
changes the fixture inputs and verifies that changed real algorithm outputs remain
visible rather than being overwritten by presentation expectations.
