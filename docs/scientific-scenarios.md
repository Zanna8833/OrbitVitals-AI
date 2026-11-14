# Scientific mission scenarios and replay

This package demonstrates the current OrbitVitals AI scientific interfaces with
deterministic, explicitly **simulated** inputs. It runs the existing Data Quality,
Personal Baseline, Sleep Monitoring and Physical Activity algorithms. It never assigns
their output statistics or statuses from a scenario script. Expected behavior is
compared with actual output after execution; a mismatch stays visible and fails replay.

The scenarios are software demonstrations for the NASA Space Apps Challenge. They are
not astronaut records, NASA standards, clinical validation or proof of suitability for
spaceflight. No scenario diagnoses illness, establishes health, estimates medical risk
or prescribes treatment. All interface strings and artifacts are in English.

## Replay instructions

Use the repository's Python 3.11 environment, with its pinned dependencies. Run these
commands from `backend/`:

```powershell
python -m app.scenarios --help
python -m app.scenarios list
python -m app.scenarios list --json

python -m app.scenarios replay sensor_quality_failure --validate
python -m app.scenarios replay personalized_baseline --validate
python -m app.scenarios replay progressive_sleep_restriction --validate
python -m app.scenarios replay exercise_adherence_change --validate
python -m app.scenarios replay insufficient_data --validate

python -m app.scenarios replay progressive_sleep_restriction --json --validate
python -m app.scenarios replay all --json --validate
```

Without `--json`, replay prints checkpoint explanations, expected and actual values,
PASS/FAIL markers, limitations and any blockers. With `--json`, stdout contains only
complete machine-readable JSON with a trailing newline. No files are written by the
package. Callers can capture stdout for export. Error diagnostics use stderr.

Exit codes are `0` for matching expectations, `1` for a behavioral mismatch or a
reported blocker, and `2` for invalid CLI usage or a handled execution/validation error.
A failed expectation never overwrites an engine output to make the demonstration pass.
The `all` command replays the five scenarios in catalog order.

`--validate` uses the existing pinned `jsonschema` development dependency. Normal
execution and serialization require only the current runtime dependencies and standard
library. No dependency or requirements file is added or changed.

The Python interface is also available without the HTTP layer:

```python
from app.scenarios import canonical_json, list_scenarios, replay_scenario, validate_contracts

catalog = list_scenarios()
result = replay_scenario("progressive_sleep_restriction")
assert result.all_checks_passed
validated_payloads = validate_contracts(result)
artifact = canonical_json(result)
```

## Execution and artifact structure

Each invocation generates fresh fixtures and reruns real algorithms at fixed UTC
checkpoints. There is no random generator, seed-dependent dataset, system-clock lookup,
random evaluation identifier, cached result, network request or storage dependency.
Activity requests explicitly set both `evaluation_id` and `evaluated_at`, overriding
that module's nondeterministic defaults. Baseline identifiers come from the real
engine's deterministic content-derived identifier implementation.

Measurements are restricted to the data available by each checkpoint. Mission phases
can include known future plans; the baseline engine clips reference windows at
`computed_at`. The final baseline checkpoint compares two policies at the same time,
not two successive physiological events. The insufficient-data scenario contains
independent cases, ordered by their fixed assessment times.

The local envelope has `replay_format_version: "0.1.0"`, `data_kind: "simulated"`, a
simulation notice, scenario purpose/assumptions/limitations, ordered `steps`, and
`all_checks_passed`. Each step contains:

| Field | Meaning |
| --- | --- |
| `step_id`, `as_of` | Explicit checkpoint identity and UTC observation horizon |
| `explanation` | Human-readable context based on actual results |
| `inputs.measurements` | Original canonical `PhysiologicalMeasurement` payloads |
| `inputs.mission_phases` | Existing `MissionPhase` contracts, when applicable |
| `inputs.parameters` | Exact configuration and call parameters; durations have explicit `seconds` units |
| `inputs.activity_request` | Existing domain-local activity input with plans, coverage and targets |
| `outputs.assessed_measurements` | Measurements assessed by the real Data Quality Engine |
| `outputs.quality_windows` | Explicit per-metric scopes and actual `DataQuality` contracts |
| `outputs.baselines`, `baseline_queries` | Actual references or `null` for an unavailable phase window |
| `outputs.evaluations` | Unchanged `EvaluationResult` contracts, including provenance and explanations |
| `outputs.observation_findings` | Actual single-observation sleep findings for unusable records |
| `outputs.sleep_trends` | The existing sleep dataclasses, including actual slopes, gaps and insufficiency reasons |
| `outputs.activity_report` | The existing domain-local daily, weekly, session and reduction-run report |
| `outputs.rejected_inputs` | Deliberately invalid raw candidates and actual Pydantic validation messages |
| `checks` | Separately authored expectations, actual values and their comparison result |
| `blockers` | Explicit inability to demonstrate behavior through an existing interface, if encountered |

Input/output collections and scenario metadata carry the simulation label; every
generated measurement has `source: "simulated"`. Rejected candidates also retain
that label. Returned snapshots are detached from mutable engine constants so a caller
cannot alter a later replay by editing an earlier result.

The envelope and domain-local reports are not public API additions. Export individual
contracts from the appropriate fields rather than submitting the envelope to an
endpoint that expects a measurement, baseline or evaluation. Unknown contract fields
remain rejected. No generated schema is edited or added.

Validation first revalidates the serialized local envelope, then validates every
embedded shared contract against the committed files in `schemas/`. Standalone
`MetricFinding` objects use the existing definition inside the evaluation schema.
The local activity report and sleep diagnostic structures also pass their generated
local envelope schema. Counts include repeated nested occurrences, not only unique
observations. Deliberately rejected raw candidates are explicitly outside the
measurement contract and are not falsely reported as valid measurement payloads.
Validation is offline; schemas are resolved from the checkout, independently of the
process working directory. Python callers can supply `schema_directory` when packaging
the validator separately.

## Fixture protocol

This section is the source of the hand-authored fixture dates, sequences, acquisition
conventions and configuration constants in `app/scenarios/fixtures.py` and checkpoint
choices in `replay.py`. They are engineering choices that exercise the software. They
have no claimed clinical or NASA authority. Canonical units come from the existing
metric catalog. Durations used for calendars and configuration are ordinary elapsed
UTC time, not physiological formulas.

### Sensor quality failure

The seven-night window starts at `2026-11-01T12:00:00Z`. Primary sleep periods start
at 22:00 UTC and have nine-hour observation intervals. Duration is 480 min except
for an injected negative value of -30 min on night offset 5; efficiency is 92% except
for an injected 125% on offset 2. A duration observation on offset 3 has a redundant
copy with a distinct opaque identifier. No identifier is parsed to determine behavior.

The real quality engine assesses all 15 records as one batch and finds 12 acceptable
records and three unusable records: two definition violations and one redundant copy.
There is no invented device range. Quality windows are degraded; six usable nights
per metric remain for sleep trends. The remaining values are constant, so the actual
sleep evaluation is `nominal` under the configured statistical policy. This means no
configured trend was found, not that the astronaut is healthy or that a sensor issue
is harmless in an operational setting.

Timestamp-presence completeness is 1.0 because records exist at all seven expected
times, including corrupt records. Usable-night coverage is 6/7. The differing values
are intentional: presence, usability and physiological interpretation are distinct.
Unusable individual sleep findings remain `insufficient_data`.

### Personalized physiological baseline

The fictional timeline starts at `2026-10-01T12:00:00Z`. Relative half-open day ranges
are pre-flight `[0,14)`, launch `[14,16)`, in-flight `[16,30)`, return `[30,31)` and
post-flight `[31,35)`. These illustrative phase durations are not a real mission plan.

Pre-flight daily heart-rate values are `(56,57,58,59,60,58,58)` repeated twice.
In-flight values are `(62,63,64,65,-5,64,64)` repeated twice. The two negative values
are deliberately corrupted records, excluded by quality admission. One launch value
is 61 bpm. Pre/in-flight records occur nine hours after each daily phase boundary;
the launch observation is one hour after launch starts. No population range is used.

Checkpoints are days 3, 16 and 30. The demonstration policy admits the baseline
engine's default acceptable-quality records and requires ten samples spanning nine
elapsed days for `established`; the arithmetic minimum for reporting statistics remains
the engine's existing default. These criteria are not validated establishment rules.
The engine's default potential-outlier reporting policy is retained, without relabelling
unusual but valid values as sensor errors.

Actual results include early provisional history, one insufficient launch sample,
pre-flight median 58 bpm from 14 values, and in-flight median 64 bpm from 12 admitted
values. In-flight baseline quality remains degraded because corrupt records were
present. A future phase query returns `null`. A fourth checkpoint at the same day-30
horizon removes establishment criteria: pre/in-flight references remain provisional
with unchanged statistics. Establishment, data quality and physiological status are
three different concepts; this scenario produces reference statistics without a
healthy/ill classification.

### Progressive sleep restriction

The nine-night window uses the same UTC sleep-period convention. Duration values are
`(490,475,460,445,430,415,400,385,370)` min. Efficiency stays at 92%. Night offsets 2
and 6 are absent for both metrics. Replays occur after 2, 5 and 9 complete buckets.

The explicit sleep policy requires four included nights, coverage of at least 0.6,
three elapsed days, at most two consecutive missing nights and a decreasing-transition
fraction of at least 0.75. Duration effect-size gates are 5 min/day slope and 30 min
fitted change; the optional baseline deviation gate is 60 min. Efficiency gates are
0.5 percentage points/day, 3 percentage points fitted change and 5 percentage points
baseline deviation. The operational night boundary is 12:00 UTC. These settings
follow the existing sleep demonstration convention and have no clinical interpretation.

The two-night checkpoint reports a descriptive slope but stays `insufficient_data`.
The later checkpoints detect the actual progressive-duration signal. Final output has
seven of nine observed nights, a -15 min/day slope, -120 min fitted change over eight
elapsed days, median 430 min and explicit missing dates `2026-11-03` and `2026-11-07`.
Per-metric quality is degraded by missing data. No personal baseline is synthesized.

Selected JSON fields from the final actual trend output are:

```json
{
  "slope_per_day": -15.0,
  "fitted_change": -120.0,
  "coverage": 0.7777777777777778,
  "missing_nights": ["2026-11-03", "2026-11-07"],
  "signal": "progressive_duration_reduction"
}
```

This is an excerpt, not a replacement for a full replay artifact. Its associated
regression check contains `expected: -15.0`, `actual: -15.0`, and `passed: true`.
No p-value, uncertainty interval, clinical sleep debt or risk estimate is invented.
Uncertainty remains visible through missing nights, sufficiency reasons and quality.

### Exercise adherence change

The two-week UTC window starts Monday `2026-11-02T00:00:00Z` and has checkpoints after
7 and 14 complete days. Independent hand-authored session sequences are:

- Duration in min: `(60,55,50,45,40,0,35,30,25,20,15,None,0,10)`.
- Active energy in kcal: `(300,280,260,220,200,0,170,150,120,100,None,None,0,50)`.

Energy is not calculated from duration. Sessions start at 09:00 UTC and have one-hour
recording intervals. Planned rest is explicit on offsets 5 and 12. Those dates have
caller-confirmed complete coverage and no additive records, allowing an explicit zero
under the activity module's existing convention. No sensor-quality assessment is
fabricated for empty rest days. On offset 10, duration has a known 15-min subtotal but
energy is missing, the session lacks that linked metric, and coverage is incomplete.
Offset 11 has neither measurements nor recording confirmations. Missing days are not
filled with zero. Each observed session record is assessed by the real quality engine;
no fixed sensor sampling cadence is assumed for variable session data.

The fictional personal plan sets daily targets of 40 min and 200 kcal, weekly targets
of 240 min and 1200 kcal, and a reduction-run length of three comparable periods.
These are exercise-plan demonstration inputs, not recommendations. Weekly targets
already reflect the planned rest schedule. No activity baseline is supplied.

The actual report identifies duration runs `[60,55,50,45,40]` and `[35,30,25,20]`, with
corresponding independent energy runs. Rest and recording gaps break runs. The first
complete week meets both weekly targets. The second week stays `unknown` because
recording is incomplete; a low known subtotal does not prove missed adherence.
Complete late active days can still be labelled `missed` against the explicit daily
plan. The overall `attention` result requests review of these records and context.

### Insufficient or unusable data

Four independent cases retain unknown conclusions:

1. A single heart-rate observation in the in-flight reference window yields an actual
   `insufficient_data` baseline with no statistics. A post-flight query before its
   window exists returns `null`.
2. One 30-min activity observation in a three-day window has no complete recording
   confirmation or personal baseline. Even with a configured 40-min daily target,
   adherence remains `unknown` and evaluation remains `insufficient_data`.
3. An empty five-night sleep window yields no observed values. An intentionally
   noncanonical `hours` payload is rejected by the actual Pydantic validator before
   entry to any scientific engine. Its raw JSON and validation errors remain labelled
   rejected candidates, not valid physiological measurements.
4. Five nights of -30-min duration and 125% efficiency produce actual unusable quality
   assessments and insufficient sleep evaluations with no invented observed values.

## Scientific evidence and limitations

The evidence demonstrated here is executable software behavior on authored fixtures.
Regression expectations are not validation results for real humans, sensors or missions.
No new scientific estimator or clinical threshold is implemented in the package.
Existing formulas, policies and scientific citations remain in their owning modules:

- [Data Quality Engine](../backend/app/algorithms/data_quality.py): mathematical metric
  definitions, duplicate handling, acquisition completeness and usability proportions.
- [Personal Baseline Engine](../backend/app/algorithms/personal_baseline.py) and
  [robust statistics](../backend/app/algorithms/robust_statistics.py): phase-aware
  references, descriptive statistics and documented potential-outlier conventions.
- [Sleep methods and limitations](../backend/app/domains/sleep/README.md): median
  pairwise elapsed-time slopes, explicit effect gates and progression heuristics.
- [Physical Activity methods and limitations](physical-activity-monitoring.md): additive
  totals, recording-aware adherence, contextual exclusions and consecutive reductions.

Acceptable quality means only that the available checks passed. No device measuring
range or sensor accuracy claim is configured here. Statistical trends are descriptive;
missingness can be informative, reference selection can be biased, and passing a
coverage gate does not eliminate uncertainty. The phase-dependent heart-rate sequences
do not prove a physiological adaptation model. Exercise targets and baseline
establishment settings require separate operational/scientific review before other use.

The actual sleep adapter accepts per-metric quality contracts but has no shared
cross-metric quality aggregator. Accordingly, its overall `data_quality` stays
`not_assessed` while per-metric assessments retain real engine provenance. The package
does not invent a combined score or request changes to that interface. All required
scenarios run correctly through current interfaces; no required scenario is blocked.

## Integration requirements

A future dashboard should preserve the simulation notice, render each checkpoint's
explanation, and present quality, baseline availability and evaluation status separately.
Display null and `unknown` values as unavailable, never as zeros or emergency labels.
Policy comparisons at one observation horizon are not new mission events. Direct
scientific diagnostics and daily recording details are available without parsing the
plain-language explanations.

For existing-contract consumers, use `outputs.evaluations`, `outputs.baselines`,
`outputs.assessed_measurements` and scoped quality assessments. The replay envelope,
activity request/report and sleep dataclasses remain local integration structures.
The package imports neither API routers nor repositories/services from concurrent API
integration work, and it does not depend on changes to Marco's domains. The caller
remains responsible for triggering, persistence, authorization and dashboard transport.

Adapting future real datasets requires agreed primary-sleep timestamps, unit conversion,
device calibration, duplicate reconciliation, mission timeline, additive activity
semantics, recording confirmations and reviewed personal plans. Session-level or
heart-rate baselines cannot be substituted for complete-active-day activity references.
Those semantics are not encoded by the generic `PersonalBaseline` contract; the
existing activity adapter requires an explicit compatibility declaration. The current
exercise scenario therefore uses configured targets without manufacturing a reference.

The checkout's committed schemas must accompany validation, or the caller must provide
their directory. Keep Python and dependencies pinned for reproducibility. Canonical
JSON uses sorted keys, finite numbers, UTC timestamps and deterministic set encoding;
tests compare output across fresh processes, hash seeds and timezone settings in the
test environment. Cross-version/platform scientific validation is not claimed.

## Verification commands

```powershell
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
python -m app.scenarios replay all --validate
```

Scenario tests also compare outputs with independent direct engine calls, validate
every embedded shared contract, disable network connections, exercise invalid
contracts and schema failures, and change a duration fixture to prove that actual
outputs and exit status change instead of being forced to match expectations.
All created implementation and test files are confined to `app/scenarios/` and
`tests/scenarios/`; this is the only additional documentation file.
