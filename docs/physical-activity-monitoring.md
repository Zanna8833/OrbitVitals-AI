# Exercise and physical activity monitoring

The module is a deterministic research prototype for reviewing recorded activity.
It does not diagnose deconditioning, determine fitness for duty, prescribe exercise,
or estimate medical risk. Its only metrics are the existing canonical
`exercise_duration` in **min** and `active_energy_expenditure` in **kcal**.

## Location and Python interface

Implementation: `backend/app/domains/physical_activity/`.
Tests: `backend/tests/domains/physical_activity/`.
The scientific layer imports shared Pydantic models and the Python standard library;
it does not import FastAPI, the HTTP layer, or either unfinished scientific engine.
No dependencies, shared models, generated schemas, or HTTP routes are changed.

```python
from app.domains.physical_activity import ActivityRequest, monitor_activity

request = ActivityRequest.model_validate(payload)
report = monitor_activity(request)
evaluation_json = report.evaluation.model_dump_json()
```

`report.evaluation` is the unchanged shared `EvaluationResult`, with domain
`physical_activity`, two canonical `MetricFinding` entries, algorithm name
`physical_activity_monitor`, and version `0.1.0`. It can be passed to a future
evaluation repository or response adapter without changing the existing contract.
`ActivityRequest`, `ActivityReport`, session links, plans and coverage are **local
Python integration models**, not proposed additions to the public HTTP contract.

The report also contains:

| Field | Content |
| --- | --- |
| `days` | UTC dates, plan context, metric totals, targets, adherence, coverage and quality |
| `weeks` | Monday-based ISO weeks, totals, weekly targets and comparable weekly changes |
| `sessions` | Explicitly linked session observations and missing-field explanations |
| `trends` | Maximal strictly decreasing runs of comparable daily or weekly totals |
| `notices` | Exclusions, safe duplicate removal, unusable baselines and simulation labels |

## Input responsibilities

An evaluation has one crew member and one mission phase. Supply timezone-aware
timestamps; the implementation normalizes output timestamps and calendar allocation
to UTC. Windows are half-open `[window_start, window_end)`, must have positive
duration, and cannot extend beyond `evaluated_at`. Supply `evaluation_id` and
`evaluated_at` for reproducible results; otherwise they default to a UUID and UTC now.

Measurements must be **additive, non-overlapping contributions**, such as separate
exercise-session values or independent activity-energy increments. Never mix a daily
energy total with energy contributions already contained in that total. Convert
cumulative device counters to validated increments before calling this module.
The shared canonical-unit validator still applies; this module does no unit
conversion. It never derives kcal from minutes or body mass, and never substitutes
session elapsed time for measured exercise duration.

`ExerciseSession` identifies a session, its optional end time, and measurement IDs.
Links group existing values and never add another copy to daily totals. A measurement
can belong to at most one session; closed session intervals must not overlap. Unknown links, duplicate configuration keys,
conflicting measurement IDs, foreign crew measurements and unsupported metrics are
validation errors. An unknown session end or a missing linked metric prevents
complete recording from being asserted for the affected metric and period.

## Recording completeness and quality

For every metric and UTC date, supply `RecordingCoverage(day, metric, complete)`.
Complete coverage means that the caller has reconciled **all expected additive
records**. It must come from the recording workflow, not from the presence of one
measurement or from an assumed exercise schedule. `complete=False`, or no coverage
entry, leaves the day unknown even when a subtotal is available. An empty confirmed
complete day is an explicit zero; an empty unconfirmed day is `null`.

No interpolation, missing-day filling, scaling by wear time, or retrospective
zero-filling is performed. One missing metric does not invalidate the other's
observations. Partial UTC days remain descriptive and never receive daily target or
baseline classifications.

The module consumes `DataQuality` attached to measurements and optionally to daily
coverage. This is the integration point for the future quality engine:

| Input quality | Behavior |
| --- | --- |
| Missing or `not_assessed`, with no contradictory flags | Retain values; complete coverage can support comparisons; explicitly report unassessed quality |
| `acceptable` | Eligible if coverage and integrity checks also pass |
| `degraded` | Retain a descriptive subtotal; withhold comparisons |
| `unusable` | Exclude the value and leave the affected recording incomplete |
| Sensor-range, artifact or duplicate flag | Exclude the affected value |
| Missing/insufficient-sample flag or completeness below 1 | Withhold comparisons even if status says acceptable |

Input quality scores are not averaged or thresholded. Output scores remain `null`.
Output completeness is the fraction of confirmed complete **usable UTC metric-days**
(per-metric days on findings), not a reconstructed sensor-sample completeness score.
The output quality identifies this module as the producer of that coverage rollup;
it does not claim that the unfinished quality engine ran. Input quality flags and
notes are propagated. Recording quality and activity review status remain separate.

Identical repeated measurement IDs are safely collapsed and flagged, without losing
a usable original. Conflicting repeated IDs are rejected. Different IDs with
overlapping intervals or coincident points for the same metric are ambiguous:
all members of a connected overlap group are excluded. Touching half-open intervals
do not overlap. Negative activity values are excluded as invalid inputs; they are
not assigned a clinical or device-range threshold.

Intervals crossing UTC midnight or an evaluation boundary cannot be reliably split
from a single aggregate value. They are excluded from daily/weekly allocation and
affected days are marked incomplete. Whole cross-midnight session observations can
remain visible in session detail. An interval ending exactly at midnight belongs to
the preceding date. Producers should supply separate validated contributions for
each date when possible. No uniform exercise or energy rate is assumed.
If an instantaneous record is explicitly linked to a closed session, known session
boundaries also prevent allocation across midnight or evaluation boundaries.
Explicit per-date measurement intervals can still be allocated independently.

Finite representable subtotals are retained. Overflowing sums become `null` and
ineligible. Means avoid overflow of the intermediate sum when possible; undefined
or unrepresentable relative changes are `null`, never NaN or infinity.

## Targets, mission context and rest

`ActivityMetricPolicy` has optional `daily_target`, `weekly_target`,
`baseline_absolute_tolerance` and `baseline_relative_tolerance`. All are nonnegative
finite numbers. Targets and absolute tolerances use the metric's canonical unit;
relative tolerances are dimensionless. There are **no default exercise targets or
baseline deviation tolerances**.

Targets are personal minimums: complete, usable total `>= target` is `met`;
total `< target` is `missed`. Incomplete or degraded recording is `unknown`, even
when the known subtotal already exceeds a target. No configured target is
`not_configured`. These results describe adherence to a supplied plan.

`ActivityDayPlan` supplies explicit `planned_rest`, `comparisons_enabled`, optional
daily target overrides, and contextual notes. Rest suspends daily targets, baseline
comparisons and daily reduction runs. An operational exception suspends comparisons
without deleting recorded observations. Equipment maintenance, mission operations,
recovery periods and plan changes must be supplied by the caller; they are never
inferred from low activity. Phase labels alone do not set an exercise prescription.
Caller context notes are included in the shared evaluation summary.

Weeks start Monday at 00:00 UTC and end the following Monday. Weekly totals include
known activity on rest days. A weekly target requires all seven dates to have
complete usable recording, at least one non-rest date, and no suspended operational
date. Partial weeks and weeks with missing rest-day records remain unknown; targets
are never prorated. The caller must supply a weekly target that already reflects
the mission schedule. All-rest weeks and operationally suspended weeks have
`not_applicable` weekly targets.

## Personal baselines and unusual deviations

The module consumes `PersonalBaseline`; it does not construct, establish, update or
relabel baselines. `DailyBaselineReference` requires explicit
`comparison_basis="complete_active_day_total"` and a `comparable` confirmation.
That confirmation certifies compatible device/protocol, active-energy definition,
aggregation and active-day context. A session-duration baseline is not a baseline
of daily total duration. The shared baseline model alone cannot express that
distinction, hence the local adapter.

Eligible baselines must be established, belong to the crew member and metric, match
the known mission phase, contain at least one sample and a nonnegative daily-total
mean, and have a positive historical reference window ending no later than the
evaluation start. Computation must not precede the baseline's reference end or
follow `evaluated_at`. Degraded, unusable, flagged or incomplete baseline quality
prevents use. Missing quality remains explicitly unassessed. Of eligible references,
the latest `(window_end, computed_at, baseline_id)` is chosen deterministically.
Rejected references carry reasons. No arbitrary sample minimum or expiration age
is invented; establishment and validity remain the baseline producer's responsibility.

The shared finding's `observed_value` is the arithmetic mean of complete usable
active-day totals in the requested window. Its `baseline_value` is the selected
baseline mean. Signed deviations are:

```text
absolute_deviation = observed_mean - baseline_mean
relative_deviation = absolute_deviation / baseline_mean   (only if baseline_mean > 0)
```

Each eligible **individual day** is also checked against the selected baseline.
A strict exceedance of either configured absolute or relative tolerance prompts
review, in either direction. Equality does not. With a zero baseline only an
absolute tolerance can classify an unusual deviation; relative deviations remain
undefined. Tolerances are operational settings, not medical thresholds. No standard
deviation rule, population cutoff, significance level, or unvalidated default is
introduced. A baseline without tolerances still supplies descriptive deviations.
Daily exceptions remain visible even when positive and negative deviations cancel
in the window mean.

## Reductions and status mapping

Daily and weekly reports attach signed changes from the previous consecutive
eligible period. Reduction detection finds maximal runs of **strictly decreasing**
totals. The default `reduction_run_length=3` is a descriptive design convention:
three observations provide two successive falls. It is configurable, has no medical
meaning and is not a statistical test. No minimum fall magnitude is presumed.

Missing/partial/low-quality periods, planned rest, operational exceptions and daily
target changes break daily runs. Weekly runs require consecutive complete usable
weeks with identical weekly targets, daily target patterns and rest/exception
schedules. Changes are not computed across those breaks. A run can prompt attention
without an absolute target or historical baseline, since it only describes change.
Energy and duration runs are evaluated independently.

| Shared status | Module meaning |
| --- | --- |
| `attention` | At least one confirmed target miss, configured unusual daily deviation or progressive reduction; a person should review the records and context |
| `insufficient_data` | No confirmed review signal, but applicable periods are incomplete/unusable, or no applicable configured target/baseline tolerance can support assessment |
| `nominal` | At least one configured comparison was possible, applicable recording was usable, and no review signal was found |
| `alert` | Never produced: this module has no validated basis for a medical escalation threshold |

Overall status gives confirmed `attention` precedence, then `insufficient_data`, then
`nominal`. Attention in one usable period can coexist with unknown periods. A complete
duration assessment cannot make an unrecorded energy metric nominal. A fully rested
or suspended window cannot establish nominal activity. Existing physiological status
labels are used only to carry explainable activity review signals; none establishes
health, safety, countermeasure effectiveness or exercise adequacy.

## Simulation and verification

Run from `backend/`:

```bash
python -m app.domains.physical_activity.demo
python -m app.domains.physical_activity.demo --full
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m scripts.export_schemas --check
```

The five deterministic scenarios show target adherence, missed targets with
progressive reductions, rest with an operational exception, missing/degraded
records, and observations without baselines or targets. Every measurement uses
`source="simulated"`; crew, device, session and baseline identifiers are synthetic.
Baseline statistics, quality examples, targets and tolerances are fabricated fixture
values, not scientific recommendations or output from the unfinished engines.
The command labels both its JSON envelope and each scenario as simulated. Any
evaluation containing simulated measurements labels its summary and every finding
`SIMULATED DATA`. Keep simulated records separate from operational data stores.

Tests validate domain edge cases, independently test both metrics, exercise complete
and partial calendar periods, and validate simulated evaluation payloads against
both the existing Pydantic contract and committed JSON Schema. Existing architecture,
API and schema-sync tests continue to apply.

## Integration requirements and limitations

The ingestion adapter must reconcile IDs and devices, convert counters and units,
provide authoritative per-metric coverage, and link session metadata. The mission
adapter must split evaluations at mission-phase boundaries and provide rest and
exception schedules. Use separate windows or disable comparisons when device,
protocol, exercise regime or baseline context changes. Day target overrides alone
do not establish that a historical baseline remains comparable. Target provenance,
baseline validity and acquisition comparability require mission-team review.

A future quality engine can populate measurement/coverage `DataQuality`. A future
baseline engine can supply established daily-total baselines through
`DailyBaselineReference`. Neither engine is called or mocked by production code.
No persistence, automatic scheduling, ingestion endpoint or public route is added;
those integration layers remain owned by their respective components.

Duration and active kcal do not encode exercise modality, mechanical loading,
intensity, resistance repetitions, aerobic capacity, nutrition, injury or adherence
to an entire mission countermeasure prescription. Active kcal is not total daily
energy expenditure or a nutritional energy-balance measurement. Device and protocol
changes can dominate apparent trends. The algorithm cannot identify undocumented
cumulative counters, distinguish all duplicate sensors, establish real-world
recording completeness, or validate a producer's baseline claims.

There is no causal attribution, noise model, seasonal/mission adaptation model,
false-positive calibration, predictive validity or flight validation. Tiny decreases
can form a descriptive run; results require review in context. UTC calendar days may
differ from crew sleep/work cycles. Cross-midnight allocation and strict complete-week
requirements can reduce sensitivity. These are conservative, explicit limitations.

## Scientific context

NASA describes exercise as a countermeasure whose physiological context varies with
the individual and mission. This motivates caller-supplied plans and compatible
personal references; it does not validate this module's detection rules or provide
its numeric settings. See [NASA OCHMO-TB-031, Exercise Overview](https://www.nasa.gov/ochmo-tb-031-exercise-overview-2/).

Shcherbina et al. evaluated wrist-device energy-expenditure estimates against indirect
calorimetry in a terrestrial study and found limitations in their accuracy. This
supports treating device estimates cautiously; it does not establish any spaceflight
error bound. See [Accuracy in Wrist-Worn, Sensor-Based Measurements of Heart Rate and Energy Expenditure in a Diverse Cohort (2017)](https://pubmed.ncbi.nlm.nih.gov/28538708/).

The sums, means, configurable comparisons, calendar rules and reduction-run convention
above are transparent implementation choices, not clinical algorithms derived from
these sources.
