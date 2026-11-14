# Sleep monitoring through HTTP

This **SIMULATED** demonstration uses the existing FastAPI server, Data Quality Engine,
Personal Baseline Engine and Sleep Monitoring module. The client never calls scientific
engines locally or constructs evaluation results. All results come from HTTP responses.
Its explicit policies exercise the prototype; they are not clinical thresholds, medical
recommendations, validated establishment criteria or NASA mission settings.

## Exact PowerShell commands

Use the existing Python 3.11 environment with the repository requirements installed.
An existing single-worker API on port 8000 can be used without restarting it:

```powershell
Set-Location "C:\Users\Andrea\Desktop\OrbitVitals AI\OrbitVitals-Codex\backend"
python -m scripts.demo_sleep_http --base-url "http://127.0.0.1:8000/api/v1" --namespace "v1" --validate
```

If a server is not already running, start it in a separate PowerShell terminal:

```powershell
Set-Location "C:\Users\Andrea\Desktop\OrbitVitals AI\OrbitVitals-Codex\backend"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

The demo accepts local HTTP(S) base URLs ending in `/api/v1`; change the port as needed.
`--validate` uses the existing pinned `jsonschema` development dependency. No new
dependency is required. The script prints a compact JSON summary and returns `0` when
all comparisons pass, `1` for a behavioral/content mismatch, or `2` for an HTTP,
validation or namespace error. Errors use stderr. No files or server configuration
are written by the client.

Capture exact request/response bodies, including server-generated IDs, as objects:

```powershell
$sleepHttpFull = python -m scripts.demo_sleep_http `
    --base-url "http://127.0.0.1:8000/api/v1" --namespace "v1" --full --validate |
    ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Sleep HTTP demonstration failed." }
$sleepHttpRestriction = $sleepHttpFull.cases | Where-Object { $_.case_id -eq "restriction" }
$sleepHttpRestriction.evaluation_request | ConvertTo-Json -Depth 30
$sleepHttpRestriction.evaluation_response | ConvertTo-Json -Depth 40
$sleepHttpRestriction.checks |
    Where-Object { $_.name -eq "stored_evaluation_matches" } |
    Select-Object name, passed
```

`http_exchanges` in the full output contains every method, path, request body, status
code and unmodified JSON response. `evaluation_response` is the original POST response;
`stored_evaluation_response` is the matching GET item. JSON objects are compared in full,
independently of field order. The client does not assume that the first GET item matches.

Retries use the same deterministic IDs and identical input content. The client checks
all three dedicated crew namespaces before any POST. Matching partial prior runs can
be completed; unrelated/different measurement content causes a failure. Choose a new
namespace such as `--namespace "frontend2"` in that case. No history is deleted or reset,
and no mission-demo-seeder code is imported or changed.

## Frontend request sequence

All paths below are relative to `/api/v1`. The full transcript provides runnable bodies
for the [existing commands](api-contracts.md#explicit-computation-commands).

1. `GET /health` and `GET /metrics`: confirm the server and canonical `sleep_duration`
   (`min`) and `sleep_efficiency` (`%`) definitions.
2. `POST /measurements` with `{"measurements": [...]}`: ingest labelled simulated
   measurements and read real quality assessments from the `201` `items` response.
3. `GET /crew-members/{crew}/measurements`: verify persisted values and assessments.
4. `POST /crew-members/{crew}/baselines` for each metric, with the prior reference
   window, mission timeline, explicit computation time and sourced synthetic criteria.
   Read `status`, `statistics`, `data_quality` and `baseline_id`; only actual established
   references are selected by this client. `GET .../baselines?mission_phase=in_flight`
   verifies the stored baseline bodies. Insufficient references are retained for display.
5. `POST /crew-members/{crew}/evaluations` with `domain: "sleep"`, the completed window,
   explicit `evaluated_at`, matching `mission_phase`, selected `baseline_ids` and the
   complete `sleep_config`. It returns `201` and one unchanged `EvaluationResult`.
6. `GET /crew-members/{crew}/evaluations?domain=sleep`: select the matching opaque
   `evaluation_id` and compare the entire object with the POST response. There is no
   single-evaluation GET-by-ID route; do not invent one or assume list position.

After running the full demo, the frontend developer can inspect stored responses directly:

```powershell
$sleepApiBase = "http://127.0.0.1:8000/api/v1"
$sleepCrewId = $sleepHttpRestriction.crew_member_id
Invoke-RestMethod "$sleepApiBase/crew-members/$sleepCrewId/measurements?metric=sleep_duration"
Invoke-RestMethod "$sleepApiBase/crew-members/$sleepCrewId/baselines?mission_phase=in_flight"
$sleepStored = Invoke-RestMethod "$sleepApiBase/crew-members/$sleepCrewId/evaluations?domain=sleep"
$sleepStored.items |
    Where-Object { $_.evaluation_id -ceq $sleepHttpRestriction.evaluation_response.evaluation_id } |
    ConvertTo-Json -Depth 40
```

Display the simulation notice, canonical units, observed medians, reference availability,
measurement quality, baseline status, evaluation status, algorithm identity, summary and
finding explanations separately. `attention` requests review, not a diagnosis or emergency.
`insufficient_data` may contain a descriptive median when some valid observations exist.
Null values and empty collections are unavailable data, never implied zeros or normality.
The API returns slopes and missing-night diagnostics in finding explanations; this client
preserves those strings rather than inventing structured slope or uncertainty fields.

## Synthetic protocol and policies

This section is the source of all hand-authored fixture dates, levels, faults, gaps and
policy constants in `scripts/demo_sleep_http.py`. The three isolated crews are
`sim-sleep-http-v1-restriction`, `sim-sleep-http-v1-sparse` and
`sim-sleep-http-v1-unusable` for the default namespace. Every submitted measurement uses
`source: "simulated"` and the simulated device identifier. No sensor range is invented.

Primary sleep periods start at 22:00 UTC and end at 07:00 UTC. The reference window is
`2026-10-18T12:00:00Z` through `2026-10-25T12:00:00Z`; baseline computation is fixed at
`2026-11-01T12:00:00Z`. The evaluation window is `[2026-11-01T12:00:00Z,
2026-11-10T12:00:00Z)`, with `evaluated_at: "2026-11-11T12:00:00Z"`. A simulated in-flight
phase starts on October 1 and contains both windows. All computation times must be in
the server's past; the supplied reference predates the evaluated observations.

The explicitly synthetic sleep policy uses four nights, minimum coverage 0.6, three
elapsed days, at most two consecutive missing nights, decreasing-transition fraction
0.75 and a 12:00 UTC night boundary. Duration gates are 5 min/day slope, 30 min fitted
change and 60 min baseline deviation. Efficiency gates are 0.5 percentage points/day,
3 percentage points fitted change and 5 percentage points baseline deviation. These
effect sizes follow the existing sleep demonstration convention, without clinical
interpretation. Baseline establishment requires seven samples spanning six days, with
`minimum_samples: 2` and an explicit `policy_source` identifying this synthetic protocol.
Declaring that source does not validate the criteria. The engine's other documented
baseline settings remain at their existing defaults.

| Case | Inputs and actual behavior |
| --- | --- |
| Restriction | Seven prior durations `(470,480,490,475,485,480,480)` and efficiencies `(90,91,92,91,93,92,92)` establish median references of 480 min and 92%. Later durations `(490,475,460,445,430,415,400,385,370)` omit offsets 2 and 6. Efficiency is 92% except a corrupt 125% at offset 4. A distinct-ID copy duplicates duration at offset 3. The 29 ingested records include 27 acceptable and two unusable observations. |
| Sparse | One prior night has 480 min and 91%; two current nights have 480/465 min and 92%. Both reference attempts return `insufficient_data`, n=1, and no statistics. Neither is selected as a baseline. Two of nine valid nights cannot support a trend conclusion; descriptive duration median 472.5 min remains available. |
| Unusable | Five nights of -30 min duration and 125% efficiency are valid finite contract numbers but definition-invalid observations. All ten receive actual unusable quality, and evaluation returns `insufficient_data` with no observed values or baseline. |

The real HTTP integration excludes non-acceptable records before sleep analysis and
explains excluded IDs. Restriction retains 7/9 duration nights and 6/9 efficiency nights.
The duration explanation reports slope `-15 min/day` and fitted change `-120 min`.
Observed duration median is 430 min, with a 480-min prior reference and signed deviation
-50 min. The duration trend, not a fabricated alarm from corrupted data, prompts
`attention`; efficiency remains `nominal` under the configured screen.

With default server quality settings, no acquisition cadence is assumed, so quality
completeness may be null. Missing nights remain visible in the sleep explanation and
coverage gates. An explicitly configured daily cadence is also tested. Window quality
uses the existing API rollup; it is degraded for the restriction case, acceptable for
the sparse case and unusable for the all-invalid case under default settings. Acceptable
quality does not imply sufficient evidence for a physiological finding.

Selected actual live responses for namespace `v1` with the current default configuration:

| Case | Evaluation ID | Status | Duration median/reference/deviation (min) | Full GET equals POST |
| --- | --- | --- | --- | --- |
| Restriction | `20b6e50e-e748-53f3-beab-6932f45d84da` | `attention` | 430 / 480 / -50 | true |
| Sparse | `80a62cce-fbf6-500d-9290-d15daf97918a` | `insufficient_data` | 472.5 / null / null | true |
| Unusable | `4140a446-4bc2-53c4-84e5-0150fe1fb4bb` | `insufficient_data` | null / null / null | true |

These are observed response excerpts, not hard-coded client results or clinical
validation. IDs are opaque. They can differ with namespace, history, server settings or
algorithm version; clients use IDs returned by the server. All measurement/baseline/
evaluation HTTP statuses were `201` for POST and `200` for GET in the successful run.

## Reproducibility, verification and limitations

Inputs, policies and computation timestamps are fixed. For unchanged history and
configuration, retried scientific snapshots and their IDs are identical. Ingestion
assessments and health timestamps belong to the real server clock; full transcripts
are not claimed to be byte-identical across different clocks or initial repository
states. Schema validation counts can include existing preflight rows on a retry.
The compact summary preserves scientific snapshot reproducibility; it does not erase
timestamps from the full HTTP evidence. Altered server quality settings may change
eligibility and fail expectations; the client reports actual output without overriding
those settings or forcing a pass.

Run one worker. The current repository is in memory: restarts, development reloads and
separate workers lose or separate state. New/backfilled observations can invalidate
stored baselines or evaluations; ingest first and recompute explicitly. The client
creates only its named demo crews, does not reset the repository and does not require
mission-demo-seeder or frontend changes.

From `backend/`, verification commands are:

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
python -m scripts.demo_sleep_http --base-url "http://127.0.0.1:8000/api/v1" --namespace "v1" --validate
```

Automated HTTP tests use the real app through FastAPI TestClient, not a live network or
mocked scientific outputs. They verify engine calls, canonical JSON/schema validation,
historical-reference eligibility, missing and invalid evidence, retries, wall-clock
independence of scientific snapshots, full content matching, list ordering, isolated
crews and failure exits. The same client is separately run over real loopback HTTP.
No shared schemas, routes, algorithms, frontend, Marco domains or RAG files are changed.
For scientific assumptions and limits, see the existing
[sleep module documentation](../backend/app/domains/sleep/README.md).
