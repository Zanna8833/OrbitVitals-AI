# Cross-domain algorithms

Scientific code shared by every health domain. It is pure Python: it imports the
contract models from `app.models` and nothing from the web layer.

| Module | Purpose | Output contract |
| --- | --- | --- |
| `data_quality.py` | Data Quality Engine: how far can the data be trusted? | `DataQuality` |
| `personal_baseline.py` | Personal Baseline Engine: reference statistics per crew member, metric and mission phase | `PersonalBaseline` |
| `robust_statistics.py` | Mean, standard deviation, median, MAD and modified z-score | `BaselineStatistics` |

Deviation evaluation (`EvaluationResult`) is not implemented.

OrbitVitals AI is a research prototype, not a medical device. Nothing in this package is
a clinical threshold, a reference range or a diagnosis, and no algorithm here has been
validated against real data.

## Principles

- **Data quality is not health status.** The Data Quality Engine only produces
  `DataQuality`. It never flags a value for being high, low or unusual: such a value may
  be exactly what happened, and judging it is a physiological question.
- **Nothing is invented.** Device ranges, sampling protocols and the criterion for an
  established baseline are settings without a default, because this repository holds no
  source for them. The remaining settings default to their strictest value.
- **Deterministic.** The assessment time is an argument, results do not depend on the
  order of the input, and identifiers are derived from the content.
- **Explainable.** Every status comes with counts and reasons in `DataQuality.notes`.

## Data Quality Engine

```python
from datetime import UTC, datetime
from app.algorithms.data_quality import assess_measurements, assess_window

now = datetime.now(UTC)
assessed = assess_measurements(batch, assessed_at=now)  # copies with data_quality filled in
quality = assess_window(
    batch,
    crew_member_id="crew-001",
    metric=MetricType.HEART_RATE,
    window_start=start,
    window_end=end,
    assessed_at=now,
)
```

Pass the whole batch: duplicates and paired metrics can only be checked across records.

### Checks on one measurement

| Finding | Flag | Status |
| --- | --- | --- |
| Value impossible by the definition of the metric: negative count, duration, amount or mass; percentage outside 0 to 100 | `signal_artifact` | `unusable` |
| Value outside the measuring range documented for the device | `out_of_sensor_range` | `degraded` |
| Sleep or exercise duration longer than its observation interval | `signal_artifact` | `unusable` |
| Diastolic pressure above the systolic pressure of the same reading | `signal_artifact` | `unusable`, both values |
| Redundant copy of an observation | `duplicate` | `unusable`; one copy is retained and unaffected |
| Records of one observation with different values | `duplicate` | `unusable`, all of them |
| Same `measurement_id`, different content | `duplicate` | `unusable`, all of them |
| Timestamp later than the assessment time | none | `unusable` |

Two records describe the same observation when they share crew member, metric,
`measured_at`, `interval_end`, source and device. Readings taken at the same instant by
different devices are distinct observations.

`acceptable` means that no issue was found by the checks that could be applied. It does
not mean that the measurement was validated.

### Checks on a window

A window covers one metric of one crew member over `[window_start, window_end)`.

| Field | Definition |
| --- | --- |
| `completeness` | Distinct observation times present, divided by the observations expected at the configured sampling interval, capped at 1. Null without a configured interval |
| `score` | Observation times with a record that passed every check, divided by the expected observations. A descriptive proportion defined here, not a validated quality index |
| `status` | `unusable` with fewer usable values than the minimum; `acceptable` when completeness and the share of flagged records are within the limits; otherwise `degraded` |
| `flags` | Flags of the records, plus `missing_data` when completeness is below 1 and `insufficient_samples` below the minimum |

### Settings (`DataQualityConfig`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `sensor_ranges` | none | Measuring range per `device_id` and metric. Each `SensorRange` must cite the device documentation in `source` |
| `expected_intervals` | none | Expected time between two observations of a metric |
| `clock_tolerance` | 0 | How far after the assessment time a timestamp may lie |
| `interval_tolerance` | 0 | How far a duration may exceed its observation interval |
| `minimum_usable_samples` | 1 | Usable values a window needs |
| `acceptable_min_completeness` | 1.0 | Completeness needed for `acceptable` |
| `acceptable_max_flagged_fraction` | 0.0 | Share of flagged records allowed for `acceptable` |

## Personal Baseline Engine

```python
from app.algorithms.personal_baseline import build_baseline, build_baselines

baselines = build_baselines(batch, mission_phases, computed_at=now)
baseline = build_baseline(
    batch,
    mission_phases,
    crew_member_id="crew-001",
    metric=MetricType.HEART_RATE,
    mission_phase=MissionPhaseType.IN_FLIGHT,
    computed_at=now,
)  # None when the phase has no reference window
```

How a baseline is built:

1. Every measurement is assessed by the Data Quality Engine. Only admitted measurements
   enter the baseline: by default those with the status `acceptable`.
2. A measurement belongs to the phase that contains its `measured_at`. A phase includes
   its start and excludes its end. An ongoing phase ends at `computed_at`. Entries of the
   same phase are pooled. The window can be narrowed with `reference_start` and
   `reference_end`.
3. Potential outliers are identified with the modified z-score. By default they are
   reported and kept. The screening runs once and is skipped when the MAD is zero.
4. The statistics are the mean, the sample standard deviation (n - 1), the median, the
   MAD (not rescaled), the minimum and the maximum of the values used.

| Status | Rule |
| --- | --- |
| `insufficient_data` | Fewer values than `minimum_samples`. Every statistic is null |
| `established` | Every configured criterion is met and the values are not all identical |
| `provisional` | Every other case |

With the default settings no baseline is ever `established`: the criterion must be
configured by the team, with its source. `established` means that the configured
criteria are met. It does not mean that the baseline was validated.

A phase without usable measurements still yields a baseline, with `insufficient_data`,
so that missing observations stay visible.

### Settings (`BaselineConfig`)

| Setting | Default | Meaning |
| --- | --- | --- |
| `quality` | `DataQualityConfig()` | Settings applied to the reference data |
| `admitted_quality` | `acceptable` | Quality statuses admitted to a baseline; `degraded` can be added |
| `minimum_samples` | 2 | Values needed to report statistics. Two is the smallest count with a standard deviation |
| `established_min_samples` | none | Values needed for `established` |
| `established_min_span` | none | Time between the first and the last value needed for `established` |
| `outlier_cutoff` | 3.5 | Absolute modified z-score of a potential outlier; `None` disables the screening |
| `outlier_handling` | `report` | `report` keeps potential outliers, `exclude` leaves them out |

## Sources

- Modified z-score, factor 0.6745 and cut-off 3.5: Iglewicz B, Hoaglin DC. *How to
  Detect and Handle Outliers*. ASQC Basic References in Quality Control, vol. 16. ASQC
  Quality Press, 1993. Quoted in the NIST/SEMATECH *e-Handbook of Statistical Methods*,
  section 1.3.5.17.
- Definition bounds: the definitions in `app.models.metrics`. A count, a duration, an
  amount or a mass cannot be negative; a percentage share lies between 0 and 100.
- Systolic and diastolic pressure: the highest and the lowest arterial pressure of a
  heartbeat, so the second cannot exceed the first.

## Decisions open to review

These are choices made in this package, not facts taken from a source.

- A contradiction that corrupts the value maps to `signal_artifact`. The contract has no
  flag for an inconsistent timestamp, so that case sets none and explains itself in
  `notes`.
- A value outside the sensor range is `degraded`, not `unusable`: it may be real, but its
  accuracy is not documented.
- `score` is the proportion defined above. It has no external source. If the team
  prefers a null score, remove it in `summarize_series`.
- Potential outliers are kept by default.
- A baseline whose values are all identical stays `provisional`.
- `PersonalBaseline` has no text field, so the reasons behind a baseline are written in
  `data_quality.notes`.
- `baseline_id` is a UUID derived from the content of the baseline.

## Limitations

- Not validated against real data. Tests use synthetic data only.
- No sensor range is configured, so `out_of_sensor_range` is never raised until the
  ranges of the real devices are provided.
- Checks that would need an unsourced threshold are not implemented: flat-line or stuck
  sensors, implausible rates of change, disagreement between two devices.
- Completeness assumes a regular sampling interval per metric, all devices pooled.
- A measurement is assigned to a phase by its `measured_at`, even when its interval
  crosses a phase boundary.
- A baseline describes a whole phase. Adaptation within a phase is not modelled; use
  `reference_start` and `reference_end` to describe part of it.
- The mean and the standard deviation are sensitive to outliers that are kept. Prefer the
  median and the MAD when potential outliers are reported.
- A MAD of zero leaves MAD-based standardised deviations undefined. The engine reports
  it; the future evaluation algorithm must handle it.

## Demonstration and tests

```bash
python -m scripts.demo_quality_baseline          # synthetic scenarios, readable summary
python -m scripts.demo_quality_baseline --json   # the same results as contract JSON
pytest tests/algorithms
```

Every value in the demonstration is synthetic and labelled `source: "simulated"`.
