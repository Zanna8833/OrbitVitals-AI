"""Data Quality Engine.

Answers one question: how far can a measurement, or a window of measurements, be trusted
as data? The answer is the `DataQuality` contract. The engine never answers a
physiological question: `DataQuality` describes the data and never the crew member, and
the physiological status is reported elsewhere, by `EvaluationStatus`.

Checks on a single measurement, with the flag and the status they lead to:

- Value impossible by the definition of its metric (a negative duration, a percentage
  above 100): `signal_artifact`, `unusable`.
- Value outside the measuring range documented for its device: `out_of_sensor_range`,
  `degraded`. Ranges are configuration: none is built in.
- Duration longer than the observation interval it refers to: `signal_artifact`,
  `unusable`.
- Diastolic blood pressure above the systolic blood pressure of the same reading:
  `signal_artifact`, `unusable`, on both values.
- Redundant copy of an observation: `duplicate`, `unusable`. One copy is retained and is
  not affected.
- Records of one observation that disagree on the value, or records that share a
  `measurement_id` but not their content: `duplicate`, `unusable`, on all of them.
- Timestamp later than the assessment time: `unusable`. The contract has no flag for
  this, so none is set and the reason is given in `notes`.

Checks on a window of one metric of one crew member: completeness against an expected
sampling interval, when one is configured, and the share of observations that passed
every check.

What the engine deliberately does not do:

- It never flags a value for being high, low, unusual or far from a baseline. Such a
  value may be exactly what happened, and judging it is a physiological question.
- It contains no clinical threshold and no reference range.
- `acceptable` means that no issue was found by the checks that could be applied. It
  does not mean that the measurement was validated.

Every function is pure and deterministic. The assessment time is an argument, and the
assessment of a record does not depend on the order of the input.
"""

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from itertools import pairwise

from app.models import (
    AlgorithmInfo,
    DataQuality,
    MeasurementSource,
    MetricType,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)

ALGORITHM = AlgorithmInfo(name="data_quality", version="0.1.0")

# Half-open period of time: the start is included, the end is not.
Period = tuple[datetime, datetime]

_ZERO = timedelta(0)
_SECONDS_PER_MINUTE = 60.0

# Bounds that follow from the definition of a metric (see `app.models.metrics`), not from
# physiology: a count per unit of time, a duration, an amount or a mass cannot be
# negative, and a share expressed in percent lies between 0 and 100. A value outside
# these bounds cannot be an observation of the metric. The bounds are not clinical
# thresholds and say nothing about which values are healthy.
DEFINITION_BOUNDS: dict[MetricType, tuple[float | None, float | None]] = {
    MetricType.HEART_RATE: (0.0, None),  # beats per minute: a count per unit of time
    MetricType.HEART_RATE_VARIABILITY_RMSSD: (0.0, None),  # a root mean square
    MetricType.RESPIRATORY_RATE: (0.0, None),  # breaths per minute: a count per unit of time
    MetricType.BLOOD_OXYGEN_SATURATION: (0.0, 100.0),  # a share, in percent
    MetricType.SLEEP_DURATION: (0.0, None),  # a duration
    MetricType.SLEEP_EFFICIENCY: (0.0, 100.0),  # a share, in percent
    MetricType.EXERCISE_DURATION: (0.0, None),  # a duration
    MetricType.ACTIVE_ENERGY_EXPENDITURE: (0.0, None),  # an amount of energy expended
    MetricType.ENERGY_INTAKE: (0.0, None),  # an amount of energy taken in
    MetricType.PROTEIN_INTAKE: (0.0, None),  # an amount of mass
    MetricType.FLUID_INTAKE: (0.0, None),  # an amount of volume
    MetricType.BODY_MASS: (0.0, None),  # a mass
}

# Metrics that no definition bounds: a temperature in degrees Celsius and a pressure
# relative to the atmosphere may take either sign as numbers. Only the measuring range
# documented for a device can bound them.
METRICS_WITHOUT_DEFINITION_BOUND = frozenset(
    {
        MetricType.BODY_TEMPERATURE,
        MetricType.SYSTOLIC_BLOOD_PRESSURE,
        MetricType.DIASTOLIC_BLOOD_PRESSURE,
    }
)

# Metrics whose value is a duration, in minutes, spent inside the observation interval of
# the measurement (`measured_at` to `interval_end`). By definition such a value cannot be
# longer than the interval.
INTERVAL_BOUNDED_DURATIONS = frozenset({MetricType.SLEEP_DURATION, MetricType.EXERCISE_DURATION})


@dataclass(frozen=True)
class SensorRange:
    """Measuring range documented for one metric of one device, in the canonical unit.

    `source` cites the device documentation the range was taken from. It is required:
    a range without a source would be an invented threshold.
    """

    minimum: float
    maximum: float
    source: str

    def __post_init__(self) -> None:
        if not (math.isfinite(self.minimum) and math.isfinite(self.maximum)):
            raise ValueError("the bounds of a sensor range must be finite")
        if self.minimum > self.maximum:
            raise ValueError("the minimum of a sensor range must not exceed its maximum")
        if not self.source.strip():
            raise ValueError("a sensor range must cite the device documentation it comes from")


@dataclass(frozen=True)
class DataQualityConfig:
    """Settings of the Data Quality Engine.

    Nothing here is a clinical threshold. Device and protocol facts have no default
    because they are not known to this module:

    - `sensor_ranges`: documented measuring ranges, by `device_id` then by metric. A
      measurement without a configured range is not checked against one.
    - `expected_intervals`: expected time between two observations of a metric, as set by
      the acquisition protocol. Without it, completeness is not assessed.

    The remaining settings default to their strictest value, which is a natural boundary
    and not a threshold taken from the literature. Relax them only for a documented
    reason:

    - `clock_tolerance`: how far after the assessment time a timestamp may lie, to absorb
      clock differences between devices.
    - `interval_tolerance`: how far a duration may exceed its observation interval, to
      absorb the rounding of timestamps.
    - `minimum_usable_samples`: usable values a window needs in order not to be
      `unusable`.
    - `acceptable_min_completeness`: completeness a window needs to be `acceptable`.
    - `acceptable_max_flagged_fraction`: share of records with an issue that a window may
      contain and still be `acceptable`.
    """

    sensor_ranges: Mapping[str, Mapping[MetricType, SensorRange]] = field(default_factory=dict)
    expected_intervals: Mapping[MetricType, timedelta] = field(default_factory=dict)
    clock_tolerance: timedelta = _ZERO
    interval_tolerance: timedelta = _ZERO
    minimum_usable_samples: int = 1
    acceptable_min_completeness: float = 1.0
    acceptable_max_flagged_fraction: float = 0.0

    def __post_init__(self) -> None:
        for metric, interval in self.expected_intervals.items():
            if interval <= _ZERO:
                raise ValueError(f"the expected interval of {metric.value} must be positive")
        if self.clock_tolerance < _ZERO or self.interval_tolerance < _ZERO:
            raise ValueError("tolerances must not be negative")
        if self.minimum_usable_samples < 1:
            raise ValueError("minimum_usable_samples must be at least 1")
        for name in ("acceptable_min_completeness", "acceptable_max_flagged_fraction"):
            if not 0.0 <= getattr(self, name) <= 1.0:
                raise ValueError(f"{name} must lie between 0 and 1")


@dataclass(frozen=True)
class _Issue:
    """One finding about one record. `flag` is null when the contract has no fitting flag."""

    status: QualityStatus
    flag: QualityFlag | None
    note: str


def as_utc(value: datetime, name: str) -> datetime:
    """Return `value` in UTC. Raise `ValueError` when it carries no time zone."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must carry a time zone")
    return value.astimezone(UTC)


def format_duration(duration: timedelta) -> str:
    """Render a duration for a note, in the largest unit that divides it exactly."""
    seconds = duration.total_seconds()
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size and seconds % size == 0:
            return _plural(int(seconds // size), unit)
    return f"{seconds:g} seconds"


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def assess_measurements(
    measurements: Sequence[PhysiologicalMeasurement],
    *,
    assessed_at: datetime,
    config: DataQualityConfig | None = None,
) -> list[PhysiologicalMeasurement]:
    """Return a copy of every measurement with `data_quality` filled in, in input order.

    Pass the whole batch at once: duplicates and the consistency of paired metrics can
    only be seen across records. The batch may mix crew members and metrics.

    The assessment replaces any `data_quality` already attached. The input is not
    modified. `score` and `completeness` are null on a single measurement: they are
    defined for windows only.
    """
    config = config or DataQualityConfig()
    assessed_at = as_utc(assessed_at, "assessed_at")

    issues = [_own_issues(measurement, assessed_at, config) for measurement in measurements]
    _add_duplicate_issues(measurements, issues)
    _add_blood_pressure_issues(measurements, issues)

    return [
        measurement.model_copy(update={"data_quality": _measurement_quality(found, assessed_at)})
        for measurement, found in zip(measurements, issues, strict=True)
    ]


def assess_window(
    measurements: Sequence[PhysiologicalMeasurement],
    *,
    crew_member_id: str,
    metric: MetricType,
    window_start: datetime,
    window_end: datetime,
    assessed_at: datetime,
    config: DataQualityConfig | None = None,
) -> DataQuality:
    """Assess one metric of one crew member over the window `[window_start, window_end)`.

    `measurements` is the whole batch, as for `assess_measurements`: the records of the
    series are selected here, after every record has been assessed in its context.
    """
    config = config or DataQualityConfig()
    start = as_utc(window_start, "window_start")
    end = as_utc(window_end, "window_end")
    if end < start:
        raise ValueError("window_end must not be earlier than window_start")

    assessed = assess_measurements(measurements, assessed_at=assessed_at, config=config)
    series = [
        measurement
        for measurement in assessed
        if measurement.crew_member_id == crew_member_id
        and measurement.metric == metric
        and start <= measurement.measured_at < end
    ]
    return summarize_series(
        series, metric=metric, periods=[(start, end)], assessed_at=assessed_at, config=config
    )


def summarize_series(
    series: Sequence[PhysiologicalMeasurement],
    *,
    metric: MetricType,
    periods: Sequence[Period],
    assessed_at: datetime,
    config: DataQualityConfig | None = None,
    analysed_count: int | None = None,
    minimum_samples: int | None = None,
    remarks: Sequence[str] = (),
) -> DataQuality:
    """Summarize the quality of one series over `periods`.

    Building block of `assess_window`, also used by the baseline engine. `series` holds
    the records of one metric of one crew member that fall inside `periods`, as returned
    by `assess_measurements`.

    Definitions, all of them proportions without weights:

    - `completeness`: distinct observation times present, divided by the observations
      expected at the configured sampling interval, capped at 1. Samples are not expected
      after the assessment time. Null when no interval is configured or when the window
      is shorter than one interval.
    - `score`: observation times that have a record which passed every check, divided by
      the expected observations (or by the observation times present, when they are more
      or when no expectation exists). It is a descriptive proportion defined by this
      module, not a validated quality index. Null when there is nothing to count.
    - `status`: `unusable` when fewer values than `minimum_samples` can be analysed;
      `acceptable` when completeness and the share of records with an issue are within
      the configured limits; `degraded` otherwise.

    `analysed_count` is the number of values the caller will actually analyse. It
    defaults to the records that are not `unusable`. `minimum_samples` defaults to
    `config.minimum_usable_samples`. `remarks` are sentences appended to `notes`.
    """
    config = config or DataQualityConfig()
    assessed_at = as_utc(assessed_at, "assessed_at")
    for measurement in series:
        quality = measurement.data_quality
        if quality is None or quality.status is QualityStatus.NOT_ASSESSED:
            raise ValueError("summarize_series needs measurements returned by assess_measurements")

    statuses = Counter(measurement.data_quality.status for measurement in series)
    flag_counts = Counter(flag for measurement in series for flag in measurement.data_quality.flags)
    instants = {measurement.measured_at for measurement in series}
    acceptable_instants = {
        measurement.measured_at
        for measurement in series
        if measurement.data_quality.status is QualityStatus.ACCEPTABLE
    }

    # Samples are expected only in the part of the window that has already elapsed.
    elapsed = [
        (start, min(end, assessed_at)) for start, end in periods if start < min(end, assessed_at)
    ]
    interval = config.expected_intervals.get(metric)
    expected = (
        None if interval is None else sum((end - start) // interval for start, end in elapsed)
    )
    completeness = min(1.0, len(instants) / expected) if expected else None
    denominator = max(expected or 0, len(instants))
    score = len(acceptable_instants) / denominator if denominator else None

    usable = (
        len(series) - statuses[QualityStatus.UNUSABLE] if analysed_count is None else analysed_count
    )
    minimum = config.minimum_usable_samples if minimum_samples is None else minimum_samples
    flagged_fraction = (
        (len(series) - statuses[QualityStatus.ACCEPTABLE]) / len(series) if series else 0.0
    )

    found = set(flag_counts)
    if completeness is not None and completeness < 1.0:
        found.add(QualityFlag.MISSING_DATA)
    if usable < minimum:
        found.add(QualityFlag.INSUFFICIENT_SAMPLES)

    if usable < minimum:
        status = QualityStatus.UNUSABLE
    elif (
        completeness is None or completeness >= config.acceptable_min_completeness
    ) and flagged_fraction <= config.acceptable_max_flagged_fraction:
        status = QualityStatus.ACCEPTABLE
    else:
        status = QualityStatus.DEGRADED

    notes = _record_notes(series, statuses, flag_counts, config)
    if interval is None:
        notes.append(
            "Completeness is not assessed: no expected sampling interval is configured "
            f"for {metric.value}."
        )
    elif not expected:
        notes.append(
            "Completeness is not assessed: the elapsed part of the window is shorter than "
            f"the expected sampling interval ({format_duration(interval)})."
        )
    else:
        notes.append(
            f"{_plural(len(instants), 'distinct observation time')} for {expected} expected "
            f"(one every {format_duration(interval)}). Longest interval without an "
            f"observation: {format_duration(_longest_gap(instants, elapsed))}."
        )
    if usable < minimum:
        notes.append(f"{_plural(usable, 'usable value')}, fewer than the {minimum} required.")
    notes.extend(remarks)

    return DataQuality(
        status=status,
        score=score,
        completeness=completeness,
        flags=[flag for flag in QualityFlag if flag in found],
        notes=" ".join(notes),
        algorithm=ALGORITHM,
        assessed_at=assessed_at,
    )


def _record_notes(
    series: Sequence[PhysiologicalMeasurement],
    statuses: Counter[QualityStatus],
    flag_counts: Counter[QualityFlag],
    config: DataQualityConfig,
) -> list[str]:
    """Sentences that describe the records of a window."""
    if not series:
        return ["No record in the window."]

    notes = [
        f"{_plural(len(series), 'record')} in the window: "
        f"{statuses[QualityStatus.ACCEPTABLE]} acceptable, "
        f"{statuses[QualityStatus.DEGRADED]} degraded, "
        f"{statuses[QualityStatus.UNUSABLE]} unusable."
    ]
    if flag_counts:
        listed = ", ".join(
            f"{flag.value} {flag_counts[flag]}" for flag in QualityFlag if flag_counts[flag]
        )
        notes.append(f"Records per flag: {listed}.")

    unchecked = sum(1 for measurement in series if _sensor_range(measurement, config) is None)
    if unchecked:
        notes.append(
            f"Records not checked against a sensor range: {unchecked} of {len(series)} "
            "(no measuring range is configured for their device)."
        )

    simulated = sum(1 for m in series if m.source is MeasurementSource.SIMULATED)
    if simulated:
        notes.append(f"Simulated (synthetic) records: {simulated} of {len(series)}.")
    return notes


def _longest_gap(instants: Iterable[datetime], periods: Sequence[Period]) -> timedelta:
    """Longest stretch of `periods` without an observation, period edges included."""
    longest = _ZERO
    for start, end in periods:
        marks = [start, *sorted(instant for instant in instants if start <= instant < end), end]
        longest = max(longest, *(later - earlier for earlier, later in pairwise(marks)))
    return longest


def _sensor_range(
    measurement: PhysiologicalMeasurement, config: DataQualityConfig
) -> SensorRange | None:
    if measurement.device_id is None:
        return None
    return config.sensor_ranges.get(measurement.device_id, {}).get(measurement.metric)


def _describe_bounds(lower: float | None, upper: float | None) -> str:
    if lower is not None and upper is not None:
        return f"between {lower:g} and {upper:g}"
    if lower is not None:
        return f"at or above {lower:g}"
    return f"at or below {upper:g}"


def _own_issues(
    measurement: PhysiologicalMeasurement, assessed_at: datetime, config: DataQualityConfig
) -> list[_Issue]:
    """Issues that can be found by looking at one record alone."""
    issues: list[_Issue] = []
    value, unit, metric = measurement.value, measurement.unit, measurement.metric

    lower, upper = DEFINITION_BOUNDS.get(metric, (None, None))
    if (lower is not None and value < lower) or (upper is not None and value > upper):
        issues.append(
            _Issue(
                QualityStatus.UNUSABLE,
                QualityFlag.SIGNAL_ARTIFACT,
                f"Value {value:g} {unit} is impossible for {metric.value}: by definition "
                f"the metric lies {_describe_bounds(lower, upper)} {unit}.",
            )
        )

    sensor_range = _sensor_range(measurement, config)
    if sensor_range is not None and not sensor_range.minimum <= value <= sensor_range.maximum:
        issues.append(
            _Issue(
                QualityStatus.DEGRADED,
                QualityFlag.OUT_OF_SENSOR_RANGE,
                f"Value {value:g} {unit} is outside the measuring range documented for "
                f"device '{measurement.device_id}' ({sensor_range.minimum:g} to "
                f"{sensor_range.maximum:g} {unit}; source: {sensor_range.source}), where "
                "the accuracy of the device is not documented.",
            )
        )

    if measurement.interval_end is not None and metric in INTERVAL_BOUNDED_DURATIONS:
        interval = measurement.interval_end - measurement.measured_at
        allowed_seconds = (interval + config.interval_tolerance).total_seconds()
        if value * _SECONDS_PER_MINUTE > allowed_seconds:
            issues.append(
                _Issue(
                    QualityStatus.UNUSABLE,
                    QualityFlag.SIGNAL_ARTIFACT,
                    f"Value {value:g} {unit} is longer than the observation interval it "
                    f"refers to ({interval.total_seconds() / _SECONDS_PER_MINUTE:g} {unit}).",
                )
            )

    latest = measurement.interval_end or measurement.measured_at
    if latest > assessed_at + config.clock_tolerance:
        issues.append(
            _Issue(
                QualityStatus.UNUSABLE,
                None,
                "The timestamp is later than the assessment time, so the record cannot be "
                "placed on the mission timeline.",
            )
        )
    return issues


def _add_duplicate_issues(
    measurements: Sequence[PhysiologicalMeasurement], issues: list[list[_Issue]]
) -> None:
    """Find records that describe the same observation or share an identifier."""
    by_observation: dict[tuple, list[int]] = defaultdict(list)
    by_identifier: dict[str, list[int]] = defaultdict(list)
    for index, measurement in enumerate(measurements):
        by_observation[_observation_key(measurement)].append(index)
        by_identifier[measurement.measurement_id].append(index)

    for indices in by_observation.values():
        if len(indices) < 2:
            continue
        if len({measurements[index].value for index in indices}) > 1:
            for index in indices:
                issues[index].append(
                    _Issue(
                        QualityStatus.UNUSABLE,
                        QualityFlag.DUPLICATE,
                        f"{len(indices)} records describe this observation (same crew "
                        "member, metric, time, source and device) with different values, "
                        "so the true value cannot be determined.",
                    )
                )
            continue
        # Identical copies: retain one. The smallest identifier is only a deterministic
        # tie-break that does not depend on the order of the input.
        retained = min(indices, key=lambda index: (measurements[index].measurement_id, index))
        retained_id = measurements[retained].measurement_id
        for index in indices:
            if index == retained:
                continue
            note = (
                "This record was received more than once; only one copy is used."
                if measurements[index].measurement_id == retained_id
                else f"Redundant copy of measurement '{retained_id}' (same crew member, "
                "metric, time, source, device and value); only one copy is used."
            )
            issues[index].append(_Issue(QualityStatus.UNUSABLE, QualityFlag.DUPLICATE, note))

    for indices in by_identifier.values():
        contents = {(_observation_key(measurements[i]), measurements[i].value) for i in indices}
        if len(contents) < 2:
            continue
        for index in indices:
            issues[index].append(
                _Issue(
                    QualityStatus.UNUSABLE,
                    QualityFlag.DUPLICATE,
                    f"Its measurement_id is shared by {len(indices)} records with different "
                    "content, so the records cannot be told apart reliably.",
                )
            )


def _add_blood_pressure_issues(
    measurements: Sequence[PhysiologicalMeasurement], issues: list[list[_Issue]]
) -> None:
    """Check each blood-pressure reading against the definition of its two values.

    Systolic pressure is the highest and diastolic pressure the lowest arterial pressure
    of a heartbeat, so the diastolic value of a reading cannot exceed its systolic value.
    Equal values are not flagged: the definitions do not exclude them. Which of the two
    values is wrong cannot be known, so both are set aside.
    """
    readings: dict[tuple, dict[MetricType, list[int]]] = defaultdict(lambda: defaultdict(list))
    for index, measurement in enumerate(measurements):
        if measurement.metric in (
            MetricType.SYSTOLIC_BLOOD_PRESSURE,
            MetricType.DIASTOLIC_BLOOD_PRESSURE,
        ):
            reading = (
                measurement.crew_member_id,
                measurement.measured_at,
                measurement.interval_end,
                measurement.source,
                measurement.device_id,
            )
            readings[reading][measurement.metric].append(index)

    for by_metric in readings.values():
        systolic = {measurements[i].value for i in by_metric[MetricType.SYSTOLIC_BLOOD_PRESSURE]}
        diastolic = {measurements[i].value for i in by_metric[MetricType.DIASTOLIC_BLOOD_PRESSURE]}
        # Without exactly one value on each side there is no pair to compare. Records that
        # disagree on a value are already handled as duplicates.
        if len(systolic) != 1 or len(diastolic) != 1:
            continue
        systolic_value, diastolic_value = next(iter(systolic)), next(iter(diastolic))
        if diastolic_value <= systolic_value:
            continue
        for indices in by_metric.values():
            for index in indices:
                issues[index].append(
                    _Issue(
                        QualityStatus.UNUSABLE,
                        QualityFlag.SIGNAL_ARTIFACT,
                        f"Diastolic blood pressure ({diastolic_value:g} mmHg) is higher than "
                        f"the systolic blood pressure of the same reading ({systolic_value:g} "
                        "mmHg), which contradicts their definitions; neither value is used.",
                    )
                )


def _observation_key(measurement: PhysiologicalMeasurement) -> tuple:
    """Fields that identify an observation: two records that share them describe the same one.

    Readings taken at the same instant by different devices are distinct observations.
    """
    return (
        measurement.crew_member_id,
        measurement.metric,
        measurement.measured_at,
        measurement.interval_end,
        measurement.source,
        measurement.device_id,
    )


def _measurement_quality(issues: Sequence[_Issue], assessed_at: datetime) -> DataQuality:
    if any(issue.status is QualityStatus.UNUSABLE for issue in issues):
        status = QualityStatus.UNUSABLE
    elif issues:
        status = QualityStatus.DEGRADED
    else:
        status = QualityStatus.ACCEPTABLE
    found = {issue.flag for issue in issues}
    return DataQuality(
        status=status,
        flags=[flag for flag in QualityFlag if flag in found],
        notes=" ".join(issue.note for issue in issues) or None,
        algorithm=ALGORITHM,
        assessed_at=assessed_at,
    )
