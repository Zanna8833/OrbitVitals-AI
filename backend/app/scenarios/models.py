"""Local replay envelopes; no HTTP contract or generated schema is extended."""

from typing import Literal, Self

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from app.domains.physical_activity import ActivityReport, ActivityRequest
from app.domains.sleep import SleepTrend
from app.models import (
    ContractModel,
    DataQuality,
    EvaluationResult,
    MeasurementSource,
    MetricFinding,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)

SIMULATION_NOTICE = (
    "SIMULATED DATA: deterministic research demonstrations, not astronaut records, "
    "clinical validation, diagnoses or medical recommendations."
)


class ScenarioInfo(ContractModel):
    """Stable catalog metadata, separate from running any algorithm."""

    scenario_id: str
    title: str
    scientific_purpose: str
    data_kind: Literal["simulated"] = "simulated"
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]


class BehaviorCheck(ContractModel):
    """A regression expectation compared with a value obtained from an engine."""

    check_id: str
    description: str
    expected: JsonValue
    actual: JsonValue
    passed: bool

    @model_validator(mode="after")
    def _consistent_comparison(self) -> Self:
        if self.passed != (self.expected == self.actual):
            raise ValueError("passed must reflect the expected versus actual comparison")
        return self


class RejectedInput(ContractModel):
    """A deliberately invalid input, explicitly outside the measurement contract."""

    data_kind: Literal["simulated"] = "simulated"
    payload: dict[str, JsonValue]
    validation_errors: tuple[str, ...]


class ReplayInputs(ContractModel):
    """Exact inputs and policy settings available at one replay checkpoint."""

    data_kind: Literal["simulated"] = "simulated"
    measurements: tuple[PhysiologicalMeasurement, ...] = ()
    mission_phases: tuple[MissionPhase, ...] = ()
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    activity_request: ActivityRequest | None = None
    rejected_candidates: tuple[dict[str, JsonValue], ...] = ()

    @model_validator(mode="after")
    def _only_simulated_data(self) -> Self:
        records = self.measurements + (
            self.activity_request.measurements if self.activity_request is not None else ()
        )
        if any(record.source != MeasurementSource.SIMULATED for record in records):
            raise ValueError("Scenario inputs must be explicitly simulated")
        if any(payload.get("source") != "simulated" for payload in self.rejected_candidates):
            raise ValueError("Rejected candidates must be explicitly simulated")
        return self


class QualityWindow(ContractModel):
    """Scope of a real, per-metric Data Quality engine assessment."""

    metric: MetricType
    window_start: AwareDatetime
    window_end: AwareDatetime
    assessment: DataQuality


class BaselineQuery(ContractModel):
    """A real engine lookup; None represents an unavailable reference window."""

    metric: MetricType
    mission_phase: MissionPhaseType
    baseline: PersonalBaseline | None


class ReplayOutputs(ContractModel):
    """Actual engine outputs, retaining their original models and provenance."""

    data_kind: Literal["simulated"] = "simulated"
    assessed_measurements: tuple[PhysiologicalMeasurement, ...] = ()
    quality_windows: tuple[QualityWindow, ...] = ()
    baselines: tuple[PersonalBaseline, ...] = ()
    baseline_queries: tuple[BaselineQuery, ...] = ()
    evaluations: tuple[EvaluationResult, ...] = ()
    observation_findings: tuple[MetricFinding, ...] = ()
    sleep_trends: tuple[SleepTrend, ...] = ()
    activity_report: ActivityReport | None = None
    rejected_inputs: tuple[RejectedInput, ...] = ()

    @model_validator(mode="after")
    def _only_simulated_measurements(self) -> Self:
        if any(
            record.source != MeasurementSource.SIMULATED for record in self.assessed_measurements
        ):
            raise ValueError("Scenario outputs must retain the simulated source label")
        return self


class ReplayStep(ContractModel):
    """An ordered, reproducible checkpoint for a future dashboard timeline."""

    step_id: str
    as_of: AwareDatetime
    explanation: str
    inputs: ReplayInputs
    outputs: ReplayOutputs
    checks: tuple[BehaviorCheck, ...]
    blockers: tuple[str, ...] = ()


class ReplayResult(ContractModel):
    """Versioned local artifact containing existing contract-compatible payloads."""

    replay_format_version: Literal["0.1.0"] = "0.1.0"
    data_kind: Literal["simulated"] = "simulated"
    notice: Literal[SIMULATION_NOTICE] = SIMULATION_NOTICE
    scenario: ScenarioInfo
    steps: tuple[ReplayStep, ...]
    all_checks_passed: bool

    @model_validator(mode="after")
    def _consistent_result(self) -> Self:
        if not self.steps or len({step.step_id for step in self.steps}) != len(self.steps):
            raise ValueError("A replay requires non-empty steps with unique identifiers")
        expected = all(
            step.checks and not step.blockers and all(check.passed for check in step.checks)
            for step in self.steps
        )
        if self.all_checks_passed != expected:
            raise ValueError("all_checks_passed must reflect all step checks and blockers")
        return self
