"""Personal-baseline contract."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, FiniteFloat, model_validator

from app.models.common import AlgorithmInfo, ContractModel, Identifier, require_chronological
from app.models.data_quality import DataQuality
from app.models.metrics import MetricType, require_canonical_unit
from app.models.mission import MissionPhaseType


class BaselineStatus(StrEnum):
    """How far a baseline can be relied upon.

    The criteria that separate the statuses belong to the baseline algorithm and
    are not part of this contract.
    """

    INSUFFICIENT_DATA = "insufficient_data"
    PROVISIONAL = "provisional"
    ESTABLISHED = "established"


class BaselineStatistics(ContractModel):
    """Descriptive statistics of the data a baseline is built from.

    Every field is optional so that the baseline algorithm can choose which
    statistics it relies on. All values are expressed in the baseline's unit.
    """

    mean: FiniteFloat | None = Field(default=None, description="Arithmetic mean.")
    standard_deviation: FiniteFloat | None = Field(
        default=None, ge=0, description="Standard deviation."
    )
    median: FiniteFloat | None = Field(default=None, description="Median.")
    median_absolute_deviation: FiniteFloat | None = Field(
        default=None, ge=0, description="Median absolute deviation."
    )
    minimum: FiniteFloat | None = Field(default=None, description="Smallest value.")
    maximum: FiniteFloat | None = Field(default=None, description="Largest value.")


class PersonalBaseline(ContractModel):
    """Reference description of one metric for one crew member.

    A baseline is personal: it is computed from the crew member's own measurements
    over a reference window, not from population values.
    """

    baseline_id: Identifier = Field(description="Unique identifier of the baseline.")
    crew_member_id: Identifier = Field(description="Crew member the baseline belongs to.")
    metric: MetricType = Field(description="Metric the baseline describes.")
    unit: str = Field(description="Unit of the statistics. Must be the canonical unit of `metric`.")
    mission_phase: MissionPhaseType = Field(
        description="Mission phase the reference data was collected in."
    )
    status: BaselineStatus = Field(description="How far the baseline can be relied upon.")
    window_start: AwareDatetime = Field(description="Start of the reference window (UTC).")
    window_end: AwareDatetime = Field(description="End of the reference window (UTC).")
    sample_count: int = Field(ge=0, description="Number of measurements used.")
    statistics: BaselineStatistics = Field(description="Statistics of the reference data.")
    data_quality: DataQuality | None = Field(
        default=None, description="Quality of the reference data, when assessed."
    )
    algorithm: AlgorithmInfo = Field(description="Algorithm that computed the baseline.")
    computed_at: AwareDatetime = Field(description="When the baseline was computed (UTC).")

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        require_canonical_unit(self.metric, self.unit)
        require_chronological(
            self.window_start,
            self.window_end,
            start_field="window_start",
            end_field="window_end",
        )
        return self
