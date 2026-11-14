"""Fail explicitly on contradictory domain input instead of silently changing semantics."""

from datetime import timedelta

import pytest
from pydantic import ValidationError

from app.domains.physical_activity import (
    ActivityDayPlan,
    ActivityMetricPolicy,
    DailyBaselineReference,
    ExerciseSession,
    RecordingCoverage,
)
from app.models import MetricType
from tests.domains.physical_activity.support import (
    DURATION,
    START,
    baseline_reference,
    measurement,
    request,
)


@pytest.mark.parametrize(
    "overrides",
    [
        {"window_start": START, "window_end": START},
        {"window_end": START - timedelta(days=1)},
        {"evaluated_at": START},
        {"window_start": START.replace(tzinfo=None)},
        {"reduction_run_length": 2},
        {"unexpected": True},
    ],
)
def test_invalid_evaluation_context(overrides: dict) -> None:
    with pytest.raises(ValidationError):
        request(**overrides)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
@pytest.mark.parametrize(
    "field",
    ["daily_target", "weekly_target", "baseline_absolute_tolerance", "baseline_relative_tolerance"],
)
def test_policy_requires_nonnegative_finite_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        ActivityMetricPolicy(metric=DURATION, **{field: value})


def test_other_crew_members_and_domains_are_rejected() -> None:
    with pytest.raises(ValidationError, match="crew_member_id"):
        request(measurements=[measurement(crew_member_id="someone-else")])
    with pytest.raises(ValidationError, match="physical-activity"):
        request(measurements=[measurement(metric=MetricType.HEART_RATE)])


def test_conflicting_duplicate_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Conflicting measurement_id"):
        request(measurements=[measurement(20), measurement(30)])


@pytest.mark.parametrize("field", ["coverage", "day_plans", "policies", "baselines", "sessions"])
def test_duplicate_configuration_is_rejected(field: str) -> None:
    item = {
        "coverage": RecordingCoverage(day=START.date(), metric=DURATION, complete=True),
        "day_plans": ActivityDayPlan(day=START.date()),
        "policies": ActivityMetricPolicy(metric=DURATION),
        "baselines": baseline_reference(),
        "sessions": ExerciseSession(session_id="sim-s1", start_time=START),
    }[field]
    with pytest.raises(ValidationError, match="Duplicate"):
        request(**{field: [item, item]})


def test_baseline_aggregation_semantics_must_be_explicit() -> None:
    payload = baseline_reference().model_dump()
    payload.pop("comparison_basis")
    with pytest.raises(ValidationError):
        DailyBaselineReference.model_validate(payload)
    payload["comparison_basis"] = "session_total"
    with pytest.raises(ValidationError):
        DailyBaselineReference.model_validate(payload)


@pytest.mark.parametrize("offset", [0, -1])
def test_closed_session_must_have_positive_elapsed_time(offset: int) -> None:
    with pytest.raises(ValidationError, match="end after"):
        ExerciseSession(
            session_id="sim-session", start_time=START, end_time=START + timedelta(hours=offset)
        )


def test_session_links_must_be_known_unique_and_contained() -> None:
    def session(identifier: str, links: tuple[str, ...], **kwargs) -> ExerciseSession:
        return ExerciseSession(
            session_id=identifier,
            start_time=START + timedelta(hours=8),
            end_time=START + timedelta(hours=10),
            measurement_ids=links,
            **kwargs,
        )

    with pytest.raises(ValidationError, match="Unknown"):
        request(sessions=[session("sim-s1", ("missing",))])
    with pytest.raises(ValidationError, match="unique"):
        session("sim-s1", ("sim-m1", "sim-m1"))
    with pytest.raises(ValidationError, match="multiple sessions"):
        request(
            measurements=[measurement()],
            sessions=[session("sim-s1", ("sim-m1",)), session("sim-s2", ("sim-m1",))],
        )
    with pytest.raises(ValidationError, match="contained"):
        request(
            measurements=[measurement(measured_at=START + timedelta(hours=11))],
            sessions=[session("sim-s1", ("sim-m1",))],
        )


def test_overlapping_closed_session_metadata_is_rejected() -> None:
    sessions = [
        ExerciseSession(
            session_id=f"sim-{hour}",
            start_time=START + timedelta(hours=hour),
            end_time=START + timedelta(hours=hour + 2),
        )
        for hour in (8, 9)
    ]
    with pytest.raises(ValidationError, match="must not overlap"):
        request(sessions=sessions)
