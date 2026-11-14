"""Personal baseline selection and descriptive reduction runs, without medical cutoffs."""

from datetime import date, timedelta
from typing import Literal

from app.domains.physical_activity.aggregation import quality_blocks_comparison, relative_change
from app.domains.physical_activity.models import (
    ACTIVITY_METRICS,
    ActivityRequest,
    ActivityTrend,
    DailyActivitySummary,
    PeriodMetricSummary,
    WeeklyActivitySummary,
)
from app.models import METRIC_CATALOG, BaselineStatus, MetricType, PersonalBaseline


def select_baselines(
    request: ActivityRequest,
) -> tuple[dict[MetricType, PersonalBaseline], list[str]]:
    """Select the latest eligible historical reference for each metric, deterministically."""
    candidates: dict[MetricType, list[PersonalBaseline]] = {
        metric: [] for metric in ACTIVITY_METRICS
    }
    notices = []
    for reference in sorted(request.baselines, key=lambda item: item.baseline.baseline_id):
        baseline = reference.baseline
        reason = None
        if baseline.crew_member_id != request.crew_member_id:
            reason = "different crew member"
        elif baseline.metric not in ACTIVITY_METRICS:
            reason = "unsupported metric"
        elif not reference.comparable:
            reason = "caller has not confirmed comparable acquisition and active-day context"
        elif baseline.status != BaselineStatus.ESTABLISHED:
            reason = "baseline is not established"
        elif request.mission_phase is None or baseline.mission_phase != request.mission_phase:
            reason = "mission phase is unknown or does not match"
        elif baseline.window_end > request.window_start:
            reason = "reference window overlaps or follows the evaluation window"
        elif baseline.window_end <= baseline.window_start:
            reason = "reference window has no positive duration"
        elif (
            baseline.computed_at > request.evaluated_at
            or baseline.computed_at < baseline.window_end
        ):
            reason = "baseline computation time is inconsistent with available history"
        elif baseline.sample_count == 0:
            reason = "baseline has no samples"
        elif baseline.statistics.mean is None or baseline.statistics.mean < 0:
            reason = "a nonnegative mean of daily totals is unavailable"
        elif quality_blocks_comparison(baseline.data_quality):
            reason = "baseline quality is degraded, unusable or incomplete"
        if reason:
            notices.append(f"Ignored baseline {baseline.baseline_id}: {reason}.")
        else:
            candidates[baseline.metric].append(baseline)
    selected = {}
    for metric, available in candidates.items():
        if available:
            selected[metric] = max(
                available, key=lambda item: (item.window_end, item.computed_at, item.baseline_id)
            )
    return selected, notices


def _runs(
    request: ActivityRequest,
    metric: MetricType,
    period: Literal["daily", "weekly"],
    points: list[tuple[date, PeriodMetricSummary, tuple]],
) -> list[ActivityTrend]:
    trends = []
    run: list[tuple[date, float]] = []
    previous: tuple[date, PeriodMetricSummary, tuple] | None = None
    step = timedelta(days=1 if period == "daily" else 7)

    def finish_run() -> None:
        if len(run) < request.reduction_run_length:
            return
        first_day, first_value = run[0]
        last_day, last_value = run[-1]
        trends.append(
            ActivityTrend(
                metric=metric,
                period=period,
                start_day=first_day,
                end_day=last_day,
                values=[value for _, value in run],
                absolute_change=last_value - first_value,
                relative_change=relative_change(last_value, first_value),
                explanation=(
                    f"{len(run)} consecutive comparable {period} totals strictly decreased "
                    f"from {first_value:g} to {last_value:g} {METRIC_UNITS[metric]}. "
                    f"The configured run length is {request.reduction_run_length}. "
                    "This is a descriptive review signal; no significance or medical risk "
                    "is inferred. Rest, gaps and changes of plan break a run."
                ),
            )
        )

    for day, item, context_key in points:
        if not item.comparison_eligible or item.observed_total is None:
            finish_run()
            run, previous = [], None
            continue
        value = item.observed_total
        connected = (
            previous is not None and day - previous[0] == step and context_key == previous[2]
        )
        if connected:
            previous_value = previous[1].observed_total
            item.absolute_change = value - previous_value
            item.relative_change = relative_change(value, previous_value)
        if connected and value < previous[1].observed_total:
            run.append((day, value))
        else:
            finish_run()
            run = [(day, value)]
        previous = day, item, context_key
    finish_run()
    return trends


# Read canonical units from the shared catalog; never introduce a second unit system.
METRIC_UNITS = {metric: METRIC_CATALOG[metric].unit for metric in ACTIVITY_METRICS}


def detect_reductions(
    request: ActivityRequest,
    days: list[DailyActivitySummary],
    weeks: list[WeeklyActivitySummary],
) -> list[ActivityTrend]:
    """Attach consecutive-period changes and find maximal strictly decreasing runs."""
    trends = []
    for index, metric in enumerate(ACTIVITY_METRICS):
        daily_points = [
            (day.day, day.metrics[index], (day.metrics[index].target_value,)) for day in days
        ]
        trends.extend(_runs(request, metric, "daily", daily_points))
        weekly_points = []
        for week in weeks:
            week_days = [
                day
                for day in days
                if week.week_start <= day.day < week.week_start + timedelta(days=7)
            ]
            # A changed rest schedule or target is a changed workload context.
            context_key = (
                week.metrics[index].target_value,
                tuple(
                    (day.planned_rest, day.comparisons_enabled, day.metrics[index].target_value)
                    for day in week_days
                ),
            )
            weekly_points.append((week.week_start, week.metrics[index], context_key))
        trends.extend(_runs(request, metric, "weekly", weekly_points))
    return trends
