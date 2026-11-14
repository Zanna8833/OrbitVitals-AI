"""Hand-authored synthetic scenarios; run with python -m app.domains.sleep.demo."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from json import dumps

from app.domains.sleep.config import MetricThresholds, SleepConfig
from app.domains.sleep.evaluation import analyze_sleep_observation, evaluate_sleep_window
from app.models import (
    METRIC_CATALOG,
    MeasurementSource,
    MetricType,
    PhysiologicalMeasurement,
)


@dataclass(frozen=True)
class DemoScenario:
    """Reproducible measurements and the exact window to evaluate."""

    name: str
    description: str
    measurements: tuple[PhysiologicalMeasurement, ...]
    window_start: datetime
    window_end: datetime


def demonstration_config() -> SleepConfig:
    """Return illustrative engineering choices with no clinical interpretation."""
    # Source: README.md, "Synthetic demonstrations". Every numeric value here is
    # a hand-selected fixture for exercising behavior, not an empirical cutoff.
    return SleepConfig(
        policy_id="synthetic_demonstration_only_v1",
        duration=MetricThresholds(
            minimum_slope_per_day=5.0,
            minimum_total_change=30.0,
            minimum_observation_deviation=60.0,
        ),
        efficiency=MetricThresholds(
            minimum_slope_per_day=0.5,
            minimum_total_change=3.0,
            minimum_observation_deviation=5.0,
        ),
        minimum_nights=4,
        minimum_coverage=0.6,
        minimum_span_days=3.0,
        maximum_consecutive_missing_nights=2,
        minimum_decreasing_fraction=0.75,
        night_start_hour_utc=12,
    )


def _scenario(
    name: str,
    description: str,
    durations: tuple[float, ...],
    efficiencies: tuple[float, ...],
    *,
    missing: tuple[int, ...] = (),
    hour_offsets: tuple[int, ...] = (0, 0, 0, 0, 0, 0, 0),
    partial_edges: bool = False,
) -> DemoScenario:
    # Source: README.md, "Synthetic demonstrations": arbitrary synthetic dates,
    # seven daily primary sleep periods, normally starting at 22:00 UTC with a
    # nine-hour observation interval. These fixtures describe no real person.
    start = datetime(2026, 11, 1, 12, tzinfo=UTC)
    end = start + timedelta(days=7)
    measurements = []
    for index, (duration, efficiency, offset) in enumerate(
        zip(durations, efficiencies, hour_offsets, strict=True)
    ):
        if index in missing:
            continue
        at = start + timedelta(days=index, hours=10 + offset)
        for metric, value in (
            (MetricType.SLEEP_DURATION, duration),
            (MetricType.SLEEP_EFFICIENCY, efficiency),
        ):
            measurements.append(
                PhysiologicalMeasurement(
                    measurement_id=f"{name}-{index}-{metric.value}",
                    crew_member_id="synthetic-crew",
                    metric=metric,
                    unit=METRIC_CATALOG[metric].unit,
                    value=value,
                    measured_at=at,
                    interval_end=at + timedelta(hours=9),
                    source=MeasurementSource.SIMULATED,
                    device_id="synthetic-sleep-generator",
                )
            )
    if partial_edges:
        start += timedelta(hours=6)
        end -= timedelta(hours=6)
    return DemoScenario(name, description, tuple(measurements), start, end)


def demonstration_scenarios() -> tuple[DemoScenario, ...]:
    """Create fresh, labelled fixtures without random numbers or external data."""
    # Source: README.md, "Synthetic demonstrations": values and linear ramps are
    # deliberately constructed to exercise the configured statistical rules.
    stable_duration = (480.0,) * 7
    stable_efficiency = (92.0,) * 7
    decreasing_duration = tuple(480.0 - 20.0 * index for index in range(7))
    decreasing_efficiency = tuple(92.0 - 2.0 * index for index in range(7))
    increasing_efficiency = tuple(80.0 + 2.0 * index for index in range(7))
    offsets = (0, 2, -1, 1, 0, -2, 2)
    irregular_duration = tuple(
        480.0 - 20.0 * (index + offset / 24) for index, offset in enumerate(offsets)
    )
    return (
        _scenario(
            "stable",
            "Constant synthetic values; no configured trend is expected.",
            stable_duration,
            stable_efficiency,
        ),
        _scenario(
            "duration_reduction",
            "A constructed progressive reduction of 20 minutes per elapsed day.",
            decreasing_duration,
            stable_efficiency,
        ),
        _scenario(
            "efficiency_decrease",
            "A constructed efficiency reduction of two percentage points per day.",
            stable_duration,
            decreasing_efficiency,
        ),
        _scenario(
            "efficiency_increase",
            "An increasing efficiency pattern is also a change requiring interpretation.",
            stable_duration,
            increasing_efficiency,
        ),
        _scenario(
            "missing_nights",
            "Two isolated missing nights remain absent; elapsed-time slope is preserved.",
            decreasing_duration,
            stable_efficiency,
            missing=(1, 4),
        ),
        _scenario(
            "insufficient_data",
            "Only two synthetic nights; trend classification must be withheld.",
            decreasing_duration,
            decreasing_efficiency,
            missing=(2, 3, 4, 5, 6),
        ),
        _scenario(
            "irregular_timestamps",
            "Start times vary while the constructed elapsed-time reduction stays constant.",
            irregular_duration,
            stable_efficiency,
            hour_offsets=offsets,
        ),
        _scenario(
            "isolated_outlier",
            "One lower duration among constant values is not a progressive reduction.",
            (480.0, 480.0, 480.0, 300.0, 480.0, 480.0, 480.0),
            stable_efficiency,
        ),
        _scenario(
            "partial_window",
            "Partial first and last night buckets are excluded; five full buckets remain.",
            decreasing_duration,
            stable_efficiency,
            partial_edges=True,
        ),
    )


def main() -> None:
    """Print measurements and contract-compatible results as synthetic JSON."""
    config = demonstration_config()
    scenarios = []
    for scenario in demonstration_scenarios():
        evaluation = evaluate_sleep_window(
            scenario.measurements,
            evaluation_id=f"demo-{scenario.name}",
            crew_member_id="synthetic-crew",
            window_start=scenario.window_start,
            window_end=scenario.window_end,
            evaluated_at=scenario.window_end,
            config=config,
        )
        observation = analyze_sleep_observation(
            scenario.measurements[0],
            evaluated_at=scenario.window_end,
            config=config,
        )
        scenarios.append(
            {
                "name": scenario.name,
                "description": scenario.description,
                "measurements": [item.model_dump(mode="json") for item in scenario.measurements],
                "evaluation": evaluation.model_dump(mode="json"),
                "first_observation_without_baseline": observation.model_dump(mode="json"),
            }
        )
    print(dumps({"synthetic": True, "scenarios": scenarios}, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
