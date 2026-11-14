"""Additive application commands and list envelopes; shared resource contracts are unchanged."""

from datetime import timedelta
from typing import Generic, Literal, Self, TypeVar

from pydantic import AwareDatetime, Field, FiniteFloat, model_validator

from app.algorithms.data_quality import DataQualityConfig
from app.algorithms.personal_baseline import BaselineConfig, OutlierHandling
from app.algorithms.robust_statistics import POTENTIAL_OUTLIER_CUTOFF
from app.domains.physical_activity import ActivityDayPlan, ActivityMetricPolicy, ExerciseSession
from app.domains.physical_activity.models import ACTIVITY_METRICS, RecordingCoverage
from app.domains.sleep import SleepConfig
from app.models import ContractModel, HealthDomain, MetricType, MissionPhase, MissionPhaseType
from app.models.common import Identifier
from app.models.measurement import PhysiologicalMeasurement

Item = TypeVar("Item")
BaselineBasis = Literal["measurement", "complete_active_day_total"]


class Items(ContractModel, Generic[Item]):
    """The v0.1 list response envelope, including empty collections."""

    items: list[Item]


class MeasurementBatch(ContractModel):
    """A bounded atomic ingestion command; producer quality is replaced by engine output."""

    measurements: list[PhysiologicalMeasurement] = Field(min_length=1, max_length=1000)


class ActivityOptions(ContractModel):
    """Explicit activity recording and mission context, independent of measurement ingestion."""

    sessions: tuple[ExerciseSession, ...] = ()
    coverage: tuple[RecordingCoverage, ...] = ()
    day_plans: tuple[ActivityDayPlan, ...] = ()
    policies: tuple[ActivityMetricPolicy, ...] = ()
    reduction_run_length: int = Field(default=3, ge=3)
    baselines_comparable: bool = False
    context_notes: str | None = None


class BaselineOptions(ContractModel):
    """Engine settings with explicit provenance for establishment criteria."""

    minimum_samples: int = Field(default=2, ge=2, strict=True)
    established_min_samples: int | None = Field(default=None, ge=2, strict=True)
    established_min_span: timedelta | None = Field(default=None, gt=timedelta(0))
    policy_source: str | None = Field(default=None, min_length=1)
    outlier_cutoff: FiniteFloat | None = Field(default=POTENTIAL_OUTLIER_CUTOFF, gt=0)
    outlier_handling: OutlierHandling = OutlierHandling.REPORT

    @model_validator(mode="after")
    def _criteria_need_provenance(self) -> Self:
        if (
            self.established_min_samples is not None
            and self.established_min_samples < self.minimum_samples
        ):
            raise ValueError("established_min_samples must not be below minimum_samples")
        if (self.established_min_samples is not None or self.established_min_span is not None) and (
            self.policy_source is None or not self.policy_source.strip()
        ):
            raise ValueError("Configured establishment criteria require a nonempty policy_source")
        return self

    def engine_config(self, quality: DataQualityConfig) -> BaselineConfig:
        return BaselineConfig(
            quality=quality,
            minimum_samples=self.minimum_samples,
            established_min_samples=self.established_min_samples,
            established_min_span=self.established_min_span,
            outlier_cutoff=self.outlier_cutoff,
            outlier_handling=self.outlier_handling,
        )


class BaselineCommand(ContractModel):
    """Build one baseline from stored history and an explicit mission timeline."""

    metric: MetricType
    mission_phase: MissionPhaseType
    mission_phases: tuple[MissionPhase, ...] = Field(min_length=1)
    reference_start: AwareDatetime
    reference_end: AwareDatetime
    computed_at: AwareDatetime | None = None
    aggregation: BaselineBasis = "measurement"
    activity: ActivityOptions | None = None
    config: BaselineOptions = Field(default_factory=BaselineOptions)

    @model_validator(mode="after")
    def _validate_context(self) -> Self:
        if self.reference_end <= self.reference_start:
            raise ValueError("reference_end must be after reference_start")
        if self.computed_at is not None and self.reference_end > self.computed_at:
            raise ValueError("reference_end cannot follow computed_at")
        if len({phase.phase_id for phase in self.mission_phases}) != len(self.mission_phases):
            raise ValueError("Mission phase identifiers must be unique")
        if self.aggregation == "complete_active_day_total" and self.metric not in ACTIVITY_METRICS:
            raise ValueError("Daily active-day aggregation requires a physical-activity metric")
        if self.aggregation == "measurement" and self.activity is not None:
            raise ValueError(
                "activity context applies only to complete_active_day_total aggregation"
            )
        return self


class EvaluationCommand(ContractModel):
    """Generate an evaluation from stored, assessed measurements, never client-supplied results."""

    domain: Literal[HealthDomain.SLEEP, HealthDomain.PHYSICAL_ACTIVITY]
    window_start: AwareDatetime
    window_end: AwareDatetime
    evaluated_at: AwareDatetime | None = None
    mission_phase: MissionPhaseType | None = None
    baseline_ids: tuple[Identifier, ...] = ()
    sleep_config: SleepConfig | None = None
    activity: ActivityOptions | None = None

    @model_validator(mode="after")
    def _validate_context(self) -> Self:
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.evaluated_at is not None and self.window_end > self.evaluated_at:
            raise ValueError("window_end cannot follow evaluated_at")
        if len(set(self.baseline_ids)) != len(self.baseline_ids):
            raise ValueError("baseline_ids must be unique")
        if self.baseline_ids and self.mission_phase is None:
            raise ValueError("An explicit mission_phase is required when selecting baselines")
        if self.domain == HealthDomain.SLEEP and self.activity is not None:
            raise ValueError("activity options cannot be supplied for sleep evaluations")
        if self.domain == HealthDomain.PHYSICAL_ACTIVITY and self.sleep_config is not None:
            raise ValueError("sleep_config cannot be supplied for physical-activity evaluations")
        return self
