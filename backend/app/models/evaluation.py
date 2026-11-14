"""Evaluation-result contract."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, FiniteFloat, model_validator

from app.models.common import (
    AlgorithmInfo,
    ContractModel,
    HealthDomain,
    Identifier,
    require_chronological,
)
from app.models.data_quality import DataQuality
from app.models.metrics import MetricType, require_canonical_unit
from app.models.mission import MissionPhaseType


class EvaluationStatus(StrEnum):
    """Physiological status of a crew member relative to the personal baseline.

    It describes the crew member, not the data: how far the underlying data can be
    trusted is reported separately, in `data_quality`. `insufficient_data` means
    that no physiological status could be determined.

    These are labels only. The rules that map a deviation to a status are owned by
    the scientific algorithms and are not part of this contract: no clinical
    threshold is defined here.
    """

    NOMINAL = "nominal"
    ATTENTION = "attention"
    ALERT = "alert"
    INSUFFICIENT_DATA = "insufficient_data"


class MetricFinding(ContractModel):
    """Evaluation of a single metric within an evaluation window."""

    metric: MetricType = Field(description="Evaluated metric.")
    unit: str = Field(
        description="Unit of the values below. Must be the canonical unit of `metric`."
    )
    status: EvaluationStatus = Field(description="Physiological status for this metric.")
    observed_value: FiniteFloat | None = Field(
        default=None,
        description=(
            "Value observed in the window, aggregated as defined by the algorithm. "
            "Null when it cannot be computed."
        ),
    )
    baseline_id: Identifier | None = Field(
        default=None, description="Baseline used for the comparison, when there is one."
    )
    baseline_value: FiniteFloat | None = Field(
        default=None, description="Reference value taken from the baseline."
    )
    absolute_deviation: FiniteFloat | None = Field(
        default=None, description="`observed_value` minus `baseline_value`, in `unit`."
    )
    relative_deviation: FiniteFloat | None = Field(
        default=None,
        description=(
            "`absolute_deviation` divided by `baseline_value`. Dimensionless: "
            "-0.05 means 5% below the baseline."
        ),
    )
    explanation: str = Field(
        min_length=1, description="Plain-language account of how the status was reached."
    )
    data_quality: DataQuality | None = Field(
        default=None, description="Quality of the data behind this finding, when assessed."
    )

    @model_validator(mode="after")
    def _check_unit(self) -> Self:
        require_canonical_unit(self.metric, self.unit)
        return self


class EvaluationResult(ContractModel):
    """Evaluation of one health domain for one crew member over a time window.

    Results support decisions made by people. They are not diagnoses.
    """

    evaluation_id: Identifier = Field(description="Unique identifier of the evaluation.")
    crew_member_id: Identifier = Field(description="Evaluated crew member.")
    domain: HealthDomain = Field(description="Evaluated health domain.")
    mission_phase: MissionPhaseType | None = Field(
        default=None, description="Mission phase the window falls in, when known."
    )
    window_start: AwareDatetime = Field(description="Start of the evaluated window (UTC).")
    window_end: AwareDatetime = Field(description="End of the evaluated window (UTC).")
    status: EvaluationStatus = Field(description="Overall physiological status for the domain.")
    summary: str = Field(min_length=1, description="Plain-language summary of the evaluation.")
    findings: list[MetricFinding] = Field(description="Per-metric outcomes. May be empty.")
    data_quality: DataQuality = Field(description="Quality of the data behind the evaluation.")
    algorithm: AlgorithmInfo = Field(description="Algorithm that produced the evaluation.")
    evaluated_at: AwareDatetime = Field(description="When the evaluation was produced (UTC).")

    @model_validator(mode="after")
    def _check_window(self) -> Self:
        require_chronological(
            self.window_start,
            self.window_end,
            start_field="window_start",
            end_field="window_end",
        )
        return self
