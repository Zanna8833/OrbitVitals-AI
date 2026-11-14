"""Public Python entry point for physical-activity monitoring.

No persistence, HTTP, data-quality engine or baseline engine is required. The caller
supplies observations, personal plans, recording coverage and established references.
"""

import math

from app.domains.physical_activity.aggregation import (
    algorithm_info,
    finite_mean,
    prepare_records,
    relative_change,
    roll_up_quality,
    summarize_days,
    summarize_sessions,
    summarize_weeks,
    utc,
)
from app.domains.physical_activity.comparison import detect_reductions, select_baselines
from app.domains.physical_activity.models import (
    ACTIVITY_METRICS,
    ActivityMetricPolicy,
    ActivityReport,
    ActivityRequest,
    ActivityTrend,
    DailyActivitySummary,
    TargetOutcome,
    WeeklyActivitySummary,
)
from app.models import (
    METRIC_CATALOG,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MeasurementSource,
    MetricFinding,
    PersonalBaseline,
    QualityStatus,
)


def _metric_finding(
    request: ActivityRequest,
    index: int,
    days: list[DailyActivitySummary],
    weeks: list[WeeklyActivitySummary],
    trends: list[ActivityTrend],
    baseline: PersonalBaseline | None,
    baseline_notices: list[str],
) -> MetricFinding:
    metric = ACTIVITY_METRICS[index]
    policy = next(
        (item for item in request.policies if item.metric == metric),
        ActivityMetricPolicy(metric=metric),
    )
    daily = [day.metrics[index] for day in days]
    eligible = [
        (day.day, item) for day, item in zip(days, daily, strict=True) if item.comparison_eligible
    ]
    observed = finite_mean([item.observed_total for _, item in eligible])
    notes = [
        f"Observed value is the mean of {len(eligible)} complete usable active-day totals "
        f"in {METRIC_CATALOG[metric].unit}; partial days, rest and operational exceptions "
        "are excluded. Daily and weekly details retain known subtotals."
    ]
    if any(item.data_quality.status == QualityStatus.NOT_ASSESSED for item in daily):
        notes.append("Measurement quality is not fully assessed; no quality score was inferred.")
    daily_misses = [
        f"{day.day} (observed {day.metrics[index].observed_total:g} "
        f"< target {day.metrics[index].target_value:g} {METRIC_CATALOG[metric].unit})"
        for day in days
        if day.metrics[index].target_outcome == TargetOutcome.MISSED
    ]
    weekly_misses = [
        f"{week.week_start} (observed {week.metrics[index].observed_total:g} "
        f"< target {week.metrics[index].target_value:g} {METRIC_CATALOG[metric].unit})"
        for week in weeks
        if week.metrics[index].target_outcome == TargetOutcome.MISSED
    ]
    comparisons = sum(
        item.target_outcome in (TargetOutcome.MET, TargetOutcome.MISSED)
        for item in [*daily, *(week.metrics[index] for week in weeks)]
    )
    if daily_misses:
        notes.append(f"Personal daily minimum target missed on: {', '.join(daily_misses)}.")
    if weekly_misses:
        notes.append(
            "Personal weekly minimum target missed in ISO weeks starting: "
            f"{', '.join(weekly_misses)}."
        )
    notes.append(
        f"Configured daily target: {policy.daily_target}; weekly target: {policy.weekly_target} "
        f"{METRIC_CATALOG[metric].unit}. Day-specific targets are shown in daily details. "
        "No population exercise prescription is applied."
    )
    for plan in sorted(request.day_plans, key=lambda item: item.day):
        if metric in plan.daily_targets and any(day.day == plan.day for day in days):
            notes.append(
                f"Day-specific target on {plan.day}: {plan.daily_targets[metric]:g} "
                f"{METRIC_CATALOG[metric].unit}."
            )

    baseline_value = baseline.statistics.mean if baseline is not None else None
    absolute = (
        observed - baseline_value if observed is not None and baseline_value is not None else None
    )
    relative = relative_change(observed, baseline_value) if absolute is not None else None
    unusual_days = []
    if baseline is not None:
        notes.append(
            f"Established baseline {baseline.baseline_id} has a mean complete active-day total "
            f"of {baseline_value:g} {baseline.unit} from {baseline.sample_count} samples "
            f"in mission phase {baseline.mission_phase.value}. Reference window: "
            f"{utc(baseline.window_start).isoformat()} to {utc(baseline.window_end).isoformat()}. "
            "Acquisition and aggregation comparability were explicitly confirmed by the caller."
        )
        if (
            baseline.data_quality is None
            or baseline.data_quality.status == QualityStatus.NOT_ASSESSED
        ):
            notes.append("Baseline quality has not been independently assessed.")
        if baseline_value == 0:
            notes.append(
                "The baseline is zero: relative deviation is undefined; no division by zero."
            )
        notes.append(
            f"Configured baseline review tolerances: absolute={policy.baseline_absolute_tolerance} "
            f"{baseline.unit}, relative={policy.baseline_relative_tolerance}. "
            "A strict exceedance of either applicable tolerance prompts review. "
            "These settings are operational choices, not medical thresholds."
        )
        for day, item in eligible:
            difference = abs(item.observed_total - baseline_value)
            tests = []
            if policy.baseline_absolute_tolerance is not None:
                tests.append(difference > policy.baseline_absolute_tolerance)
            if policy.baseline_relative_tolerance is not None and baseline_value > 0:
                # An overflowing ratio exceeds every finite configured tolerance.
                ratio = difference / baseline_value
                tests.append(not math.isfinite(ratio) or ratio > policy.baseline_relative_tolerance)
            if tests:
                comparisons += 1
            if any(tests):
                unusual_days.append(
                    f"{day} (observed {item.observed_total:g} {baseline.unit}; "
                    f"signed deviation {item.observed_total - baseline_value:+g} {baseline.unit})"
                )
        if unusual_days:
            notes.append(
                "Unusual daily deviations under the configured tolerance on: "
                f"{', '.join(unusual_days)}."
            )
        if absolute is not None and baseline_value > 0 and relative is None:
            notes.append("Relative deviation is not representable as a finite number and is null.")
    else:
        notes.append("No comparable established daily-total baseline is available.")
    notes.extend(baseline_notices)

    metric_trends = [trend for trend in trends if trend.metric == metric]
    for trend in metric_trends:
        notes.append(
            f"Progressive reduction from {trend.start_day} through {trend.end_day}: "
            f"{trend.explanation}"
        )
    unresolved = any(
        not day.planned_rest
        and day.comparisons_enabled
        and not day.metrics[index].comparison_eligible
        for day in days
    ) or any(week.metrics[index].target_outcome == TargetOutcome.UNKNOWN for week in weeks)
    if daily_misses or weekly_misses or unusual_days or metric_trends:
        status = EvaluationStatus.ATTENTION
        notes.append("Attention requests a human review of activity records and mission context.")
    elif unresolved or comparisons == 0:
        status = EvaluationStatus.INSUFFICIENT_DATA
        notes.append(
            "A full activity assessment is unavailable: usable coverage or applicable "
            "comparison criteria are missing."
        )
    else:
        status = EvaluationStatus.NOMINAL
        notes.append(
            "The available configured activity comparisons were met; "
            "this does not establish physiological fitness."
        )
    if unresolved:
        notes.append(
            "Incomplete or low-quality periods remain unknown and are never classified "
            "as missed targets."
        )

    quality = roll_up_quality(
        (item.data_quality for item in daily),
        complete_days=sum(item.data_quality.completeness == 1 for item in daily),
        expected_days=len(days),
        evaluated_at=request.evaluated_at,
    )
    return MetricFinding(
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        status=status,
        observed_value=observed,
        baseline_id=baseline.baseline_id if baseline is not None else None,
        baseline_value=baseline_value,
        absolute_deviation=absolute,
        relative_deviation=relative,
        explanation=" ".join(notes),
        data_quality=quality,
    )


def monitor_activity(request: ActivityRequest) -> ActivityReport:
    """Evaluate additive physical-activity records without modifying the inputs.

    Only the nested ``evaluation`` is an existing public contract. All other report
    fields are domain-local integration detail; no endpoint is registered here.
    """
    prepared = prepare_records(request)
    days = summarize_days(request, prepared)
    weeks = summarize_weeks(request, days)
    trends = detect_reductions(request, days, weeks)
    baselines, baseline_notices = select_baselines(request)
    findings = [
        _metric_finding(
            request,
            index,
            days,
            weeks,
            trends,
            baselines.get(metric),
            [
                notice
                for notice in baseline_notices
                if any(
                    reference.baseline.metric == metric
                    and notice.startswith(f"Ignored baseline {reference.baseline.baseline_id}:")
                    for reference in request.baselines
                )
            ],
        )
        for index, metric in enumerate(ACTIVITY_METRICS)
    ]
    statuses = {item.status for item in findings}
    if EvaluationStatus.ATTENTION in statuses:
        status = EvaluationStatus.ATTENTION
    elif EvaluationStatus.INSUFFICIENT_DATA in statuses:
        status = EvaluationStatus.INSUFFICIENT_DATA
    else:
        status = EvaluationStatus.NOMINAL
    period_metrics = [metric for day in days for metric in day.metrics]
    quality = roll_up_quality(
        (item.data_quality for item in period_metrics),
        complete_days=sum(item.data_quality.completeness == 1 for item in period_metrics),
        expected_days=len(period_metrics),
        evaluated_at=request.evaluated_at,
        coverage_unit="UTC metric-days",
    )
    simulated = any(item.source == MeasurementSource.SIMULATED for item in request.measurements)
    notices = [*prepared.notices, *baseline_notices]
    summary = (
        f"Physical activity: {status.value}. {len(days)} UTC day(s), {len(weeks)} ISO week(s); "
        f"{len(trends)} progressive reduction run(s). Findings describe configured activity "
        "review signals and recording limits, not diagnoses or medical risk."
    )
    if simulated:
        label = "SIMULATED DATA: this evaluation includes synthetic measurements."
        notices.insert(0, label)
        summary = f"{label} {summary}"
        for finding in findings:
            finding.explanation = f"{label} {finding.explanation}"
    if request.context_notes:
        summary += f" Mission context supplied by the caller: {request.context_notes}"
    evaluation = EvaluationResult(
        evaluation_id=request.evaluation_id,
        crew_member_id=request.crew_member_id,
        domain=HealthDomain.PHYSICAL_ACTIVITY,
        mission_phase=request.mission_phase,
        window_start=utc(request.window_start),
        window_end=utc(request.window_end),
        status=status,
        summary=summary,
        findings=findings,
        data_quality=quality,
        algorithm=algorithm_info(),
        evaluated_at=utc(request.evaluated_at),
    )
    return ActivityReport(
        evaluation=evaluation,
        days=days,
        weeks=weeks,
        sessions=summarize_sessions(request, prepared),
        trends=trends,
        notices=list(dict.fromkeys(notices)),
    )
