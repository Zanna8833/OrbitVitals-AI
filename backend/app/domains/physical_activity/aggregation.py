"""Conservative allocation of additive observations to sessions and UTC periods."""

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta

from app.domains.physical_activity.models import (
    ACTIVITY_METRICS,
    ActivityDayPlan,
    ActivityRequest,
    DailyActivitySummary,
    PeriodMetricSummary,
    SessionSummary,
    TargetOutcome,
    WeeklyActivitySummary,
)
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    DataQuality,
    MetricType,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)

ALGORITHM_NAME = "physical_activity_monitor"
ALGORITHM_VERSION = "0.1.0"
# These flags describe unavailable or unusable values, not medical abnormalities.
EXCLUDED_FLAGS = {
    QualityFlag.OUT_OF_SENSOR_RANGE,
    QualityFlag.SIGNAL_ARTIFACT,
    QualityFlag.DUPLICATE,
}
INCOMPLETE_FLAGS = {QualityFlag.MISSING_DATA, QualityFlag.INSUFFICIENT_SAMPLES}


def algorithm_info() -> AlgorithmInfo:
    return AlgorithmInfo(name=ALGORITHM_NAME, version=ALGORITHM_VERSION)


def utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


def midnight(day: date) -> datetime:
    return datetime.combine(day, time.min, UTC)


def dates_in_window(start: datetime, end: datetime) -> list[date]:
    """Dates touched by a positive, half-open UTC interval."""
    first = utc(start).date()
    last = (utc(end) - timedelta(microseconds=1)).date()
    return [first + timedelta(days=offset) for offset in range((last - first).days + 1)]


def finite_sum(values: Iterable[float]) -> float | None:
    """Refuse unrepresentable totals instead of emitting Infinity or a partial sum."""
    try:
        result = math.fsum(values)
    except OverflowError:
        return None
    return result if math.isfinite(result) else None


def relative_change(value: float, reference: float) -> float | None:
    if reference == 0:
        return None
    result = (value - reference) / reference
    return result if math.isfinite(result) else None


def finite_mean(values: list[float]) -> float | None:
    if not values:
        return None
    total = finite_sum(values)
    # Scale only when needed, preserving subnormal values in ordinary sums.
    return (
        total / len(values)
        if total is not None
        else finite_sum(value / len(values) for value in values)
    )


def quality_blocks_comparison(quality: DataQuality | None) -> bool:
    return quality is not None and (
        quality.status in (QualityStatus.DEGRADED, QualityStatus.UNUSABLE)
        or (quality.completeness is not None and quality.completeness < 1)
        or bool(quality.flags)
    )


def roll_up_quality(
    qualities: Iterable[DataQuality | None],
    *,
    complete_days: int,
    expected_days: int,
    evaluated_at: datetime,
    flags: Iterable[QualityFlag] = (),
    issues: Iterable[str] = (),
    coverage_unit: str = "UTC days",
) -> DataQuality:
    """Propagate assessments and report recording coverage; do not estimate quality scores."""
    assessments = list(qualities)
    combined_flags = set(flags)
    notes = list(issues)
    has_integrity_issues = bool(notes)
    for assessment in assessments:
        if assessment is not None:
            combined_flags.update(assessment.flags)
            if assessment.notes:
                notes.append(assessment.notes)
    if complete_days < expected_days:
        combined_flags.add(QualityFlag.MISSING_DATA)
    if (
        combined_flags
        or has_integrity_issues
        or any(quality_blocks_comparison(item) for item in assessments)
    ):
        status = QualityStatus.DEGRADED
    elif not assessments or any(
        item is None or item.status == QualityStatus.NOT_ASSESSED for item in assessments
    ):
        status = QualityStatus.NOT_ASSESSED
    else:
        status = QualityStatus.ACCEPTABLE
    if assessments and all(
        item is not None and item.status == QualityStatus.UNUSABLE for item in assessments
    ):
        status = QualityStatus.UNUSABLE
    notes.insert(
        0,
        f"Confirmed complete usable {coverage_unit}: {complete_days}/{expected_days}. "
        "Completeness describes day coverage, not sensor sample completeness. "
        "No quality score was estimated.",
    )
    return DataQuality(
        status=status,
        completeness=complete_days / expected_days,
        flags=sorted(combined_flags, key=str),
        notes=" ".join(dict.fromkeys(notes)),
        algorithm=algorithm_info(),
        assessed_at=utc(evaluated_at),
    )


@dataclass
class DayRecords:
    records: list[PhysiologicalMeasurement] = field(default_factory=list)
    qualities: list[DataQuality | None] = field(default_factory=list)
    flags: set[QualityFlag] = field(default_factory=set)
    notes: list[str] = field(default_factory=list)
    blocked: bool = False


@dataclass
class PreparedRecords:
    days: dict[tuple[date, MetricType], DayRecords]
    session_values: dict[str, PhysiologicalMeasurement]
    notices: list[str]


def _affected_dates(measurement: PhysiologicalMeasurement, request: ActivityRequest) -> list[date]:
    start = utc(measurement.measured_at)
    end = utc(measurement.interval_end or measurement.measured_at)
    if end == start:
        return (
            [start.date()] if utc(request.window_start) <= start < utc(request.window_end) else []
        )
    left, right = max(start, utc(request.window_start)), min(end, utc(request.window_end))
    return dates_in_window(left, right) if left < right else []


def _overlapping_ids(measurements: Iterable[PhysiologicalMeasurement]) -> set[str]:
    """Reject connected overlap groups within one metric, including coincident points."""
    overlapping: set[str] = set()
    for metric in ACTIVITY_METRICS:
        ordered = sorted(
            (item for item in measurements if item.metric == metric),
            key=lambda item: (utc(item.measured_at), item.measurement_id),
        )
        group: list[PhysiologicalMeasurement] = []
        group_end: datetime | None = None
        for item in ordered:
            start = utc(item.measured_at)
            end = utc(item.interval_end or item.measured_at)
            connected = group and (start < group_end or start == utc(group[-1].measured_at))
            if not connected:
                if len(group) > 1:
                    overlapping.update(member.measurement_id for member in group)
                group, group_end = [], end
            group.append(item)
            group_end = max(group_end, end)
        if len(group) > 1:
            overlapping.update(member.measurement_id for member in group)
    return overlapping


def prepare_records(request: ActivityRequest) -> PreparedRecords:
    """Deduplicate IDs, reject ambiguous allocation, and retain evidence of gaps."""
    days = {
        (day, metric): DayRecords()
        for day in dates_in_window(request.window_start, request.window_end)
        for metric in ACTIVITY_METRICS
    }
    notices: list[str] = []
    all_records = {item.measurement_id: item for item in request.measurements}
    session_limits: dict[str, tuple[list[date], str, bool]] = {}
    for session in request.sessions:
        if session.end_time is None:
            continue
        start, end = utc(session.start_time), utc(session.end_time)
        left, right = max(start, utc(request.window_start)), min(end, utc(request.window_end))
        crosses_window = start < utc(request.window_start) or end > utc(request.window_end)
        if left >= right or (not crosses_window and len(dates_in_window(start, end)) == 1):
            continue
        reason = (
            "linked session crosses the evaluation boundary; no proportional allocation"
            if crosses_window
            else "linked session crosses UTC midnight; no proportional allocation"
        )
        for identifier in session.measurement_ids:
            record = all_records[identifier]
            if record.interval_end is None or record.interval_end == record.measured_at:
                session_limits[identifier] = (
                    dates_in_window(left, right),
                    reason,
                    not crosses_window,
                )

    def affected_dates(item: PhysiologicalMeasurement) -> list[date]:
        limit = session_limits.get(item.measurement_id)
        return limit[0] if limit is not None else _affected_dates(item, request)

    unique: dict[str, PhysiologicalMeasurement] = {}
    for item in sorted(
        request.measurements, key=lambda item: (utc(item.measured_at), item.measurement_id)
    ):
        affected = affected_dates(item)
        if not affected:
            notices.append(f"Ignored out-of-window measurement {item.measurement_id}.")
            continue
        if item.measurement_id in unique:
            notices.append(f"Collapsed identical duplicate measurement {item.measurement_id}.")
            for day in affected:
                days[day, item.metric].flags.add(QualityFlag.DUPLICATE)
            continue
        unique[item.measurement_id] = item

    overlapping = _overlapping_ids(unique.values())
    incomplete_links = {
        measurement_id
        for session in request.sessions
        if session.end_time is None
        for measurement_id in session.measurement_ids
    }
    for session in request.sessions:
        left = max(utc(session.start_time), utc(request.window_start))
        right = min(utc(session.end_time or request.window_end), utc(request.window_end))
        linked_metrics = {unique[item].metric for item in session.measurement_ids if item in unique}
        if left < right:
            for day in dates_in_window(left, right):
                for metric in ACTIVITY_METRICS:
                    if session.end_time is None or metric not in linked_metrics:
                        bucket = days[day, metric]
                        bucket.blocked = True
                        bucket.notes.append(
                            f"Session {session.session_id} is open or lacks linked {metric.value}."
                        )

    session_values: dict[str, PhysiologicalMeasurement] = {}
    for item in unique.values():
        affected = affected_dates(item)
        buckets = [days[day, item.metric] for day in affected]
        for bucket in buckets:
            bucket.qualities.append(item.data_quality)
        reason: str | None = None
        if item.value < 0:
            reason = "negative activity value"
        elif item.measurement_id in overlapping:
            reason = "ambiguous overlapping or coincident records of the same metric"
            for bucket in buckets:
                bucket.flags.add(QualityFlag.DUPLICATE)
        elif item.data_quality is not None and (
            item.data_quality.status == QualityStatus.UNUSABLE
            or set(item.data_quality.flags) & EXCLUDED_FLAGS
        ):
            reason = "upstream quality marks the value unusable"
        elif item.measurement_id in session_limits:
            _, reason, keep_session_value = session_limits[item.measurement_id]
            if keep_session_value:
                session_values[item.measurement_id] = item
        elif utc(item.measured_at) < utc(request.window_start) or utc(
            item.interval_end or item.measured_at
        ) > utc(request.window_end):
            reason = "interval crosses the evaluation boundary; no proportional allocation"
        else:
            session_values[item.measurement_id] = item
            if len(affected) > 1:
                reason = "interval crosses UTC midnight; no proportional allocation"
        if reason is not None:
            note = f"Excluded {item.measurement_id} from daily totals: {reason}."
            notices.append(note)
            for bucket in buckets:
                bucket.blocked = True
                bucket.notes.append(note)
            continue
        bucket = buckets[0]
        bucket.records.append(item)
        if item.measurement_id in incomplete_links:
            bucket.blocked = True
            bucket.notes.append(f"Measurement {item.measurement_id} belongs to an open session.")
    return PreparedRecords(days=days, session_values=session_values, notices=notices)


def target_outcome(
    value: float | None, target: float | None, *, applicable: bool, eligible: bool
) -> TargetOutcome:
    if not applicable:
        return TargetOutcome.NOT_APPLICABLE
    if target is None:
        return TargetOutcome.NOT_CONFIGURED
    if not eligible or value is None:
        return TargetOutcome.UNKNOWN
    return TargetOutcome.MET if value >= target else TargetOutcome.MISSED


def summarize_days(
    request: ActivityRequest, prepared: PreparedRecords
) -> list[DailyActivitySummary]:
    coverage = {(item.day, item.metric): item for item in request.coverage}
    plans = {item.day: item for item in request.day_plans}
    policies = {item.metric: item for item in request.policies}
    results: list[DailyActivitySummary] = []
    for day in dates_in_window(request.window_start, request.window_end):
        plan = plans.get(day, ActivityDayPlan(day=day))
        full_day = utc(request.window_start) <= midnight(day) and utc(
            request.window_end
        ) >= midnight(day + timedelta(days=1))
        metrics = []
        for metric in ACTIVITY_METRICS:
            bucket = prepared.days[day, metric]
            confirmation = coverage.get((day, metric))
            qualities = [*bucket.qualities]
            notes = [*bucket.notes]
            if confirmation is not None:
                if confirmation.quality is not None:
                    qualities.append(confirmation.quality)
                if confirmation.notes:
                    notes.append(confirmation.notes)
            if not full_day:
                notes.append("Partial UTC day; daily comparisons are withheld.")
            if confirmation is None or not confirmation.complete:
                notes.append("Complete recording was not confirmed; missing values are unknown.")
            complete = (
                full_day
                and confirmation is not None
                and confirmation.complete
                and not bucket.blocked
                and not any(
                    item is not None
                    and (
                        (item.completeness is not None and item.completeness < 1)
                        or set(item.flags) & INCOMPLETE_FLAGS
                    )
                    for item in qualities
                )
            )
            total = finite_sum(item.value for item in bucket.records) if bucket.records else None
            if bucket.records and total is None:
                complete = False
                notes.append("Daily sum is not representable as a finite number.")
            if not bucket.records and complete:
                total = 0.0
            quality_usable = not any(quality_blocks_comparison(item) for item in qualities)
            usable_complete = complete and quality_usable
            applicable = not plan.planned_rest and plan.comparisons_enabled
            eligible = usable_complete and applicable
            policy = policies.get(metric)
            target = plan.daily_targets.get(metric, policy.daily_target if policy else None)
            metrics.append(
                PeriodMetricSummary(
                    metric=metric,
                    unit=METRIC_CATALOG[metric].unit,
                    observed_total=total,
                    recording_complete=complete,
                    comparison_eligible=eligible,
                    measurement_ids=sorted(item.measurement_id for item in bucket.records),
                    target_value=target,
                    target_outcome=target_outcome(
                        total, target, applicable=applicable, eligible=eligible
                    ),
                    data_quality=roll_up_quality(
                        qualities,
                        complete_days=int(usable_complete),
                        expected_days=1,
                        evaluated_at=request.evaluated_at,
                        flags=bucket.flags,
                        issues=bucket.notes,
                    ),
                    notes=list(dict.fromkeys(notes)),
                )
            )
        day_notes = [plan.notes] if plan.notes else []
        if plan.planned_rest:
            day_notes.append("Planned rest: daily targets, baselines and reduction runs suspended.")
        if not plan.comparisons_enabled:
            day_notes.append("Operational exception: activity comparisons suspended.")
        results.append(
            DailyActivitySummary(
                day=day,
                planned_rest=plan.planned_rest,
                comparisons_enabled=plan.comparisons_enabled,
                metrics=metrics,
                notes=day_notes,
            )
        )
    return results


def summarize_weeks(
    request: ActivityRequest, days: list[DailyActivitySummary]
) -> list[WeeklyActivitySummary]:
    grouped: dict[date, list[DailyActivitySummary]] = defaultdict(list)
    for day in days:
        grouped[day.day - timedelta(days=day.day.weekday())].append(day)
    policies = {item.metric: item for item in request.policies}
    weeks = []
    for week_start, week_days in sorted(grouped.items()):
        metrics = []
        applicable = any(not day.planned_rest for day in week_days) and all(
            day.comparisons_enabled for day in week_days
        )
        for index, metric in enumerate(ACTIVITY_METRICS):
            daily = [day.metrics[index] for day in week_days]
            totals = [item.observed_total for item in daily if item.observed_total is not None]
            total = finite_sum(totals) if totals else None
            complete = len(week_days) == 7 and all(item.recording_complete for item in daily)
            usable_days = sum(item.data_quality.completeness == 1 for item in daily)
            eligible = complete and usable_days == 7 and applicable
            notes = []
            if totals and total is None:
                complete, eligible = False, False
                notes.append("Weekly sum is not representable as a finite number.")
            if len(week_days) < 7:
                notes.append("Partial ISO week; weekly targets are not prorated or compared.")
            policy = policies.get(metric)
            target = policy.weekly_target if policy else None
            metrics.append(
                PeriodMetricSummary(
                    metric=metric,
                    unit=METRIC_CATALOG[metric].unit,
                    observed_total=total,
                    recording_complete=complete,
                    comparison_eligible=eligible,
                    measurement_ids=sorted(
                        measurement_id for item in daily for measurement_id in item.measurement_ids
                    ),
                    target_value=target,
                    target_outcome=target_outcome(
                        total, target, applicable=applicable, eligible=eligible
                    ),
                    data_quality=roll_up_quality(
                        (item.data_quality for item in daily),
                        complete_days=usable_days if total is not None else 0,
                        expected_days=7,
                        evaluated_at=request.evaluated_at,
                        issues=notes,
                    ),
                    notes=notes,
                )
            )
        weeks.append(
            WeeklyActivitySummary(
                week_start=week_start,
                days_in_window=len(week_days),
                metrics=metrics,
                notes=[
                    "Totals include recorded rest-day activity. Weekly targets require a full "
                    "usable week and must already reflect the planned rest schedule."
                ],
            )
        )
    return weeks


def summarize_sessions(request: ActivityRequest, prepared: PreparedRecords) -> list[SessionSummary]:
    summaries = []
    allocated_ids = {
        item.measurement_id for bucket in prepared.days.values() for item in bucket.records
    }
    for session in sorted(
        request.sessions, key=lambda item: (utc(item.start_time), item.session_id)
    ):
        end = session.end_time or request.window_end
        if utc(session.start_time) >= utc(request.window_end) or utc(end) <= utc(
            request.window_start
        ):
            continue
        records = [
            prepared.session_values[item]
            for item in session.measurement_ids
            if item in prepared.session_values
        ]
        values = {}
        notes = []
        if any(quality_blocks_comparison(item.data_quality) for item in records):
            notes.append("Retained session values have degraded or incomplete upstream quality.")
        for metric in ACTIVITY_METRICS:
            matching = [item for item in records if item.metric == metric]
            total = finite_sum(item.value for item in matching) if matching else None
            values[metric.value] = total
            if total is None:
                notes.append(f"No finite usable {metric.value} total; no value was inferred.")
        complete = (
            session.end_time is not None
            and utc(session.start_time) >= utc(request.window_start)
            and utc(session.end_time) <= utc(request.window_end)
            and len(records) == len(session.measurement_ids)
            and all(value is not None for value in values.values())
            and not any(quality_blocks_comparison(item.data_quality) for item in records)
        )
        if session.end_time is None:
            notes.append("Open session: end_time is missing.")
        elif utc(session.start_time) < utc(request.window_start) or utc(session.end_time) > utc(
            request.window_end
        ):
            notes.append("Only part of the session is inside the evaluation window.")
        if any(item.measurement_id not in allocated_ids for item in records):
            notes.append("Some session values cannot be allocated to UTC daily totals.")
        summaries.append(
            SessionSummary(
                session_id=session.session_id,
                start_time=utc(session.start_time),
                end_time=utc(session.end_time) if session.end_time else None,
                label=session.label,
                recording_complete=complete,
                measurement_ids=sorted(item.measurement_id for item in records),
                notes=notes,
                **values,
            )
        )
    return summaries
