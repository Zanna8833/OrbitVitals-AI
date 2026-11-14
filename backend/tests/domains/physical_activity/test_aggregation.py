"""Session evidence, UTC boundaries, incomplete records and arithmetic edge cases."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.domains.physical_activity import (
    ExerciseSession,
    RecordingCoverage,
    TargetOutcome,
    monitor_activity,
)
from app.models import EvaluationStatus, QualityFlag
from tests.domains.physical_activity.support import (
    DURATION,
    ENERGY,
    START,
    measurement,
    replace_request,
    request,
    series,
)


def test_daily_additive_values_and_session_links_are_not_counted_twice() -> None:
    records = [
        measurement(20, DURATION, "sim-d1", measured_at=START + timedelta(hours=8)),
        measurement(150, ENERGY, "sim-e1", measured_at=START + timedelta(hours=8)),
        measurement(25, DURATION, "sim-d2", measured_at=START + timedelta(hours=10)),
        measurement(170, ENERGY, "sim-e2", measured_at=START + timedelta(hours=10)),
    ]
    sessions = [
        ExerciseSession(
            session_id=f"sim-session-{index}",
            start_time=START + timedelta(hours=hour),
            end_time=START + timedelta(hours=hour + 1),
            measurement_ids=(f"sim-d{index}", f"sim-e{index}"),
        )
        for index, hour in [(1, 8), (2, 10)]
    ]
    original = series([45])
    result = monitor_activity(replace_request(original, measurements=records, sessions=sessions))
    assert result.days[0].metrics[0].observed_total == 45
    assert result.days[0].metrics[1].observed_total == 320
    assert [item.exercise_duration for item in result.sessions] == [20, 25]
    assert [item.active_energy_expenditure for item in result.sessions] == [150, 170]
    assert all(item.recording_complete for item in result.sessions)
    assert result.evaluation.status == EvaluationStatus.NOMINAL


def test_missing_data_never_becomes_zero_or_a_missed_target() -> None:
    result = monitor_activity(request())
    assert result.evaluation.status == EvaluationStatus.INSUFFICIENT_DATA
    assert all(item.observed_value is None for item in result.evaluation.findings)
    assert all(item.observed_total is None for item in result.days[0].metrics)
    assert all(item.target_outcome == TargetOutcome.UNKNOWN for item in result.days[0].metrics)
    assert result.evaluation.data_quality.completeness == 0
    assert QualityFlag.MISSING_DATA in result.evaluation.data_quality.flags


def test_complete_empty_recording_explicitly_confirms_zero() -> None:
    coverage = [
        RecordingCoverage(day=START.date(), metric=metric, complete=True)
        for metric in (DURATION, ENERGY)
    ]
    result = monitor_activity(request(coverage=coverage))
    assert [item.observed_total for item in result.days[0].metrics] == [0, 0]
    assert all(item.target_outcome == TargetOutcome.MISSED for item in result.days[0].metrics)
    assert result.evaluation.status == EvaluationStatus.ATTENTION


def test_observed_subtotal_without_coverage_cannot_be_compared() -> None:
    result = monitor_activity(request(measurements=[measurement(5)]))
    assert result.days[0].metrics[0].observed_total == 5
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert result.evaluation.findings[0].observed_value is None


def test_missing_one_metric_does_not_discard_the_other() -> None:
    result = monitor_activity(series([30], [None]))
    assert result.evaluation.findings[0].status == EvaluationStatus.NOMINAL
    assert result.evaluation.findings[1].status == EvaluationStatus.INSUFFICIENT_DATA
    assert result.evaluation.status == EvaluationStatus.INSUFFICIENT_DATA
    assert result.evaluation.data_quality.completeness == 0.5


def test_identical_duplicate_ids_are_collapsed_deterministically() -> None:
    original = series([30])
    result = monitor_activity(
        replace_request(original, measurements=[*original.measurements, original.measurements[0]])
    )
    assert result.days[0].metrics[0].observed_total == 30
    assert result.evaluation.findings[0].status == EvaluationStatus.NOMINAL
    assert QualityFlag.DUPLICATE in result.evaluation.data_quality.flags
    assert any("Collapsed identical" in notice for notice in result.notices)


@pytest.mark.parametrize("use_intervals", [False, True])
def test_ambiguous_duplicate_candidates_are_excluded(use_intervals: bool) -> None:
    extras = {"interval_end": START + timedelta(hours=10)} if use_intervals else {}
    records = [measurement(20, measurement_id=f"sim-{index}", **extras) for index in (1, 2)]
    result = monitor_activity(replace_request(series([30]), measurements=records))
    item = result.days[0].metrics[0]
    assert item.observed_total is None
    assert item.target_outcome == TargetOutcome.UNKNOWN
    assert QualityFlag.DUPLICATE in item.data_quality.flags


def test_touching_half_open_intervals_do_not_overlap() -> None:
    records = [
        measurement(
            30,
            measurement_id=f"sim-{hour}",
            measured_at=START + timedelta(hours=hour),
            interval_end=START + timedelta(hours=hour + 1),
        )
        for hour in (8, 9)
    ]
    result = monitor_activity(replace_request(series([30]), measurements=records))
    assert result.days[0].metrics[0].observed_total == 60
    assert result.days[0].metrics[0].comparison_eligible


def test_measurements_are_bounded_by_a_half_open_window() -> None:
    original = series([30])
    records = [
        measurement(4, measurement_id="sim-start", measured_at=START),
        measurement(-1, measurement_id="sim-before", measured_at=START - timedelta(seconds=1)),
        measurement(80, measurement_id="sim-end", measured_at=START + timedelta(days=1)),
    ]
    result = monitor_activity(replace_request(original, measurements=records))
    assert result.days[0].metrics[0].observed_total == 4
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.MISSED
    assert sum("out-of-window" in notice for notice in result.notices) == 2


def test_offset_timestamps_are_allocated_by_utc_date() -> None:
    instant = datetime(2026, 11, 3, 0, 30, tzinfo=timezone(timedelta(hours=2)))
    result = monitor_activity(request(measurements=[measurement(30, measured_at=instant)]))
    assert len(result.days) == 1
    assert result.days[0].day == START.date()
    assert result.days[0].metrics[0].observed_total == 30
    assert result.evaluation.window_start.tzinfo == UTC


def test_interval_ending_at_midnight_belongs_to_the_preceding_day() -> None:
    record = measurement(
        30, measured_at=START + timedelta(hours=23), interval_end=START + timedelta(days=1)
    )
    result = monitor_activity(replace_request(series([30, None]), measurements=[record]))
    assert result.days[0].metrics[0].observed_total == 30
    assert result.days[1].metrics[0].observed_total is None


def test_cross_midnight_session_is_retained_without_inventing_daily_distribution() -> None:
    start, end = START + timedelta(hours=23), START + timedelta(days=1, hours=1)
    records = [
        measurement(40, DURATION, "sim-duration", measured_at=start, interval_end=end),
        measurement(200, ENERGY, "sim-energy", measured_at=start, interval_end=end),
    ]
    session = ExerciseSession(
        session_id="sim-night",
        start_time=start,
        end_time=end,
        measurement_ids=("sim-duration", "sim-energy"),
    )
    result = monitor_activity(
        replace_request(series([40, 40]), measurements=records, sessions=[session])
    )
    assert result.sessions[0].exercise_duration == 40
    assert result.sessions[0].active_energy_expenditure == 200
    assert all(day.metrics[0].observed_total is None for day in result.days)
    assert all(day.metrics[0].target_outcome == TargetOutcome.UNKNOWN for day in result.days)
    assert any("UTC midnight" in notice for notice in result.notices)


@pytest.mark.parametrize("left_boundary", [False, True])
def test_intervals_crossing_the_evaluation_boundary_are_not_prorated(left_boundary: bool) -> None:
    start = START - timedelta(hours=1) if left_boundary else START + timedelta(hours=23)
    record = measurement(60, measured_at=start, interval_end=start + timedelta(hours=2))
    result = monitor_activity(replace_request(series([30]), measurements=[record]))
    assert result.days[0].metrics[0].observed_total is None
    assert not result.days[0].metrics[0].recording_complete
    assert any("evaluation boundary" in notice for notice in result.notices)


def test_partial_utc_day_does_not_compare_full_day_targets() -> None:
    original = series([30])
    result = monitor_activity(replace_request(original, window_end=START + timedelta(hours=12)))
    assert result.days[0].metrics[0].observed_total == 30
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert result.evaluation.status == EvaluationStatus.INSUFFICIENT_DATA


def test_open_or_incomplete_session_does_not_infer_elapsed_duration_or_calories() -> None:
    original = series([30])
    session = ExerciseSession(
        session_id="sim-open",
        start_time=START + timedelta(hours=8),
        measurement_ids=(original.measurements[0].measurement_id,),
    )
    result = monitor_activity(replace_request(original, sessions=[session]))
    assert result.sessions[0].exercise_duration == 30
    assert result.sessions[0].active_energy_expenditure is None
    assert not result.sessions[0].recording_complete
    assert all(not item.comparison_eligible for item in result.days[0].metrics)


def test_missing_session_metric_prevents_a_false_confirmed_zero() -> None:
    record = measurement(30)
    session = ExerciseSession(
        session_id="sim-partial",
        start_time=START + timedelta(hours=8),
        end_time=START + timedelta(hours=10),
        measurement_ids=(record.measurement_id,),
    )
    result = monitor_activity(
        replace_request(series([30]), measurements=[record], sessions=[session])
    )
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.MET
    assert result.days[0].metrics[1].observed_total is None
    assert result.days[0].metrics[1].target_outcome == TargetOutcome.UNKNOWN


def test_negative_values_are_excluded_without_a_false_target_miss() -> None:
    result = monitor_activity(replace_request(series([30]), measurements=[measurement(-2)]))
    assert result.days[0].metrics[0].observed_total is None
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert any("negative activity" in notice for notice in result.notices)


def test_nonrepresentable_daily_sum_is_unknown_and_json_stays_finite() -> None:
    records = [
        measurement(1e308, measurement_id=f"sim-{hour}", measured_at=START + timedelta(hours=hour))
        for hour in (8, 9)
    ]
    result = monitor_activity(replace_request(series([30]), measurements=records))
    assert result.days[0].metrics[0].observed_total is None
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    json.dumps(result.model_dump(mode="json"), allow_nan=False)


def test_representable_mean_survives_overflow_of_intermediate_sum() -> None:
    result = monitor_activity(series([1e308, 1e308, 1e308]))
    assert result.evaluation.findings[0].observed_value == pytest.approx(1e308)


def test_subnormal_mean_is_preserved() -> None:
    result = monitor_activity(series([5e-324, 5e-324, 5e-324]))
    assert result.evaluation.findings[0].observed_value == 5e-324


def test_order_does_not_change_results_and_inputs_are_not_modified() -> None:
    original = series([30, 25, 20])
    before = original.model_dump(mode="json")
    forward = monitor_activity(original)
    reverse = monitor_activity(replace_request(original, measurements=original.measurements[::-1]))
    assert forward == reverse
    assert original.model_dump(mode="json") == before


@pytest.mark.parametrize("point_interval", [False, True])
def test_linked_session_boundaries_apply_to_instantaneous_records(point_interval: bool) -> None:
    start, end = START + timedelta(hours=23), START + timedelta(days=1, hours=1)
    records = [
        measurement(
            value,
            metric,
            f"sim-{metric}",
            measured_at=start,
            interval_end=start if point_interval else None,
        )
        for metric, value in [(DURATION, 40), (ENERGY, 200)]
    ]
    session = ExerciseSession(
        session_id="sim-midnight-point",
        start_time=start,
        end_time=end,
        measurement_ids=tuple(item.measurement_id for item in records),
    )
    result = monitor_activity(
        replace_request(series([40, 40]), measurements=records, sessions=[session])
    )
    assert result.sessions[0].exercise_duration == 40
    assert all(day.metrics[0].observed_total is None for day in result.days)
    assert all(day.metrics[0].target_outcome == TargetOutcome.UNKNOWN for day in result.days)


def test_cross_midnight_session_accepts_explicit_per_date_contributions() -> None:
    start, boundary, end = (
        START + timedelta(hours=23),
        START + timedelta(days=1),
        START + timedelta(days=1, hours=1),
    )
    records = [
        measurement(value, metric, f"sim-{offset}-{metric}", measured_at=left, interval_end=right)
        for offset, (left, right) in enumerate([(start, boundary), (boundary, end)])
        for metric, value in [(DURATION, 20), (ENERGY, 100)]
    ]
    session = ExerciseSession(
        session_id="sim-split-session",
        start_time=start,
        end_time=end,
        measurement_ids=tuple(item.measurement_id for item in records),
    )
    result = monitor_activity(
        replace_request(series([20, 20]), measurements=records, sessions=[session])
    )
    assert [day.metrics[0].observed_total for day in result.days] == [20, 20]
    assert result.sessions[0].exercise_duration == 40
    assert result.sessions[0].recording_complete


def test_partial_linked_session_is_not_complete_even_when_point_is_in_window() -> None:
    instant = START + timedelta(hours=23)
    records = [measurement(30, measured_at=instant)]
    session = ExerciseSession(
        session_id="sim-window-point",
        start_time=instant,
        end_time=START + timedelta(days=1, hours=1),
        measurement_ids=(records[0].measurement_id,),
    )
    result = monitor_activity(
        replace_request(series([30]), measurements=records, sessions=[session])
    )
    assert result.days[0].metrics[0].observed_total is None
    assert not result.sessions[0].recording_complete


def test_open_session_starting_before_window_blocks_unknown_activity() -> None:
    session = ExerciseSession(session_id="sim-old-open", start_time=START - timedelta(hours=1))
    result = monitor_activity(replace_request(series([30, 30]), sessions=[session]))
    assert all(not day.metrics[0].comparison_eligible for day in result.days)
    assert all(day.metrics[0].target_outcome == TargetOutcome.UNKNOWN for day in result.days)


def test_iso_weeks_cross_year_boundaries_without_merging() -> None:
    start = datetime(2026, 12, 28, tzinfo=UTC)
    original = series([30] * 14)
    shift = start - START
    records = [
        item.model_copy(update={"measured_at": item.measured_at + shift})
        for item in original.measurements
    ]
    coverage = [item.model_copy(update={"day": item.day + shift}) for item in original.coverage]
    result = monitor_activity(
        replace_request(
            original,
            window_start=start,
            window_end=start + timedelta(days=14),
            evaluated_at=start + timedelta(days=14),
            measurements=records,
            coverage=coverage,
        )
    )
    assert [week.week_start for week in result.weeks] == [
        start.date(),
        (start + timedelta(days=7)).date(),
    ]
    assert [week.metrics[0].observed_total for week in result.weeks] == [210, 210]


def test_confirmed_signal_is_retained_when_other_dates_are_missing() -> None:
    result = monitor_activity(series([10, None]))
    assert result.evaluation.findings[0].status == EvaluationStatus.ATTENTION
    assert result.days[1].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert "remain unknown" in result.evaluation.findings[0].explanation
