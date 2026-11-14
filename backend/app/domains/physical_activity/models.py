"""Domain-local inputs and descriptive outputs; these do not extend the public API."""

from datetime import UTC, date, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Literal, Self
from uuid import uuid4

from pydantic import AwareDatetime, Field, FiniteFloat, model_validator

from app.models import (
    ContractModel,
    DataQuality,
    EvaluationResult,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)
from app.models.common import Identifier

ActivityMetric = Literal[MetricType.EXERCISE_DURATION, MetricType.ACTIVE_ENERGY_EXPENDITURE]
NonNegativeValue = Annotated[FiniteFloat, Field(ge=0)]
ACTIVITY_METRICS = (MetricType.EXERCISE_DURATION, MetricType.ACTIVE_ENERGY_EXPENDITURE)


class TargetOutcome(StrEnum):
    """Recording-aware adherence to a personal operational target."""

    MET = "met"
    MISSED = "missed"
    UNKNOWN = "unknown"
    NOT_CONFIGURED = "not_configured"
    NOT_APPLICABLE = "not_applicable"


class ActivityMetricPolicy(ContractModel):
    """Values are in the metric's canonical unit; tolerances are review settings."""

    metric: ActivityMetric
    daily_target: NonNegativeValue | None = None
    weekly_target: NonNegativeValue | None = None
    baseline_absolute_tolerance: NonNegativeValue | None = None
    baseline_relative_tolerance: NonNegativeValue | None = None


class RecordingCoverage(ContractModel):
    """Caller confirmation that all additive records for one UTC day are present.

    An empty list of measurements is not evidence of a zero-activity day. Only an
    explicit, complete coverage record can confirm zero. Quality remains separate.
    """

    day: date
    metric: ActivityMetric
    complete: bool
    quality: DataQuality | None = None
    notes: str | None = None


class ActivityDayPlan(ContractModel):
    """Mission-team context, never inferred from low activity or missing records."""

    day: date
    planned_rest: bool = False
    comparisons_enabled: bool = True
    daily_targets: dict[ActivityMetric, NonNegativeValue] = Field(default_factory=dict)
    notes: str | None = None


class DailyBaselineReference(ContractModel):
    """Explicit adapter for the aggregation semantics absent from PersonalBaseline.

    The caller certifies compatible acquisition, device calibration and active-day
    context. Session-level baselines cannot be compared with daily totals.
    """

    baseline: PersonalBaseline
    comparison_basis: Literal["complete_active_day_total"]
    comparable: bool


class ExerciseSession(ContractModel):
    """Explicit links to additive measurements; elapsed time is never a metric value."""

    session_id: Identifier
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    measurement_ids: tuple[Identifier, ...] = ()
    label: str | None = None

    @model_validator(mode="after")
    def _validate_session(self) -> Self:
        if self.end_time is not None and self.end_time <= self.start_time:
            raise ValueError("A closed session must end after its start_time")
        if len(set(self.measurement_ids)) != len(self.measurement_ids):
            raise ValueError("Session measurement_ids must be unique")
        return self


class ActivityRequest(ContractModel):
    """One crew member, one mission phase, and a half-open evaluation window."""

    crew_member_id: Identifier
    window_start: AwareDatetime
    window_end: AwareDatetime
    measurements: tuple[PhysiologicalMeasurement, ...] = ()
    sessions: tuple[ExerciseSession, ...] = ()
    coverage: tuple[RecordingCoverage, ...] = ()
    day_plans: tuple[ActivityDayPlan, ...] = ()
    policies: tuple[ActivityMetricPolicy, ...] = ()
    baselines: tuple[DailyBaselineReference, ...] = ()
    mission_phase: MissionPhaseType | None = None
    context_notes: str | None = None
    # Three observations give two successive falls: a descriptive design convention,
    # not a physiological threshold or a statistical significance test.
    reduction_run_length: int = Field(default=3, ge=3)
    evaluation_id: Identifier = Field(default_factory=lambda: str(uuid4()))
    evaluated_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_request(self) -> Self:
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.window_end > self.evaluated_at:
            raise ValueError("window_end cannot be after evaluated_at")
        unique_keys = (
            ([(item.day, item.metric) for item in self.coverage], "coverage day/metric"),
            ([item.day for item in self.day_plans], "day plan"),
            ([item.metric for item in self.policies], "metric policy"),
            ([item.session_id for item in self.sessions], "session_id"),
            ([item.baseline.baseline_id for item in self.baselines], "baseline_id"),
        )
        for keys, label in unique_keys:
            if len(keys) != len(set(keys)):
                raise ValueError(f"Duplicate {label}")

        by_id: dict[str, PhysiologicalMeasurement] = {}
        for measurement in self.measurements:
            if measurement.crew_member_id != self.crew_member_id:
                raise ValueError("All measurements must belong to crew_member_id")
            if measurement.metric not in ACTIVITY_METRICS:
                raise ValueError("Only canonical physical-activity metrics are supported")
            previous = by_id.get(measurement.measurement_id)
            if previous is not None and previous != measurement:
                raise ValueError(f"Conflicting measurement_id: {measurement.measurement_id}")
            by_id[measurement.measurement_id] = measurement

        assigned: set[str] = set()
        for session in self.sessions:
            for measurement_id in session.measurement_ids:
                if measurement_id not in by_id:
                    raise ValueError(f"Unknown session measurement_id: {measurement_id}")
                if measurement_id in assigned:
                    raise ValueError("A measurement cannot belong to multiple sessions")
                assigned.add(measurement_id)
                measurement = by_id[measurement_id]
                end = measurement.interval_end or measurement.measured_at
                if measurement.measured_at < session.start_time or (
                    session.end_time is not None
                    and (end > session.end_time or measurement.measured_at >= session.end_time)
                ):
                    raise ValueError("Linked measurement must be contained in its session")
        closed_sessions = sorted(
            (session for session in self.sessions if session.end_time is not None),
            key=lambda session: (session.start_time, session.session_id),
        )
        for previous, current in pairwise(closed_sessions):
            if current.start_time < previous.end_time:
                raise ValueError(
                    "Closed exercise sessions must not overlap; reconcile session logs"
                )
        return self


class PeriodMetricSummary(ContractModel):
    """A total is a known subtotal when recording_complete is false."""

    metric: ActivityMetric
    unit: str
    observed_total: FiniteFloat | None
    recording_complete: bool
    comparison_eligible: bool
    measurement_ids: list[str] = Field(default_factory=list)
    target_value: NonNegativeValue | None = None
    target_outcome: TargetOutcome
    absolute_change: FiniteFloat | None = None
    relative_change: FiniteFloat | None = None
    data_quality: DataQuality
    notes: list[str] = Field(default_factory=list)


class DailyActivitySummary(ContractModel):
    """UTC day intersected with the requested window."""

    day: date
    planned_rest: bool
    comparisons_enabled: bool
    metrics: list[PeriodMetricSummary]
    notes: list[str] = Field(default_factory=list)


class WeeklyActivitySummary(ContractModel):
    """ISO week, Monday inclusive through the following Monday exclusive."""

    week_start: date
    days_in_window: int
    metrics: list[PeriodMetricSummary]
    notes: list[str] = Field(default_factory=list)


class SessionSummary(ContractModel):
    """Session observations, including values that cannot be allocated to UTC days."""

    session_id: str
    start_time: AwareDatetime
    end_time: AwareDatetime | None
    label: str | None
    exercise_duration: FiniteFloat | None
    active_energy_expenditure: FiniteFloat | None
    recording_complete: bool
    measurement_ids: list[str]
    notes: list[str] = Field(default_factory=list)


class ActivityTrend(ContractModel):
    """A maximal, uninterrupted, strictly decreasing run of comparable totals."""

    metric: ActivityMetric
    period: Literal["daily", "weekly"]
    start_day: date
    end_day: date
    values: list[FiniteFloat]
    absolute_change: FiniteFloat
    relative_change: FiniteFloat | None
    explanation: str


class ActivityReport(ContractModel):
    """Internal detail plus an unchanged, directly serializable shared evaluation."""

    evaluation: EvaluationResult
    days: list[DailyActivitySummary]
    weeks: list[WeeklyActivitySummary]
    sessions: list[SessionSummary]
    trends: list[ActivityTrend]
    notices: list[str]
