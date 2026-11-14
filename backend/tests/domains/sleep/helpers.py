"""Fictional sleep fixtures, labelled simulated and independent of all engines."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domains.sleep import SleepConfig, SleepTrend, analyze_sleep_trends
from app.domains.sleep.demo import demonstration_config
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    BaselineStatistics,
    BaselineStatus,
    DataQuality,
    EvaluationResult,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityStatus,
)

START = datetime(2026, 11, 1, 12, tzinfo=UTC)
END = START + timedelta(days=7)
CREW = "synthetic-crew"


def measurement(
    night: int = 0,
    value: float = 480.0,
    metric: MetricType = MetricType.SLEEP_DURATION,
    **overrides: Any,
) -> PhysiologicalMeasurement:
    at = START + timedelta(days=night, hours=10)
    payload = {
        "measurement_id": f"synthetic-{metric.value}-{night}",
        "crew_member_id": CREW,
        "metric": metric,
        "unit": METRIC_CATALOG[metric].unit,
        "value": value,
        "measured_at": at,
        "interval_end": at + timedelta(hours=9),
        "source": MeasurementSource.SIMULATED,
        **overrides,
    }
    return PhysiologicalMeasurement.model_validate(payload)


def series(
    values: Iterable[float], metric: MetricType = MetricType.SLEEP_DURATION
) -> list[PhysiologicalMeasurement]:
    return [measurement(night, value, metric) for night, value in enumerate(values)]


def both_metrics() -> list[PhysiologicalMeasurement]:
    return series([480.0] * 7) + series([92.0] * 7, MetricType.SLEEP_EFFICIENCY)


def analyze(
    measurements: Iterable[PhysiologicalMeasurement],
    config: SleepConfig | None = None,
    **overrides: Any,
) -> tuple[SleepTrend, SleepTrend]:
    arguments = {
        "crew_member_id": CREW,
        "window_start": START,
        "window_end": END,
        "config": config if config is not None else demonstration_config(),
        **overrides,
    }
    return analyze_sleep_trends(measurements, **arguments)


def baseline(metric: MetricType = MetricType.SLEEP_DURATION, **overrides: Any) -> PersonalBaseline:
    # Established is a manually assigned fixture label, not an engine result.
    reference = 480.0 if metric == MetricType.SLEEP_DURATION else 92.0
    payload = {
        "baseline_id": f"synthetic-reference-{metric.value}",
        "crew_member_id": CREW,
        "metric": metric,
        "unit": METRIC_CATALOG[metric].unit,
        "mission_phase": MissionPhaseType.PRE_FLIGHT,
        "status": BaselineStatus.ESTABLISHED,
        "window_start": START - timedelta(days=15),
        "window_end": START - timedelta(days=1),
        "sample_count": 14,
        "statistics": BaselineStatistics(median=reference, mean=reference + 1),
        "data_quality": DataQuality(status=QualityStatus.NOT_ASSESSED),
        "algorithm": AlgorithmInfo(name="synthetic_fixture_not_an_engine", version="0.0.0"),
        "computed_at": START - timedelta(days=1),
        **overrides,
    }
    return PersonalBaseline.model_validate(payload)


def evaluate(
    measurements: Iterable[PhysiologicalMeasurement] | None = None, **overrides: Any
) -> EvaluationResult:
    from app.domains.sleep import evaluate_sleep_window

    arguments = {
        "evaluation_id": "synthetic-evaluation",
        "crew_member_id": CREW,
        "window_start": START,
        "window_end": END,
        "evaluated_at": END,
        "config": demonstration_config(),
        **overrides,
    }
    return evaluate_sleep_window(
        measurements if measurements is not None else both_metrics(), **arguments
    )
