"""Catalog of the physiological metrics handled by OrbitVitals.

The list is an initial proposal, open to review by the team. To add a metric, add a
`MetricType` member and its `MetricDefinition`, then regenerate the schemas.
"""

from enum import StrEnum

from pydantic import Field

from app.models.common import ContractModel, HealthDomain


class MetricType(StrEnum):
    """Physiological metrics that can be measured, baselined and evaluated."""

    HEART_RATE = "heart_rate"
    HEART_RATE_VARIABILITY_RMSSD = "heart_rate_variability_rmssd"
    RESPIRATORY_RATE = "respiratory_rate"
    BLOOD_OXYGEN_SATURATION = "blood_oxygen_saturation"
    BODY_TEMPERATURE = "body_temperature"
    SYSTOLIC_BLOOD_PRESSURE = "systolic_blood_pressure"
    DIASTOLIC_BLOOD_PRESSURE = "diastolic_blood_pressure"
    SLEEP_DURATION = "sleep_duration"
    SLEEP_EFFICIENCY = "sleep_efficiency"
    EXERCISE_DURATION = "exercise_duration"
    ACTIVE_ENERGY_EXPENDITURE = "active_energy_expenditure"
    ENERGY_INTAKE = "energy_intake"
    PROTEIN_INTAKE = "protein_intake"
    FLUID_INTAKE = "fluid_intake"
    BODY_MASS = "body_mass"


class MetricDefinition(ContractModel):
    """Static description of a metric: where it belongs and how it is expressed."""

    metric: MetricType = Field(description="Metric identifier.")
    domain: HealthDomain = Field(description="Functional area the metric belongs to.")
    unit: str = Field(description="Canonical unit. Every value of this metric uses it.")
    description: str = Field(description="Short human-readable definition.")


_DEFINITIONS = (
    MetricDefinition(
        metric=MetricType.HEART_RATE,
        domain=HealthDomain.VITAL_SIGNS,
        unit="bpm",
        description="Heart rate.",
    ),
    MetricDefinition(
        metric=MetricType.HEART_RATE_VARIABILITY_RMSSD,
        domain=HealthDomain.VITAL_SIGNS,
        unit="ms",
        description=(
            "Heart rate variability, as the root mean square of successive "
            "differences between heartbeats (RMSSD)."
        ),
    ),
    MetricDefinition(
        metric=MetricType.RESPIRATORY_RATE,
        domain=HealthDomain.VITAL_SIGNS,
        unit="breaths/min",
        description="Respiratory rate.",
    ),
    MetricDefinition(
        metric=MetricType.BLOOD_OXYGEN_SATURATION,
        domain=HealthDomain.VITAL_SIGNS,
        unit="%",
        description="Peripheral blood oxygen saturation (SpO2).",
    ),
    MetricDefinition(
        metric=MetricType.BODY_TEMPERATURE,
        domain=HealthDomain.VITAL_SIGNS,
        unit="degC",
        description="Body temperature.",
    ),
    MetricDefinition(
        metric=MetricType.SYSTOLIC_BLOOD_PRESSURE,
        domain=HealthDomain.VITAL_SIGNS,
        unit="mmHg",
        description="Systolic blood pressure.",
    ),
    MetricDefinition(
        metric=MetricType.DIASTOLIC_BLOOD_PRESSURE,
        domain=HealthDomain.VITAL_SIGNS,
        unit="mmHg",
        description="Diastolic blood pressure.",
    ),
    MetricDefinition(
        metric=MetricType.SLEEP_DURATION,
        domain=HealthDomain.SLEEP,
        unit="min",
        description="Total sleep time within a sleep period.",
    ),
    MetricDefinition(
        metric=MetricType.SLEEP_EFFICIENCY,
        domain=HealthDomain.SLEEP,
        unit="%",
        description="Share of the time in bed that was spent asleep.",
    ),
    MetricDefinition(
        metric=MetricType.EXERCISE_DURATION,
        domain=HealthDomain.PHYSICAL_ACTIVITY,
        unit="min",
        description="Duration of a physical exercise session.",
    ),
    MetricDefinition(
        metric=MetricType.ACTIVE_ENERGY_EXPENDITURE,
        domain=HealthDomain.PHYSICAL_ACTIVITY,
        unit="kcal",
        description="Energy expended through physical activity.",
    ),
    MetricDefinition(
        metric=MetricType.ENERGY_INTAKE,
        domain=HealthDomain.NUTRITION,
        unit="kcal",
        description="Dietary energy intake.",
    ),
    MetricDefinition(
        metric=MetricType.PROTEIN_INTAKE,
        domain=HealthDomain.NUTRITION,
        unit="g",
        description="Dietary protein intake.",
    ),
    MetricDefinition(
        metric=MetricType.FLUID_INTAKE,
        domain=HealthDomain.NUTRITION,
        unit="mL",
        description="Fluid intake.",
    ),
    MetricDefinition(
        metric=MetricType.BODY_MASS,
        domain=HealthDomain.NUTRITION,
        unit="kg",
        description="Body mass.",
    ),
)

METRIC_CATALOG: dict[MetricType, MetricDefinition] = {
    definition.metric: definition for definition in _DEFINITIONS
}


def require_canonical_unit(metric: MetricType, unit: str) -> None:
    """Raise `ValueError` unless `unit` is the canonical unit of `metric`.

    Unit conversion happens once, where data enters the system, so that every
    algorithm can rely on a single unit per metric.
    """
    expected = METRIC_CATALOG[metric].unit
    if unit != expected:
        raise ValueError(
            f"unit '{unit}' is not the canonical unit of metric '{metric.value}' "
            f"(expected '{expected}')"
        )
