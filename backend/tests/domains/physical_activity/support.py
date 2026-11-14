"""Deterministic simulated fixtures for physical-activity tests."""

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domains.physical_activity import (
    ActivityMetricPolicy,
    ActivityRequest,
    DailyBaselineReference,
    RecordingCoverage,
)
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    BaselineStatistics,
    BaselineStatus,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)

START = datetime(2026, 11, 2, tzinfo=UTC)  # Monday, used only for simulated records.
DURATION = MetricType.EXERCISE_DURATION
ENERGY = MetricType.ACTIVE_ENERGY_EXPENDITURE


def measurement(
    value: float = 30,
    metric: MetricType = DURATION,
    measurement_id: str = "sim-m1",
    **overrides: Any,
) -> PhysiologicalMeasurement:
    return PhysiologicalMeasurement.model_validate(
        {
            "measurement_id": measurement_id,
            "crew_member_id": "sim-crew",
            "metric": metric,
            "unit": METRIC_CATALOG[metric].unit,
            "value": value,
            "measured_at": START + timedelta(hours=9),
            "source": MeasurementSource.SIMULATED,
            **overrides,
        }
    )


def request(**overrides: Any) -> ActivityRequest:
    return ActivityRequest.model_validate(
        {
            "crew_member_id": "sim-crew",
            "window_start": START,
            "window_end": START + timedelta(days=1),
            "evaluated_at": START + timedelta(days=30),
            "evaluation_id": "sim-evaluation",
            "mission_phase": MissionPhaseType.IN_FLIGHT,
            "policies": (
                ActivityMetricPolicy(metric=DURATION, daily_target=20),
                ActivityMetricPolicy(metric=ENERGY, daily_target=100),
            ),
            **overrides,
        }
    )


def series(
    durations: list[float | None], energies: list[float | None] | None = None, **overrides: Any
) -> ActivityRequest:
    # Independent fabricated energy values; production code never estimates calories.
    if energies is None:
        energies = [200 if value is not None else None for value in durations]
    assert len(durations) == len(energies)
    records = []
    coverage = []
    for offset, values in enumerate(zip(durations, energies, strict=True)):
        for metric, value in zip((DURATION, ENERGY), values, strict=True):
            if value is None:
                continue
            instant = START + timedelta(days=offset, hours=9)
            records.append(
                measurement(value, metric, f"sim-{offset}-{metric}", measured_at=instant)
            )
            coverage.append(RecordingCoverage(day=instant.date(), metric=metric, complete=True))
    return request(
        **{
            "window_end": START + timedelta(days=len(durations)),
            "measurements": records,
            "coverage": coverage,
            **overrides,
        }
    )


def replace_request(original: ActivityRequest, **overrides: Any) -> ActivityRequest:
    return ActivityRequest.model_validate({**original.model_dump(), **overrides})


def baseline_reference(**overrides: Any) -> DailyBaselineReference:
    baseline = PersonalBaseline.model_validate(
        {
            "baseline_id": "sim-daily-baseline",
            "crew_member_id": "sim-crew",
            "metric": DURATION,
            "unit": "min",
            "mission_phase": MissionPhaseType.IN_FLIGHT,
            "status": BaselineStatus.ESTABLISHED,
            "window_start": START - timedelta(days=21),
            "window_end": START - timedelta(days=7),
            "sample_count": 14,
            "statistics": BaselineStatistics(mean=40, standard_deviation=5),
            "algorithm": AlgorithmInfo(name="simulated_reference_fixture", version="0.1.0"),
            "computed_at": START - timedelta(days=6),
            **overrides,
        }
    )
    return DailyBaselineReference(
        baseline=baseline, comparison_basis="complete_active_day_total", comparable=True
    )
