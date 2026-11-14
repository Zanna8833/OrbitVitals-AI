# Sleep Monitoring and Trend Analysis

This module describes individual sleep observations and screens multi-day windows for
configured statistical patterns. It supports the existing `sleep_duration` (`min`)
and `sleep_efficiency` (`%`) metrics. It is a research prototype with no clinical or
spaceflight validation. It does not diagnose sleep disorders, define adequate sleep,
or recommend treatment.

All functions are deterministic and perform no network, storage, clock or web-framework
operations. The implementation uses the Python standard library and the existing
Pydantic contracts. No Data Quality or Personal Baseline engine is required or imported.
No HTTP endpoint, shared model or generated schema is added.

## Entry points

Import these functions and types from `app.domains.sleep`:

| Entry point | Purpose | Output |
| --- | --- | --- |
| `analyze_sleep_observation` | Describe a completed observation; optionally compare a supplied prior personal baseline | Existing `MetricFinding` |
| `analyze_sleep_trends` | Select nightly values and compute transparent trend diagnostics for both metrics | Two internal `SleepTrend` dataclasses, duration then efficiency |
| `evaluate_sleep_window` | Adapt trend findings and optional reference comparisons to the unchanged contracts | Existing `EvaluationResult` with two findings |
| `SleepConfig`, `MetricThresholds` | Supply the complete, explicit screening policy | Frozen configuration dataclasses |

The caller supplies crew and evaluation identifiers, timezone-aware window bounds,
`evaluated_at` and a configuration. Identifiers are never parsed. The evaluation window
must have positive length and end no later than `evaluated_at`. Trend-only analysis
treats the supplied window end as a completed observation horizon. Evaluation timestamps
are normalized to UTC. Measurement units are validated by `PhysiologicalMeasurement`;
ingestion must perform any unit conversion.

```python
from app.domains.sleep import analyze_sleep_observation, analyze_sleep_trends, evaluate_sleep_window
from app.domains.sleep.demo import demonstration_config, demonstration_scenarios

# Illustrative fixtures only. Supply a separately reviewed policy for any other use.
config = demonstration_config()
scenario = demonstration_scenarios()[1]

trends = analyze_sleep_trends(
    scenario.measurements,
    crew_member_id="synthetic-crew",
    window_start=scenario.window_start,
    window_end=scenario.window_end,
    config=config,
)
assert trends[0].slope_per_day == -20.0

finding = analyze_sleep_observation(
    scenario.measurements[0],
    evaluated_at=scenario.window_end,
    config=config,
)
# No baseline was supplied: the individual value is descriptive, with insufficient_data.

result = evaluate_sleep_window(
    scenario.measurements,
    evaluation_id="synthetic-evaluation",
    crew_member_id="synthetic-crew",
    window_start=scenario.window_start,
    window_end=scenario.window_end,
    evaluated_at=scenario.window_end,
    config=config,
)
payload = result.model_dump(mode="json")
```

`SleepTrend` exposes the selected observations and their identifiers, expected and
missing night dates, coverage, longest missing run, actual elapsed span, median,
signed slope, fitted change, decreasing-transition fraction, signal, insufficiency
reasons and excluded record identifiers/reasons. These dataclasses are internal domain
outputs, not additions to the published API. Contract findings carry the same main
diagnostics in their explanations; slope values are never put into baseline fields.

## Windows and nights

The following rules are explicit project design decisions, not biological assumptions
established by a study:

- Windows are half-open: `[window_start, window_end)`, based on `measured_at`.
  An interval ending exactly at the window end is complete. An observation starting
  at the end is outside. Intervals crossing either window edge are excluded, never
  clipped, prorated or split.
- A night is a 24-hour UTC bucket starting at `night_start_hour_utc`. Its label is
  the UTC date of that boundary. The observation's **start** assigns the bucket,
  including intervals crossing midnight. UTC offsets are normalized before grouping.
  The configurable boundary is an operational convention, not an inferred circadian
  or local sleep schedule.
- Only buckets fully enclosed by the requested window are eligible. Partially
  observed first/last buckets are excluded even if a completed record is present.
  This conservative rule avoids judging incomplete exposure as missing or short
  sleep. A current bucket becomes eligible at its next boundary; an isolated
  completed observation can still be analyzed through `analyze_sleep_observation`.
- Exactly one eligible record per metric per bucket is required. Identical repeats
  of the same identifier count once. Conflicting contents for one identifier raise
  `ValueError`. Multiple distinct records in a bucket make that metric/night
  ambiguous and exclude all of them; the module cannot distinguish naps, revisions,
  or multiple devices. It does not sum durations or average efficiency ratios.
- Overlapping intervals in different buckets exclude both records for that metric.
  Duration and efficiency are analyzed independently; they need not be paired, and
  neither is reconstructed from the other. A record without `interval_end` is a
  completed point summary at `measured_at`; its acquisition completeness and correct
  sleep-period assignment remain the producer's responsibility.
- Missing, unusable, invalid and ambiguous nights remain absent. No interpolation,
  zero filling, forward filling or resampling occurs. A recorded duration of zero
  is a value, never a missing-data sentinel. Percentages of 0 and 100 are valid.

Basic domain guards enforce only metric definitions: duration is non-negative,
efficiency is between 0 and 100, an explicitly supplied interval has positive length,
and total sleep minutes cannot exceed that interval's minutes. These are mathematical
identities from the metric catalog, not sensor ranges or clinical limits. Rejection
reasons belong to this module's selection diagnostics and do not pretend to be Data
Quality engine assessments. Non-finite model inputs are already rejected by Pydantic;
non-finite trend arithmetic suppresses classification rather than emitting invalid JSON.

Mixed crew members and unsupported metrics raise `ValueError` to prevent accidental
cross-person or cross-domain analysis. Out-of-window records are excluded and listed.
Input ordering does not affect the results, and the input contracts are not mutated.

## Configuration policy

There are **no default detection thresholds**. The caller must supply every field of
`SleepConfig` and `MetricThresholds`, including a policy identifier. This section is
the source of the module's engineering policy definitions; it is not evidence for
any particular numerical setting. The only ready-made numbers are explicitly labelled
synthetic demonstration fixtures. Clinical threshold logic is intentionally unimplemented
because the repository supplies no evidence to justify it.

| Parameter | Definition |
| --- | --- |
| `minimum_nights` | Minimum included nights for each metric, at least three to observe more than one transition |
| `minimum_coverage` | Minimum included-night count divided by fully enclosed bucket count, in `(0, 1]` |
| `minimum_span_days` | Minimum elapsed UTC days between the first and last included starts, strictly positive |
| `maximum_consecutive_missing_nights` | Maximum run of absent buckets, including leading/trailing gaps; zero requires full coverage |
| `minimum_decreasing_fraction` | Minimum fraction of strictly decreasing adjacent observed transitions for progressive duration reduction, in `(0, 1]` |
| `night_start_hour_utc` | Operational boundary hour, an integer from 0 through 23 |
| `minimum_slope_per_day` | Minimum absolute slope, in min/day or percentage points/day, strictly positive |
| `minimum_total_change` | Minimum absolute fitted change over the observed span, in minutes or percentage points, strictly positive |
| `minimum_observation_deviation` | Minimum two-sided absolute difference from a supplied baseline, in minutes or percentage points, strictly positive |

All sufficiency gates must pass for a metric before a trend or window comparison
can assign `attention` or `nominal`. Equality passes minimum and maximum gates.
Coverage has no denominator when there is no complete bucket; it is then `None` and
the trend is insufficient. Coverage is per metric, not pooled across duration and
efficiency. A minimum count of three is not a claim of adequate statistical power.

The evaluation summary serializes the complete configuration, including `policy_id`,
for traceability within the existing string field. Callers should also persist and
version the policy beside the evaluation. Baseline comparison uses the same absolute
effect-size threshold for an individual value or the window's median; this is a
deliberate simple policy, not a calibrated probability model.

## Detection rules

For observed start times `t_i` in elapsed UTC days and nightly values `y_i`, the
Theil-Sen slope is `median((y_j - y_i) / (t_j - t_i))` for all `i < j`. The source
is [NIST's Theil-Sen reference](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/ts_fit.htm),
which cites Sen (1968). This standard descriptive estimator uses actual time, so
a two-day gap does not become a one-day step. The median uses the ordinary middle
value or mean of the middle two, as defined in the
[Python statistics documentation](https://docs.python.org/3.11/library/statistics.html#statistics.median).
No SciPy dependency is needed.

The following are project screening rules, separately documented here so they are
not mistaken for conclusions from those statistical references:

1. Fitted change is `slope * (last_start - first_start)` in elapsed days. It describes
   the fitted line over the observed span, not the literal last-minus-first value.
2. Progressive duration reduction requires a negative slope, both configured
   effect-size gates, and the configured fraction of observed adjacent transitions
   that strictly decrease. Ties count in the denominator but do not count as
   reductions. A transition across missing nights compares its two observed endpoints;
   it says nothing about the unobserved nights between them.
3. Efficiency change requires both effect-size gates and may be increasing or
   decreasing. An increase is a change to interpret, not automatically an improvement
   or a danger. Efficiency differences are **percentage points**; they are not
   relative percentage changes. Flat or subthreshold slopes have no trend signal.
4. An isolated observation can only be compared if a usable external personal baseline
   is supplied. The signed absolute deviation and dimensionless relative deviation
   follow `MetricFinding`'s definitions. A zero reference leaves relative deviation
   undefined (`None`); an unrepresentable finite-input ratio is also omitted.

This is not a significance test, change-point detector or sleep-stage analysis.
No p-values, confidence intervals, risk scores or diagnoses are produced.

## Status mapping

The existing enum is reused without changing its schema. In this module, labels have
an explicitly limited statistical meaning:

- `attention`: a configured trend or two-sided baseline effect-size gate was met
  with sufficient data. It requests human interpretation.
- `nominal`: sufficient window data and no configured signal, or an individual
  observation inside the configured baseline deviation gate. It does not establish
  adequate sleep, physiological normality or safety.
- `insufficient_data`: a window failed any sufficiency gate, supplied window/metric
  quality is unusable, or an individual observation cannot be compared with a usable
  reference. Raw descriptive medians may still be present.
- `alert`: never emitted; no evidence supports a clinical escalation rule.

A window can detect statistical trends with no personal baseline: baseline and
deviation fields remain `None`, and explanations explicitly say no personal-reference
comparison was made. This extends the contract's baseline-oriented descriptive intent
without inventing a baseline or changing a field. Consumers must display the explanation
and algorithm identity and must not treat the enum as a clinical conclusion. When a
trend window is insufficient, any available baseline deviation is descriptive only.

At domain level, any metric with `attention` takes precedence. Otherwise any
`insufficient_data` metric makes the domain insufficient; only two evaluable metrics
with no signal produce `nominal`. Each metric's completeness stays visible even when
the other metric needs attention.

## Integration requirements

### Data Quality integration

Measurement `data_quality.status == unusable` excludes that record. Degraded and
unassessed records remain eligible and their statuses are counted in the default
per-metric quality notes. No sensor noise filter, sensor-range rule, artifact detection,
quality score or quality engine flag is implemented here.

`evaluate_sleep_window` accepts optional `data_quality` for the whole window and
`metric_data_quality` keyed by metric. Supplied objects are preserved by deep copy;
an unusable window suppresses both metric classifications, while an unusable metric
assessment suppresses only that metric. Supplied window assessments are not silently
copied onto metrics with different coverage. Without an applicable supplied assessment,
quality is `not_assessed`, with no score, completeness, flags, algorithm or assessment
timestamp inferred. The single-observation adapter preserves the record's assessment
or `None`. Selection coverage remains separate from formal Data Quality completeness.

The future quality-engine owner must agree sample eligibility, expected acquisition
cadence, assessment scope and provenance with the caller. The caller must supply
assessments for the exact evaluated population and time horizon, and decide how to
handle degraded records operationally. This module does not import that implementation.

### Baseline integration

The caller may supply existing `PersonalBaseline` contracts keyed by metric, or a
single baseline for an individual observation. The adapter requires a matching crew
member and metric (mismatches raise `ValueError`), `established` status, nonzero sample
count, quality other than unusable, a usable median or fallback mean, a reference
window ending at or before the target start, and `computed_at <= evaluated_at`.
It rejects future/overlapping references to prevent look-ahead or self-comparison.
Provisional/insufficient references are described but not used. No baseline is built,
updated or reclassified by this module. Zero reference values are supported.

The baseline owner and caller must decide establishment criteria, reference age,
phase/device compatibility, update schedules, and which prior baseline to select.
Mission phase is passed through as metadata; this module imposes no cross-phase
biological equivalence or freshness rule. A matching mission phase is not proof of
comparability. The median/mean preference and two-sided effect gate are explicit
adapter choices to review before integration.

### Ingestion and API integration

Ingestion must identify one primary sleep-period summary per metric per operational
night, resolve revisions/device conflicts, normalize units, and agree whether instant
summaries are timestamped at the sleep-period start. If producers timestamp summaries
at wake time or use a different sleep-day convention, they must adapt before analysis.
Split sleep, naps and rotating mission schedules need an agreed representation; the
module cannot infer it from the existing contracts. The API owner can call the pure
functions from a thin route when triggering and persistence are agreed; no route or
public API change is included here. No RAG dependency is introduced.

## Synthetic demonstrations

From `backend/`, run `python -m app.domains.sleep.demo`. It prints JSON containing
input measurements, individual descriptive findings and contract-compatible evaluations.
Every generated measurement uses `source: "simulated"`. Dates, levels, nine-hour
periods, linear ramps, missing-night positions and policy values are hand-authored
engineering fixtures; they are not measured astronaut data or recommended targets.

The demonstration policy uses four nights, 0.6 coverage, three elapsed days, at most
two consecutive missing nights, a 0.75 decreasing-transition fraction, and a 12:00 UTC
boundary. Duration gates are 5 min/day, 30 min fitted change and 60 min baseline
deviation; efficiency gates are 0.5 percentage points/day, 3 percentage points fitted
change and 5 percentage points baseline deviation. These choices exist only to make
the examples visibly exercise the rules. No clinical source or validation is claimed.

| Scenario | Constructed behavior |
| --- | --- |
| `stable` | Constant duration and efficiency; no configured signal |
| `duration_reduction` | Duration decreases 20 minutes per day |
| `efficiency_decrease` | Efficiency decreases two percentage points per day |
| `efficiency_increase` | Efficiency increases two percentage points per day |
| `missing_nights` | Two isolated missing nights; preserve elapsed-time slope |
| `insufficient_data` | Two observed nights; classification withheld |
| `irregular_timestamps` | Variable start hours along the same elapsed-time duration ramp |
| `isolated_outlier` | One lower duration among constant nights; no progressive trend |
| `partial_window` | Ignore partial edge buckets; analyze five fully enclosed nights |

## Scientific limitations

The method describes an approximately linear tendency over the chosen window.
Median pairwise slopes reduce the influence of isolated extreme points but do not
guarantee resistance to all artifacts, step changes, clustering or repeated errors.
The progression gate is a transparent heuristic; it is not a validated clinical
definition. Results depend on window length, operational boundary and caller policy.
Very short windows and correlated nightly observations do not support claims of
statistical significance. There is no calibration for multiple windows or metrics.

Missingness may be informative, and passing coverage gates does not establish absence
of bias. Sensor accuracy, medication, workload, illness, circadian shifts and mission
context are not modeled. Efficiency alone cannot distinguish a change in total sleep
from a change in time in bed. Uniformly low or high values may have no trend signal
and cannot be labelled healthy. An isolated abrupt change may require individual
baseline review; this module does not promise to detect every change pattern.

The algorithm is intended for short nightly monitoring windows: computing every
pairwise slope costs quadratic time and memory. Callers must bound window sizes for
their deployment. Longitudinal prediction, sleep debt, stage estimation, clinical
thresholds, medical recommendations and proof of safety remain unimplemented.
The tests verify deterministic software behavior on synthetic inputs, not clinical
performance or suitability for a space mission.
