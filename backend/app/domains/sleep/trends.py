"""Deterministic nightly selection and descriptive trends, independent of the API."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from itertools import combinations, pairwise
from math import isfinite

from app.domains.sleep.config import SleepConfig
from app.models import (
    MeasurementSource,
    MetricType,
    PhysiologicalMeasurement,
    QualityStatus,
)

SLEEP_METRICS = (MetricType.SLEEP_DURATION, MetricType.SLEEP_EFFICIENCY)
# Calendar/time conversion constants, not physiological reference values.
DAY = timedelta(days=1)
MINUTE = timedelta(minutes=1)


class TrendSignal(StrEnum):
    """Descriptive patterns requiring human interpretation."""

    DURATION_REDUCTION = "progressive_duration_reduction"
    EFFICIENCY_DECREASE = "efficiency_decrease"
    EFFICIENCY_INCREASE = "efficiency_increase"


@dataclass(frozen=True)
class ExcludedObservation:
    """Why a record did not contribute; these are not Data Quality engine flags."""

    measurement_id: str
    reason: str


@dataclass(frozen=True)
class NightlyObservation:
    """One unambiguous observation for an operational night."""

    night: date
    measurement_id: str
    measured_at: datetime
    value: float
    source: MeasurementSource
    quality_status: QualityStatus


@dataclass(frozen=True)
class SleepTrend:
    """Internal domain diagnostics; this is not a new public API contract."""

    metric: MetricType
    observations: tuple[NightlyObservation, ...]
    expected_nights: tuple[date, ...]
    missing_nights: tuple[date, ...]
    longest_missing_run: int
    coverage: float | None
    span_days: float
    median_value: float | None
    slope_per_day: float | None
    fitted_change: float | None
    decreasing_fraction: float | None
    signal: TrendSignal | None
    insufficient_reasons: tuple[str, ...]
    exclusions: tuple[ExcludedObservation, ...]

    @property
    def sufficient_data(self) -> bool:
        """Whether all caller-configured data sufficiency gates were met."""
        return not self.insufficient_reasons


def utc(value: datetime, name: str) -> datetime:
    """Normalize an aware instant; never interpret a naive datetime as local time."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def value_problem(metric: MetricType, value: float) -> str | None:
    """Check mathematical metric definitions, without sensor or clinical cutoffs."""
    if metric not in SLEEP_METRICS:
        raise ValueError(f"Unsupported sleep metric: {metric}")
    # Source: schemas/metric_catalog.json: elapsed minutes cannot be negative;
    # a percentage share of time asleep is bounded by 0 and 100 by definition.
    if not isfinite(value) or value < 0:
        return "invalid_metric_value"
    if metric == MetricType.SLEEP_EFFICIENCY and value > 100:
        return "invalid_metric_value"
    return None


def observation_problem(measurement: PhysiologicalMeasurement) -> str | None:
    """Check only the definitions needed to interpret a sleep observation."""
    problem = value_problem(measurement.metric, measurement.value)
    if problem:
        return problem
    if measurement.interval_end is not None:
        elapsed = utc(measurement.interval_end, "interval_end") - utc(
            measurement.measured_at, "measured_at"
        )
        # Source: PhysiologicalMeasurement's interval definition and the catalog's
        # total-sleep-time definition. This is an interval identity, not a limit
        # on how long a person should sleep. No partial interval is prorated.
        if elapsed <= timedelta(0):
            return "non_positive_interval"
        if measurement.metric == MetricType.SLEEP_DURATION and measurement.value > elapsed / MINUTE:
            return "duration_exceeds_observation_interval"
    return None


def _median(values: Sequence[float]) -> float:
    # Source: https://docs.python.org/3.11/library/statistics.html#statistics.median
    # Mean of the middle two for even counts; halving first avoids sum overflow.
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return ordered[middle - 1] / 2 + ordered[middle] / 2


def _night_start(instant: datetime, hour: int) -> datetime:
    boundary = instant.replace(hour=hour, minute=0, second=0, microsecond=0)
    return boundary if boundary <= instant else boundary - DAY


def _expected_nights(start: datetime, end: datetime, hour: int) -> tuple[date, ...]:
    # Source: README.md, "Windows and nights": only fully enclosed UTC buckets
    # count towards expected nights; partially observed edge buckets are excluded.
    boundary = _night_start(start, hour)
    if boundary < start:
        boundary += DAY
    nights: list[date] = []
    while end - boundary >= DAY:
        nights.append(boundary.date())
        boundary += DAY
    return tuple(nights)


def _unique_measurements(
    measurements: Iterable[PhysiologicalMeasurement], crew_member_id: str
) -> tuple[list[PhysiologicalMeasurement], dict[MetricType, list[ExcludedObservation]]]:
    unique: dict[str, PhysiologicalMeasurement] = {}
    exclusions: dict[MetricType, list[ExcludedObservation]] = defaultdict(list)
    for measurement in measurements:
        if measurement.crew_member_id != crew_member_id:
            raise ValueError("All measurements must belong to the requested crew member")
        if measurement.metric not in SLEEP_METRICS:
            raise ValueError(f"Unsupported sleep metric: {measurement.metric}")
        previous = unique.get(measurement.measurement_id)
        if previous is not None:
            if previous != measurement:
                raise ValueError(f"Conflicting measurement_id: {measurement.measurement_id}")
            exclusions[measurement.metric].append(
                ExcludedObservation(measurement.measurement_id, "repeated_identical_id")
            )
        else:
            unique[measurement.measurement_id] = measurement
    return list(unique.values()), exclusions


def _select_nights(
    measurements: Iterable[PhysiologicalMeasurement],
    expected: tuple[date, ...],
    start: datetime,
    end: datetime,
    config: SleepConfig,
    exclusions: list[ExcludedObservation],
) -> tuple[NightlyObservation, ...]:
    candidates: dict[date, list[PhysiologicalMeasurement]] = defaultdict(list)
    expected_set = set(expected)
    for measurement in measurements:
        at = utc(measurement.measured_at, "measured_at")
        night = _night_start(at, config.night_start_hour_utc).date()
        if not start <= at < end:
            problem = "outside_window"
        elif measurement.interval_end is not None and measurement.interval_end > end:
            problem = "incomplete_interval"
        elif night not in expected_set:
            problem = "partial_night_bucket"
        else:
            problem = observation_problem(measurement)
            if (
                problem is None
                and measurement.data_quality is not None
                and measurement.data_quality.status == QualityStatus.UNUSABLE
            ):
                problem = "upstream_quality_unusable"
        if problem:
            exclusions.append(ExcludedObservation(measurement.measurement_id, problem))
        else:
            candidates[night].append(measurement)

    selected: list[tuple[date, PhysiologicalMeasurement]] = []
    for night, records in sorted(candidates.items()):
        # Source: README.md, "Windows and nights". The contract has no primary-
        # sleep/nap or revision identifier. Multiple records are ambiguous; neither
        # adding durations nor averaging efficiency percentages is justified.
        if len(records) > 1:
            exclusions.extend(
                ExcludedObservation(record.measurement_id, "ambiguous_night") for record in records
            )
        else:
            selected.append((night, records[0]))

    overlapping: set[str] = set()
    for (_, left), (_, right) in combinations(selected, 2):
        if left.interval_end is not None and left.interval_end > right.measured_at:
            overlapping.update((left.measurement_id, right.measurement_id))

    observations: list[NightlyObservation] = []
    for night, measurement in selected:
        if measurement.measurement_id in overlapping:
            exclusions.append(
                ExcludedObservation(measurement.measurement_id, "overlapping_intervals")
            )
            continue
        quality = measurement.data_quality
        observations.append(
            NightlyObservation(
                night=night,
                measurement_id=measurement.measurement_id,
                measured_at=utc(measurement.measured_at, "measured_at"),
                value=measurement.value,
                source=measurement.source,
                quality_status=quality.status if quality else QualityStatus.NOT_ASSESSED,
            )
        )
    return tuple(observations)


def _describe_trend(
    metric: MetricType,
    observations: tuple[NightlyObservation, ...],
    expected: tuple[date, ...],
    exclusions: list[ExcludedObservation],
    config: SleepConfig,
) -> SleepTrend:
    present = {observation.night for observation in observations}
    missing = tuple(night for night in expected if night not in present)
    run = longest_run = 0
    for night in expected:
        run = 0 if night in present else run + 1
        longest_run = max(longest_run, run)
    # Source: README.md, "Configuration policy": coverage is included nights /
    # fully observable nights, not the fraction of time asleep or a quality score.
    coverage = len(observations) / len(expected) if expected else None
    span = (
        (observations[-1].measured_at - observations[0].measured_at) / DAY if observations else 0.0
    )
    reasons: list[str] = []
    if not expected:
        reasons.append("no_complete_night_buckets")
    if len(observations) < config.minimum_nights:
        reasons.append("too_few_nights")
    if coverage is not None and coverage < config.minimum_coverage:
        reasons.append("coverage_below_minimum")
    if span < config.minimum_span_days:
        reasons.append("time_span_below_minimum")
    if longest_run > config.maximum_consecutive_missing_nights:
        reasons.append("missing_run_exceeds_maximum")

    slope = fitted_change = decreasing_fraction = None
    if len(observations) >= 2:
        # Source: NIST, Theil-Sen fit (Sen, 1968): median of all pairwise slopes.
        # https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/ts_fit.htm
        # Actual elapsed UTC days preserve gaps and irregular observation times.
        slopes = [
            (right.value - left.value) / ((right.measured_at - left.measured_at) / DAY)
            for left, right in combinations(observations, 2)
        ]
        if all(isfinite(value) for value in slopes):
            slope = _median(slopes)
            # Fitted change is the line's endpoint difference: slope * elapsed days.
            fitted_change = slope * span
        if fitted_change is None or not isfinite(fitted_change):
            slope = fitted_change = None
            reasons.append("non_finite_trend_arithmetic")
        # Source: README.md, "Detection rules": the fraction of observed adjacent
        # transitions that strictly decrease. Ties do not count as reductions;
        # missing nights are not imputed as intermediate transitions.
        decreasing_fraction = sum(
            right.value < left.value for left, right in pairwise(observations)
        ) / (len(observations) - 1)

    signal = None
    thresholds = config.thresholds_for(metric)
    if not reasons and slope is not None and fitted_change is not None:
        # Source of these effect-size and progression gates: the explicit caller
        # policy, documented in README.md. They are not significance tests.
        substantial = (
            abs(slope) >= thresholds.minimum_slope_per_day
            and abs(fitted_change) >= thresholds.minimum_total_change
        )
        if substantial:
            if metric == MetricType.SLEEP_EFFICIENCY:
                signal = (
                    TrendSignal.EFFICIENCY_DECREASE
                    if slope < 0
                    else TrendSignal.EFFICIENCY_INCREASE
                )
            elif (
                slope < 0
                and decreasing_fraction is not None
                and decreasing_fraction >= config.minimum_decreasing_fraction
            ):
                signal = TrendSignal.DURATION_REDUCTION

    return SleepTrend(
        metric=metric,
        observations=observations,
        expected_nights=expected,
        missing_nights=missing,
        longest_missing_run=longest_run,
        coverage=coverage,
        span_days=span,
        median_value=_median([observation.value for observation in observations])
        if observations
        else None,
        slope_per_day=slope,
        fitted_change=fitted_change,
        decreasing_fraction=decreasing_fraction,
        signal=signal,
        insufficient_reasons=tuple(reasons),
        exclusions=tuple(sorted(exclusions, key=lambda item: (item.measurement_id, item.reason))),
    )


def analyze_sleep_trends(
    measurements: Iterable[PhysiologicalMeasurement],
    *,
    crew_member_id: str,
    window_start: datetime,
    window_end: datetime,
    config: SleepConfig,
) -> tuple[SleepTrend, SleepTrend]:
    """Describe both metrics in a completed, half-open window, in catalog order.

    Only complete operational night buckets are analyzed. Input order is irrelevant;
    absent metrics produce explicit insufficient-data diagnostics. No baseline,
    clock, I/O, quality engine, imputation or health threshold is used.
    """
    start = utc(window_start, "window_start")
    end = utc(window_end, "window_end")
    if end <= start:
        raise ValueError("window_end must be later than window_start")
    unique, exclusions = _unique_measurements(measurements, crew_member_id)
    expected = _expected_nights(start, end, config.night_start_hour_utc)
    trends = []
    for metric in SLEEP_METRICS:
        metric_exclusions = exclusions[metric]
        observations = _select_nights(
            (measurement for measurement in unique if measurement.metric == metric),
            expected,
            start,
            end,
            config,
            metric_exclusions,
        )
        trends.append(_describe_trend(metric, observations, expected, metric_exclusions, config))
    return trends[0], trends[1]
