"""Explicit, non-clinical policy inputs for sleep screening."""

from dataclasses import dataclass
from math import isfinite

from app.models import MetricType


def _positive(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite positive number")
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")


@dataclass(frozen=True, kw_only=True)
class MetricThresholds:
    """Caller-selected effect sizes, in minutes or percentage points.

    Source of these policy parameters: README.md, "Configuration policy" in this
    package. There are deliberately no default or clinically justified cutoffs.
    """

    minimum_slope_per_day: float
    minimum_total_change: float
    minimum_observation_deviation: float

    def __post_init__(self) -> None:
        for name in (
            "minimum_slope_per_day",
            "minimum_total_change",
            "minimum_observation_deviation",
        ):
            _positive(name, getattr(self, name))


@dataclass(frozen=True, kw_only=True)
class SleepConfig:
    """A versioned screening policy supplied by the caller, never a health norm.

    Source of the gates and their interpretation: README.md, "Configuration policy"
    and "Windows and nights" in this package. The minimum of three nights is a
    structural requirement for observing more than one transition, not evidence
    of statistical power. A night boundary is an operational UTC convention.
    """

    policy_id: str
    duration: MetricThresholds
    efficiency: MetricThresholds
    minimum_nights: int
    minimum_coverage: float
    minimum_span_days: float
    maximum_consecutive_missing_nights: int
    minimum_decreasing_fraction: float
    night_start_hour_utc: int

    def __post_init__(self) -> None:
        if not isinstance(self.policy_id, str) or not self.policy_id.strip():
            raise ValueError("policy_id must be a non-empty policy identifier")
        if not isinstance(self.duration, MetricThresholds) or not isinstance(
            self.efficiency, MetricThresholds
        ):
            raise ValueError("duration and efficiency must be MetricThresholds")
        if type(self.minimum_nights) is not int or self.minimum_nights < 3:
            raise ValueError("minimum_nights must be an integer of at least three")
        if (
            type(self.maximum_consecutive_missing_nights) is not int
            or self.maximum_consecutive_missing_nights < 0
        ):
            raise ValueError("maximum_consecutive_missing_nights must be a non-negative integer")
        if type(self.night_start_hour_utc) is not int or not 0 <= self.night_start_hour_utc < 24:
            raise ValueError("night_start_hour_utc must be an integer from 0 through 23")
        _positive("minimum_span_days", self.minimum_span_days)
        for name in ("minimum_coverage", "minimum_decreasing_fraction"):
            value = getattr(self, name)
            _positive(name, value)
            if value > 1:
                raise ValueError(f"{name} must be at most one")

    def thresholds_for(self, metric: MetricType) -> MetricThresholds:
        """Return the policy for a supported sleep metric."""
        if metric == MetricType.SLEEP_DURATION:
            return self.duration
        if metric == MetricType.SLEEP_EFFICIENCY:
            return self.efficiency
        raise ValueError(f"Unsupported sleep metric: {metric}")
