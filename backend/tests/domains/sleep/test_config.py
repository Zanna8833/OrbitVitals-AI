"""Configuration validation prevents implicit or meaningless screening policies."""

from dataclasses import FrozenInstanceError, replace
from typing import Any

import pytest

from app.domains.sleep import MetricThresholds, SleepConfig
from app.domains.sleep.demo import demonstration_config
from app.models import MetricType


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_id", ""),
        ("policy_id", "   "),
        ("policy_id", None),
        ("minimum_nights", 2),
        ("minimum_nights", 4.5),
        ("minimum_nights", True),
        ("minimum_coverage", 0),
        ("minimum_coverage", -0.1),
        ("minimum_coverage", 1.01),
        ("minimum_coverage", float("nan")),
        ("minimum_coverage", float("inf")),
        ("minimum_coverage", True),
        ("minimum_coverage", "0.5"),
        ("minimum_decreasing_fraction", 0),
        ("minimum_decreasing_fraction", 1.01),
        ("minimum_span_days", 0),
        ("minimum_span_days", float("inf")),
        ("maximum_consecutive_missing_nights", -1),
        ("maximum_consecutive_missing_nights", 1.5),
        ("maximum_consecutive_missing_nights", False),
        ("night_start_hour_utc", -1),
        ("night_start_hour_utc", 24),
        ("night_start_hour_utc", 12.5),
        ("night_start_hour_utc", True),
        ("duration", None),
        ("efficiency", {"minimum_total_change": 3}),
    ],
)
def test_invalid_policy_is_rejected(field: str, value: Any) -> None:
    with pytest.raises(ValueError, match=field):
        replace(demonstration_config(), **{field: value})


@pytest.mark.parametrize(
    "field",
    ["minimum_slope_per_day", "minimum_total_change", "minimum_observation_deviation"],
)
@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf"), True, "5"])
def test_effect_sizes_must_be_finite_positive_numbers(field: str, value: Any) -> None:
    with pytest.raises(ValueError, match=field):
        replace(demonstration_config().duration, **{field: value})


def test_boundary_values_and_frozen_configuration() -> None:
    config = replace(
        demonstration_config(),
        minimum_nights=3,
        minimum_coverage=1,
        minimum_decreasing_fraction=1,
        maximum_consecutive_missing_nights=0,
        night_start_hour_utc=0,
    )
    assert config.minimum_nights == 3
    assert config.thresholds_for(MetricType.SLEEP_DURATION) == config.duration
    assert config.thresholds_for(MetricType.SLEEP_EFFICIENCY) == config.efficiency
    with pytest.raises(FrozenInstanceError):
        config.minimum_nights = 10  # type: ignore[misc]


def test_thresholds_for_other_metrics_are_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported sleep metric"):
        demonstration_config().thresholds_for(MetricType.HEART_RATE)


def test_no_detection_policy_is_supplied_implicitly() -> None:
    with pytest.raises(TypeError):
        SleepConfig()  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        MetricThresholds()  # type: ignore[call-arg]
