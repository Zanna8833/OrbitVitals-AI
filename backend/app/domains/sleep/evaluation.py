"""Adapters from descriptive sleep analysis to the existing evaluation contracts."""

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from json import dumps
from math import isfinite

from app.domains.sleep.config import SleepConfig
from app.domains.sleep.trends import (
    SleepTrend,
    analyze_sleep_trends,
    observation_problem,
    utc,
    value_problem,
)
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    BaselineStatus,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MeasurementSource,
    MetricFinding,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityStatus,
)


@dataclass(frozen=True)
class _Comparison:
    description: str
    baseline_id: str | None = None
    baseline_value: float | None = None
    absolute_deviation: float | None = None
    relative_deviation: float | None = None
    flagged: bool = False


def _check_baseline_identity(
    baseline: PersonalBaseline, metric: MetricType, crew_member_id: str
) -> None:
    if baseline.crew_member_id != crew_member_id or baseline.metric != metric:
        raise ValueError("A baseline must match the requested crew member and metric")


def _compare_reference(
    observed_value: float | None,
    *,
    metric: MetricType,
    crew_member_id: str,
    target_start: datetime,
    evaluated_at: datetime,
    baseline: PersonalBaseline | None,
    config: SleepConfig,
) -> _Comparison:
    if baseline is None:
        return _Comparison("No personal baseline supplied; no personal-reference comparison made.")
    _check_baseline_identity(baseline, metric, crew_member_id)
    # Source: README.md, "Baseline integration": a conservative adapter policy,
    # independent of how a future engine decides that a baseline is established.
    if baseline.status != BaselineStatus.ESTABLISHED or baseline.sample_count == 0:
        return _Comparison("Supplied baseline is not established with nonzero samples.")
    if baseline.data_quality is not None and baseline.data_quality.status == QualityStatus.UNUSABLE:
        return _Comparison("Supplied baseline has unusable upstream data quality.")
    if baseline.window_end > target_start:
        return _Comparison(
            "Supplied baseline overlaps or follows the target window; comparison withheld."
        )
    if baseline.computed_at > evaluated_at:
        return _Comparison(
            "Supplied baseline was computed after evaluated_at; comparison withheld."
        )
    # Source: README.md, "Baseline integration": prefer an explicitly supplied
    # median, otherwise mean; never derive or synthesize a personal baseline.
    statistic = "median" if baseline.statistics.median is not None else "mean"
    reference = getattr(baseline.statistics, statistic)
    if reference is None or value_problem(metric, reference) is not None:
        return _Comparison("Supplied baseline has no usable median or mean for this metric.")
    if observed_value is None:
        return _Comparison("No included observed value is available for baseline comparison.")
    # Source: app/models/evaluation.py, MetricFinding's deviation definitions.
    deviation = observed_value - reference
    relative = deviation / reference if reference != 0 else None
    if relative is not None and not isfinite(relative):
        relative = None
    thresholds = config.thresholds_for(metric)
    flagged = abs(deviation) >= thresholds.minimum_observation_deviation
    description = (
        f"Compared with supplied baseline {statistic} {reference:.6g} "
        f"{METRIC_CATALOG[metric].unit}; signed deviation {deviation:+.6g}. "
        f"Absolute-deviation threshold >= {thresholds.minimum_observation_deviation:.6g} "
        f"{'percentage points' if metric == MetricType.SLEEP_EFFICIENCY else 'min'} "
        f"was {'met' if flagged else 'not met'}."
    )
    if relative is None:
        description += " Relative deviation is undefined for a zero reference or non-finite ratio."
    return _Comparison(
        description=description,
        baseline_id=baseline.baseline_id,
        baseline_value=reference,
        absolute_deviation=deviation,
        relative_deviation=relative,
        flagged=flagged,
    )


def _finding(
    metric: MetricType,
    observed_value: float | None,
    status: EvaluationStatus,
    explanation: str,
    comparison: _Comparison,
    quality: DataQuality | None,
) -> MetricFinding:
    return MetricFinding(
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        status=status,
        observed_value=observed_value,
        baseline_id=comparison.baseline_id,
        baseline_value=comparison.baseline_value,
        absolute_deviation=comparison.absolute_deviation,
        relative_deviation=comparison.relative_deviation,
        explanation=explanation,
        data_quality=quality.model_copy(deep=True) if quality is not None else None,
    )


def analyze_sleep_observation(
    measurement: PhysiologicalMeasurement,
    *,
    evaluated_at: datetime,
    config: SleepConfig,
    baseline: PersonalBaseline | None = None,
) -> MetricFinding:
    """Describe a completed observation and optionally compare a prior baseline.

    Without a usable supplied baseline the value remains descriptive and status is
    insufficient_data. Two-sided effect sizes are operational review triggers,
    never sleep adequacy or disease classifications. No engine is invoked.
    """
    config.thresholds_for(measurement.metric)
    at = utc(evaluated_at, "evaluated_at")
    start = utc(measurement.measured_at, "measured_at")
    if baseline is not None:
        _check_baseline_identity(baseline, measurement.metric, measurement.crew_member_id)
    problem = observation_problem(measurement)
    if start > at or (measurement.interval_end is not None and measurement.interval_end > at):
        problem = "observation_not_complete_at_evaluated_at"
    quality = measurement.data_quality
    if quality is not None and quality.status == QualityStatus.UNUSABLE:
        problem = "upstream_quality_unusable"
    if problem:
        return _finding(
            measurement.metric,
            None,
            EvaluationStatus.INSUFFICIENT_DATA,
            f"Observation excluded: {problem}. No reference comparison made. "
            f"Policy '{config.policy_id}'. This is not a diagnosis.",
            _Comparison("Reference comparison withheld."),
            quality,
        )

    comparison = _compare_reference(
        measurement.value,
        metric=measurement.metric,
        crew_member_id=measurement.crew_member_id,
        target_start=start,
        evaluated_at=at,
        baseline=baseline,
        config=config,
    )
    status = EvaluationStatus.INSUFFICIENT_DATA
    if comparison.baseline_id is not None:
        status = EvaluationStatus.ATTENTION if comparison.flagged else EvaluationStatus.NOMINAL
    explanation = (
        f"Completed observation: {measurement.value:.6g} {measurement.unit}. "
        f"{comparison.description} Policy '{config.policy_id}'. "
        f"Source: {measurement.source.value}. "
        "Non-clinical comparison only; nominal means no configured deviation was detected."
    )
    if quality is None or quality.status == QualityStatus.NOT_ASSESSED:
        explanation += " Measurement quality has not been assessed."
    elif quality.status == QualityStatus.DEGRADED:
        explanation += " Upstream quality is degraded; interpret this comparison cautiously."
    return _finding(measurement.metric, measurement.value, status, explanation, comparison, quality)


def _unassessed_quality(trend: SleepTrend) -> DataQuality:
    statuses = Counter(observation.quality_status.value for observation in trend.observations)
    return DataQuality(
        status=QualityStatus.NOT_ASSESSED,
        notes=(
            "No window-level quality assessment supplied. Included measurement quality statuses: "
            f"{dumps(dict(sorted(statuses.items())))}. Night coverage is reported in the "
            "finding explanation and is not a Data Quality engine score."
        ),
    )


def _trend_explanation(trend: SleepTrend, config: SleepConfig) -> str:
    thresholds = config.thresholds_for(trend.metric)
    unit = "percentage points" if trend.metric == MetricType.SLEEP_EFFICIENCY else "min"
    coverage = f"{trend.coverage:.6g}" if trend.coverage is not None else "undefined"
    missing = ", ".join(night.isoformat() for night in trend.missing_nights) or "none"
    text = (
        f"Included {len(trend.observations)}/{len(trend.expected_nights)} complete night buckets; "
        f"coverage={coverage}; missing nights={missing}; longest missing run="
        f"{trend.longest_missing_run}; elapsed span={trend.span_days:.6g} days. "
        "Observed value is the median of included nightly values. "
    )
    if trend.slope_per_day is not None:
        text += (
            f"Theil-Sen slope={trend.slope_per_day:+.6g} {unit}/day; "
            f"fitted change={trend.fitted_change:+.6g} {unit}; "
            f"decreasing transition fraction={trend.decreasing_fraction:.6g}. "
        )
    text += (
        f"Trend gates: absolute slope >= {thresholds.minimum_slope_per_day:.6g} {unit}/day "
        f"and absolute fitted change >= {thresholds.minimum_total_change:.6g} {unit}. "
    )
    if trend.metric == MetricType.SLEEP_DURATION:
        text += (
            "Duration also requires a negative slope and decreasing transition fraction >= "
            f"{config.minimum_decreasing_fraction:.6g}. "
        )
    if trend.insufficient_reasons:
        text += f"Insufficient trend data: {', '.join(trend.insufficient_reasons)}. "
    elif trend.signal is not None:
        text += f"Configured statistical pattern detected: {trend.signal.value}. "
    else:
        text += "No configured trend pattern detected. "
    if trend.exclusions:
        exclusions = ", ".join(f"{item.measurement_id}: {item.reason}" for item in trend.exclusions)
        text += f"Excluded records: {exclusions}. "
    simulated = sum(
        observation.source == MeasurementSource.SIMULATED for observation in trend.observations
    )
    text += f"Included simulated observations: {simulated}. "
    return text


def evaluate_sleep_window(
    measurements: Iterable[PhysiologicalMeasurement],
    *,
    evaluation_id: str,
    crew_member_id: str,
    window_start: datetime,
    window_end: datetime,
    evaluated_at: datetime,
    config: SleepConfig,
    mission_phase: MissionPhaseType | None = None,
    baselines: Mapping[MetricType, PersonalBaseline] | None = None,
    data_quality: DataQuality | None = None,
    metric_data_quality: Mapping[MetricType, DataQuality] | None = None,
) -> EvaluationResult:
    """Return the unchanged EvaluationResult contract for a completed sleep window.

    Optional quality assessments are supplied, not computed. Unusable assessments
    suppress classification. Established, prior personal baselines may add a
    two-sided comparison of the window median. Trends remain available without
    baseline engines. See README.md for the non-clinical status interpretation.
    """
    start = utc(window_start, "window_start")
    end = utc(window_end, "window_end")
    at = utc(evaluated_at, "evaluated_at")
    if end > at:
        raise ValueError("window_end must not be later than evaluated_at")
    for metric, baseline in (baselines or {}).items():
        config.thresholds_for(metric)
        _check_baseline_identity(baseline, metric, crew_member_id)
    for metric in metric_data_quality or {}:
        config.thresholds_for(metric)

    trends = analyze_sleep_trends(
        measurements,
        crew_member_id=crew_member_id,
        window_start=start,
        window_end=end,
        config=config,
    )
    findings = []
    for trend in trends:
        supplied_quality = (metric_data_quality or {}).get(trend.metric)
        quality = supplied_quality if supplied_quality is not None else _unassessed_quality(trend)
        blocked = quality.status == QualityStatus.UNUSABLE or (
            data_quality is not None and data_quality.status == QualityStatus.UNUSABLE
        )
        comparison = _compare_reference(
            trend.median_value,
            metric=trend.metric,
            crew_member_id=crew_member_id,
            target_start=start,
            evaluated_at=at,
            baseline=(baselines or {}).get(trend.metric),
            config=config,
        )
        status = EvaluationStatus.INSUFFICIENT_DATA
        if trend.sufficient_data and not blocked:
            status = (
                EvaluationStatus.ATTENTION
                if trend.signal is not None or comparison.flagged
                else EvaluationStatus.NOMINAL
            )
        explanation = _trend_explanation(trend, config) + comparison.description
        if blocked:
            explanation += (
                " Classification withheld because supplied window/metric quality is unusable."
            )
        elif not trend.sufficient_data:
            explanation += (
                " Baseline deviations, if reported, are descriptive only "
                "for this incomplete window."
            )
        explanation += (
            " Non-clinical screening only; nominal means no configured signal detected, "
            "and does not establish adequate sleep or health."
        )
        findings.append(
            _finding(trend.metric, trend.median_value, status, explanation, comparison, quality)
        )

    # Source: README.md, "Status mapping": a review signal takes precedence;
    # otherwise any unevaluable metric makes the domain insufficient_data. Never
    # emit alert or present absence of a configured signal as evidence of health.
    statuses = {finding.status for finding in findings}
    if EvaluationStatus.ATTENTION in statuses:
        overall = EvaluationStatus.ATTENTION
    elif EvaluationStatus.INSUFFICIENT_DATA in statuses:
        overall = EvaluationStatus.INSUFFICIENT_DATA
    else:
        overall = EvaluationStatus.NOMINAL
    window_quality = (
        data_quality
        if data_quality is not None
        else DataQuality(
            status=QualityStatus.NOT_ASSESSED,
            notes=(
                "No window-level Data Quality engine output supplied; "
                "no score or quality flags inferred."
            ),
        )
    )
    counts = Counter(finding.status for finding in findings)
    return EvaluationResult(
        evaluation_id=evaluation_id,
        crew_member_id=crew_member_id,
        domain=HealthDomain.SLEEP,
        mission_phase=mission_phase,
        window_start=start,
        window_end=end,
        status=overall,
        summary=(
            "Non-clinical sleep screen. "
            f"Attention metrics: {counts[EvaluationStatus.ATTENTION]}; "
            "insufficient-data metrics: "
            f"{counts[EvaluationStatus.INSUFFICIENT_DATA]}. "
            "Nominal means no configured statistical signal; this is not a diagnosis. "
            f"Policy: {dumps(asdict(config), sort_keys=True)}"
        ),
        findings=findings,
        data_quality=window_quality.model_copy(deep=True),
        algorithm=AlgorithmInfo(name="sleep_monitoring_trends", version="0.1.0"),
        evaluated_at=at,
    )
