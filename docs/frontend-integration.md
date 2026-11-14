# Frontend integration for the API MVP

Silvio can use the same JSON API from React, Flutter Web, or another HTTP client.
No frontend implementation is included in this change. The existing resource
contracts in `backend/app/models/` and `/schemas` remain authoritative and unchanged.
OpenAPI describes the new request commands and list envelopes.

## Run the backend

From `backend/`, with the existing requirements installed:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use one worker. Storage belongs to this process: restarting the server, including
`--reload` after a code change, erases measurements, baselines and evaluations.
There is no database, external service, authentication setup or RAG dependency.

- Development API base URL: `http://127.0.0.1:8000/api/v1`.
- Interactive requests: `http://127.0.0.1:8000/docs`.
- Generated OpenAPI: `http://127.0.0.1:8000/openapi.json`.
- Change the host/port with Uvicorn and set the frontend base URL to match.
- React/Vite can use `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1`.
- Flutter can use `--dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1` and read
  `String.fromEnvironment('API_BASE_URL')`.

Default CORS accepts HTTP/HTTPS origins on `localhost` or `127.0.0.1` at any port,
including Vite and Flutter's varying development ports. JSON POST preflights are
supported. Configure additional exact origins with
`ORBITVITALS_CORS_ALLOW_ORIGINS='["https://frontend.example"]'`; optionally replace
`ORBITVITALS_CORS_ALLOW_ORIGIN_REGEX`. Configure these before starting the process.

## Implemented routes

Paths below are relative to `/api/v1`.

| Method | Path | Response |
| --- | --- | --- |
| GET | `/health` | Existing health response |
| GET | `/metrics` | `{"items": [MetricDefinition, ...]}` |
| POST | `/measurements` | `201`, `{"items": [PhysiologicalMeasurement, ...]}` |
| GET | `/crew-members/{crew_member_id}/measurements` | `{"items": [PhysiologicalMeasurement, ...]}` |
| POST | `/crew-members/{crew_member_id}/baselines` | `201`, one `PersonalBaseline` |
| GET | `/crew-members/{crew_member_id}/baselines` | `{"items": [PersonalBaseline, ...]}` |
| POST | `/crew-members/{crew_member_id}/evaluations` | `201`, one `EvaluationResult` |
| GET | `/crew-members/{crew_member_id}/evaluations` | `{"items": [EvaluationResult, ...]}` |

Measurement filters: `metric`, inclusive `start`, exclusive `end`, optional `limit`.
Baseline filters: `metric`, `mission_phase`. Evaluation filters: `domain`, inclusive
`start` and exclusive `end` applied to `window_end`, optional `limit`. Limits are
integers from 1 through 1000; omitting a limit returns all matching in-memory items.
Measurement order is oldest first; baseline/evaluation order is newest first. Ties
have deterministic ID ordering. All filter timestamps must carry a timezone.

Unknown crew collections return `200` and `{"items": []}`. No synthetic crew registry
or mission timeline is invented. The proposed mission-directory route is not
implemented; baseline commands receive explicit `MissionPhase` objects from the caller.

## Frontend request sequence

1. Load `/metrics` for exact metric names, canonical units and domains.
2. POST `{"measurements": [...]}`. Send 1 through 1000 canonical measurements with
   unique IDs. Keep `source="simulated"` for every fabricated example.
3. Read returned `data_quality` or fetch the stored history. The backend replaces
   producer quality with the real Data Quality Engine assessment. Ingestion alone
   does not create a personal baseline or a physiological evaluation.
4. When a mission timeline and historical reference window are available, explicitly
   POST a baseline command. Read its status and quality before selecting it as a
   reference. Baseline generation is optional for trend/target-only analysis.
5. When recording context and any required screening policy are available, explicitly
   POST an evaluation command for a completed window. Read the canonical result or
   retrieve saved results through GET. The selected baseline must predate that window.

Do not turn `items: []` into a zero-activity day or a nominal health result. It means
that no matching resource has been stored. In React/Flutter, keep request-loading
state separate from empty data and from returned `insufficient_data` evaluations.
Display metric values, measurement quality, baseline status and evaluation status
separately. Display `summary`, each finding's `explanation`, units and algorithm
identity. The interface must not interpret `attention` as a diagnosis or medical risk.

An identical measurement ID/content retry is idempotent, with status `201`; duplicate
IDs within a batch return one item each in first-occurrence order. Equality ignores
producer `data_quality`. Conflicting content, including a different crew member,
returns `409` and writes none of the batch. Different IDs for one observation are
retained and assessed, not silently merged into a new identity.

Malformed requests, unknown body fields, wrong units, invalid filters and incompatible
computation context return `422` with a `detail` array. A missing/foreign selected
baseline returns `404` with a string `detail`. A conflict returns `409` with a string
`detail`. Rejected NaN/Infinity values also return valid JSON validation errors.
Negative/impossible metric values may be valid contract numbers: the quality engine
stores and labels them unusable rather than pretending they are physiological alerts.

## Runnable simulated activity workflow (PowerShell)

Run this after starting the server. Every value, identifier, target, tolerance and
establishment criterion here is **SIMULATED**, solely to exercise the integration.
These numbers are not recommended mission settings or clinical thresholds. The
script loads prior and current sessions, builds a genuine daily-total baseline with
the real engine, and compares a later activity window through the real activity module.

```powershell
$apiBase = "http://127.0.0.1:8000/api/v1"
$demoCrew = "sim-http-guide-crew"
$demoPrior = [datetimeoffset]"2026-10-26T00:00:00Z"
$demoCurrent = [datetimeoffset]"2026-11-02T00:00:00Z"
$demoRecords = @()
$demoWindows = @(
    @{ FirstDay = $demoPrior; Minutes = @(40, 45, 50) },
    @{ FirstDay = $demoCurrent; Minutes = @(40, 30, 20) }
)
foreach ($demoWindow in $demoWindows) {
    for ($demoDay = 0; $demoDay -lt 3; $demoDay++) {
        $demoInstant = $demoWindow.FirstDay.AddDays($demoDay).AddHours(9)
        foreach ($demoMetric in @("exercise_duration", "active_energy_expenditure")) {
            $demoValue = 200
            $demoUnit = "kcal"
            if ($demoMetric -eq "exercise_duration") {
                $demoValue = $demoWindow.Minutes[$demoDay]
                $demoUnit = "min"
            }
            $demoRecords += @{
                measurement_id = "sim-http-guide-$($demoInstant.ToString('yyyyMMdd'))-$demoMetric"
                crew_member_id = $demoCrew
                metric = $demoMetric
                unit = $demoUnit
                value = $demoValue
                measured_at = $demoInstant.ToString("o")
                interval_end = $demoInstant.AddHours(1).ToString("o")
                source = "simulated"
                device_id = "sim-http-guide-device"
            }
        }
    }
}
$demoIngested = Invoke-RestMethod "$apiBase/measurements" -Method Post `
    -ContentType "application/json" `
    -Body (@{ measurements = $demoRecords } | ConvertTo-Json -Depth 20)

function New-SimulatedCoverage([datetimeoffset]$firstDay) {
    for ($coverageDay = 0; $coverageDay -lt 3; $coverageDay++) {
        foreach ($coverageMetric in @("exercise_duration", "active_energy_expenditure")) {
            @{
                day = $firstDay.AddDays($coverageDay).ToString("yyyy-MM-dd")
                metric = $coverageMetric
                complete = $true
            }
        }
    }
}
$demoBaselineBody = @{
    metric = "exercise_duration"
    mission_phase = "in_flight"
    mission_phases = @(@{
        phase_id = "sim-http-guide-phase"
        mission_id = "sim-http-guide-mission"
        phase = "in_flight"
        start_time = "2026-10-01T00:00:00Z"
    })
    reference_start = "2026-10-26T00:00:00Z"
    reference_end = "2026-10-29T00:00:00Z"
    computed_at = "2026-11-02T00:00:00Z"
    aggregation = "complete_active_day_total"
    activity = @{ coverage = @(New-SimulatedCoverage $demoPrior) }
    config = @{
        established_min_samples = 3
        policy_source = "SIMULATED frontend smoke-test criterion; not clinical guidance"
    }
}
$demoBaseline = Invoke-RestMethod "$apiBase/crew-members/$demoCrew/baselines" `
    -Method Post -ContentType "application/json" `
    -Body ($demoBaselineBody | ConvertTo-Json -Depth 20)

$demoEvaluationBody = @{
    domain = "physical_activity"
    mission_phase = "in_flight"
    window_start = "2026-11-02T00:00:00Z"
    window_end = "2026-11-05T00:00:00Z"
    evaluated_at = "2026-11-06T00:00:00Z"
    baseline_ids = @($demoBaseline.baseline_id)
    activity = @{
        coverage = @(New-SimulatedCoverage $demoCurrent)
        baselines_comparable = $true
        policies = @(
            @{ metric = "exercise_duration"; daily_target = 30; baseline_absolute_tolerance = 10 },
            @{ metric = "active_energy_expenditure"; daily_target = 100 }
        )
    }
}
$demoEvaluation = Invoke-RestMethod "$apiBase/crew-members/$demoCrew/evaluations" `
    -Method Post -ContentType "application/json" `
    -Body ($demoEvaluationBody | ConvertTo-Json -Depth 20)
[ordered]@{
    data_kind = "simulated"
    ingested_measurements = $demoIngested.items.Count
    baseline_status = $demoBaseline.status
    baseline_mean_minutes = $demoBaseline.statistics.mean
    evaluation_status = $demoEvaluation.status
    observed_mean_minutes = $demoEvaluation.findings[0].observed_value
    absolute_deviation_minutes = $demoEvaluation.findings[0].absolute_deviation
} | ConvertTo-Json
```

The script prints this summary of the actual resource responses:

```json
{
  "data_kind": "simulated",
  "ingested_measurements": 12,
  "baseline_status": "established",
  "baseline_mean_minutes": 45.0,
  "evaluation_status": "attention",
  "observed_mean_minutes": 30.0,
  "absolute_deviation_minutes": -15.0
}
```

Inspect full stored JSON with:

```powershell
Invoke-RestMethod "$apiBase/crew-members/$demoCrew/measurements?metric=exercise_duration"
Invoke-RestMethod "$apiBase/crew-members/$demoCrew/baselines?mission_phase=in_flight"
Invoke-RestMethod "$apiBase/crew-members/$demoCrew/evaluations?domain=physical_activity"
$demoEvaluation | ConvertTo-Json -Depth 30
```

## Sleep command example

The following valid request can be sent to
`POST /api/v1/crew-members/sim-sleep-crew/evaluations`. All policy numbers are
**SIMULATED demonstration choices**. Without corresponding stored sleep measurements
it correctly returns `insufficient_data`, never invented observations. After ingesting
eligible nightly summaries through `/measurements`, the same shape runs the real sleep
trend module. Use canonical `sleep_duration` (`min`) and `sleep_efficiency` (`%`) records
whose intervals contain the measured duration. One complete primary summary per metric
per operational night is required by the module; naps/revisions need producer resolution.

```json
{
  "domain": "sleep",
  "window_start": "2026-11-02T12:00:00Z",
  "window_end": "2026-11-06T12:00:00Z",
  "evaluated_at": "2026-11-07T00:00:00Z",
  "mission_phase": "in_flight",
  "sleep_config": {
    "policy_id": "simulated-frontend-example",
    "duration": {
      "minimum_slope_per_day": 5,
      "minimum_total_change": 15,
      "minimum_observation_deviation": 30
    },
    "efficiency": {
      "minimum_slope_per_day": 0.5,
      "minimum_total_change": 2,
      "minimum_observation_deviation": 5
    },
    "minimum_nights": 3,
    "minimum_coverage": 1,
    "minimum_span_days": 2,
    "maximum_consecutive_missing_nights": 0,
    "minimum_decreasing_fraction": 1,
    "night_start_hour_utc": 12
  }
}
```

## Scientific configuration and integration policy

The application calls the real engines; it does not import any demonstration policy.
All settings use existing documented algorithm meanings:

| Input | Application behavior |
| --- | --- |
| `ORBITVITALS_DATA_QUALITY` | JSON `DataQualityConfig`: documented device ranges, expected acquisition intervals, clock/interval tolerances and quality sufficiency settings; algorithm defaults otherwise |
| `ORBITVITALS_SLEEP_CONFIG` | Optional complete `SleepConfig` JSON; per-request `sleep_config` overrides it; without either, an explained `insufficient_data` orchestration result |
| Baseline `config` | `minimum_samples=2`, unset establishment criteria, modified-z cutoff 3.5 with report/keep handling by default, exactly as documented by the existing engine |
| Baseline establishment | Explicit sample/span criteria plus `policy_source`; declaring a policy does not validate it; identical reference values remain provisional under the engine's rule |
| Activity `policies` | Optional personal daily/weekly minimums and absolute/relative baseline tolerances; no targets or deviation tolerances are assumed |
| Activity `coverage` | Explicit per-day/per-metric recording completeness, independent of a sampling-cadence estimate; no records without confirmation means unknown |
| Activity `day_plans`, `sessions` | Rest, operational exceptions, overrides and explicit session-to-measurement links; all session IDs must refer to this crew's stored activity history |
| Activity `reduction_run_length` | Existing descriptive module convention, default 3; not a significance or clinical threshold |

`DataQualityConfig` uses `sensor_ranges[device_id][metric]` entries with `minimum`,
`maximum` and a nonempty documentary `source`; no range is supplied by this MVP.
Expected intervals and duration settings accept ISO 8601 duration strings, for example
`"P1D"` for a protocol that actually specifies one observation per day. Without a
configured acquisition cadence the engine leaves sample completeness and score unset.
Activity recording confirmation is still required separately.

Ingestion assesses the entire affected crew history, preserving values and IDs. Sleep
screening admits only engine-acceptable measurements, a deliberately conservative
application eligibility rule. Excluded IDs are explained. The exact per-metric window
quality is supplied to the sleep adapter. Window quality combines statuses and flags
without averaging scores or pooling different sample denominators. A missing/unusable
metric suppresses that metric; it does not erase justified findings for the other.
Activity receives assessed measurements and applies its documented stricter quality,
overlap, recording and session rules. Neither adapter emits an unsupported `alert`.

Baselines use only stored, reassessed measurement history and the supplied mission
timeline/reference bounds. The existing raw-measurement engine assigns phases and
reference membership by observation start; it does not split intervals at phase or
reference boundaries. Producers must resolve those cases before using raw references.
Daily activity references additionally require complete
usable active days contained in the requested phase. Rest and operational exceptions
are excluded. A day crossing a phase boundary is withheld. Sessions are summed first;
daily totals are transient engine inputs, not new raw device readings. Original device
ranges and irregular per-record sampling cadence are not reapplied to sums. Mixed
source types within an aggregated day require producer reconciliation (`422`).
An explicitly confirmed empty day is a manual recording assertion of zero. Missing
reference dates are counted and degrade reference quality even if sample-count
establishment criteria happen to pass. The activity module then withholds use of that
degraded baseline. API baseline IDs include aggregation/provenance metadata so that
session-level and daily-level references cannot collide.

Baseline selection is explicit through `baseline_ids`: matching crew, domain, phase,
and aggregation are checked. Choose at most one reference for each metric. Sleep
expects `measurement` references. Activity expects `complete_active_day_total` and an
explicit `baselines_comparable` confirmation after device/protocol/context review.
The modules retain their historical-window, establishment, quality and zero-reference
guards. No baseline is synthesized from the evaluated window or promoted to established
by the API. Provisional or otherwise ineligible references remain explained, unused
references. Baseline and evaluation timestamps are snapshots, not forecast horizons.

See [algorithm documentation](../backend/app/algorithms/README.md),
[sleep documentation](../backend/app/domains/sleep/README.md), and
[activity documentation](physical-activity-monitoring.md) for the algorithms' full
assumptions, operational parameter meanings and scientific limitations.

## Storage behavior and remaining integration requirements

The per-app repository uses a process-local lock, copied resource models and stable
sorting. A batch conflict cannot partially write data. An identical retry does not
create another record or invalidate results. New/backfilled measurements or changed
quality invalidate saved snapshots in intersecting crew/time windows, conservatively
across metrics, and evaluations that reference an invalidated baseline. Later activity
outside a prior reference window preserves that baseline. GET can therefore return
an empty derived-result collection after backfill; recompute explicitly.

For fixed commands, history, policy and explicit computation time, IDs/results are
deterministic. Omitting computation time requests a fresh server-time snapshot.
Restarts and separate workers do not share state. The MVP has no durable retention,
pagination cursor, crew directory, mission directory, or automatic evaluation schedule.
Those are application integration needs, not fabricated scientific outputs.

No code blocker remains for the four integrated scientific modules. Real operation
still needs mission timelines, acquisition/device documentation, primary sleep-period
selection, reviewed sleep policies, baseline establishment criteria, and authoritative
activity completeness/context. Missing prerequisites remain visible as provisional or
insufficient results. Vitals/cognition evaluation adapters, nutrition monitoring and RAG
are outside this integration; requesting an unsupported computation domain returns
`422`. Their owners' code and concurrent scenario files are unchanged.

## Verification

From `backend/`:

```bash
python -m pytest
python -m pytest tests/api
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
```

API tests verify ingestion, invalid units/JSON/non-finite values, duplicate identity,
cross-request quality context, documented sensor failures, baseline creation and
retrieval, daily aggregation, sleep/activity evaluation, missing data, astronaut/app
isolation, deterministic replay, backfill invalidation, CORS preflights, OpenAPI
generation/reference resolution and resource validation against existing schemas.
