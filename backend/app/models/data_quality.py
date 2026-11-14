"""Data-quality contract."""

from enum import StrEnum

from pydantic import AwareDatetime, Field

from app.models.common import AlgorithmInfo, ContractModel, UnitInterval


class QualityStatus(StrEnum):
    """Overall usability of the assessed data. It is not a health status.

    `not_assessed` means no quality algorithm has processed the data yet.
    """

    NOT_ASSESSED = "not_assessed"
    ACCEPTABLE = "acceptable"
    DEGRADED = "degraded"
    UNUSABLE = "unusable"


class QualityFlag(StrEnum):
    """Specific issues found while assessing data quality.

    `out_of_sensor_range` refers to the measuring range documented for the device.
    It is a property of the sensor, not a clinical threshold.
    """

    MISSING_DATA = "missing_data"
    OUT_OF_SENSOR_RANGE = "out_of_sensor_range"
    SIGNAL_ARTIFACT = "signal_artifact"
    DUPLICATE = "duplicate"
    INSUFFICIENT_SAMPLES = "insufficient_samples"


class DataQuality(ContractModel):
    """Quality assessment of one measurement or of a window of measurements.

    Data quality describes the data, not the crew member: it says how far the values
    can be trusted and carries no physiological meaning. The physiological status is
    reported separately, by `EvaluationStatus`.

    The rules that assign `status`, `score` and `flags` belong to the data-quality
    algorithm and are not part of this contract.
    """

    status: QualityStatus = Field(description="Overall usability of the data.")
    score: UnitInterval | None = Field(
        default=None,
        description="Overall quality from 0 (worst) to 1 (best). Null when no score is computed.",
    )
    completeness: UnitInterval | None = Field(
        default=None,
        description="Fraction of the expected samples that are present. Null when not applicable.",
    )
    flags: list[QualityFlag] = Field(
        default_factory=list, description="Issues found during the assessment."
    )
    notes: str | None = Field(default=None, description="Optional human-readable remarks.")
    algorithm: AlgorithmInfo | None = Field(
        default=None,
        description="Algorithm that produced the assessment. Null when not assessed.",
    )
    assessed_at: AwareDatetime | None = Field(
        default=None,
        description="When the assessment was produced (UTC). Null when not assessed.",
    )
