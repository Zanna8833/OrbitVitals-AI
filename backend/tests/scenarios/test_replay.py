"""Actual engine behavior and scientific meaning of the deterministic mission cases."""

from collections import Counter
from datetime import UTC
from unittest.mock import Mock

import pytest

from app.algorithms.data_quality import assess_measurements, assess_window
from app.algorithms.personal_baseline import build_baseline, build_baselines
from app.domains.physical_activity import TargetOutcome, monitor_activity
from app.domains.sleep import analyze_sleep_trends, evaluate_sleep_window
from app.models import (
    BaselineStatus,
    EvaluationStatus,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    QualityFlag,
    QualityStatus,
)
from app.scenarios import fixtures, list_scenarios, replay_scenario
from app.scenarios import replay as replay_module

SCENARIO_IDS = (
    "sensor_quality_failure",
    "personalized_baseline",
    "progressive_sleep_restriction",
    "exercise_adherence_change",
    "insufficient_data",
)


def test_catalog_covers_every_required_scenario() -> None:
    catalog = list_scenarios()
    assert tuple(info.scenario_id for info in catalog) == SCENARIO_IDS
    assert all(info.data_kind == "simulated" for info in catalog)
    assert all(
        info.scientific_purpose and info.assumptions and info.limitations for info in catalog
    )
    assert all("SIMULATED" in info.title for info in catalog)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_every_scenario_executes_and_meets_independent_expectations(scenario_id: str) -> None:
    result = replay_scenario(scenario_id)
    assert result.all_checks_passed
    assert result.scenario.scenario_id == scenario_id
    assert "SIMULATED DATA" in result.notice
    assert result.steps
    for step in result.steps:
        assert step.explanation
        assert step.checks
        assert not step.blockers
        assert len({check.check_id for check in step.checks}) == len(step.checks)
        assert all(check.passed and check.actual == check.expected for check in step.checks)


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_only_labelled_simulated_inputs_are_used_and_no_future_observations_leak(
    scenario_id: str,
) -> None:
    result = replay_scenario(scenario_id)
    assert [step.as_of for step in result.steps] == sorted(step.as_of for step in result.steps)
    for step in result.steps:
        assert step.inputs.data_kind == step.outputs.data_kind == "simulated"
        assert step.as_of.tzinfo == UTC
        records = (*step.inputs.measurements, *step.outputs.assessed_measurements)
        for record in records:
            assert record.source == MeasurementSource.SIMULATED
            assert record.crew_member_id == fixtures.CREW
            assert record.measured_at < step.as_of
            assert record.interval_end is None or record.interval_end <= step.as_of
        for payload in step.inputs.rejected_candidates:
            assert payload["source"] == "simulated"
        for baseline in step.outputs.baselines:
            assert baseline.computed_at == step.as_of
            assert baseline.window_end <= step.as_of
        for evaluation in step.outputs.evaluations:
            assert evaluation.evaluated_at == step.as_of
            assert evaluation.window_end <= step.as_of
            assert evaluation.status != EvaluationStatus.ALERT
            assert all(item.status != EvaluationStatus.ALERT for item in evaluation.findings)


def test_sensor_failures_are_identified_by_the_actual_quality_engine() -> None:
    (step,) = replay_scenario("sensor_quality_failure").steps
    raw = step.inputs.measurements
    policy = fixtures.daily_quality_policy(fixtures.SLEEP_METRICS)
    assert step.outputs.assessed_measurements == tuple(
        assess_measurements(raw, assessed_at=step.as_of, config=policy)
    )
    statuses = Counter(item.data_quality.status for item in step.outputs.assessed_measurements)
    assert statuses == {QualityStatus.ACCEPTABLE: 12, QualityStatus.UNUSABLE: 3}
    flags = Counter(
        flag for item in step.outputs.assessed_measurements for flag in item.data_quality.flags
    )
    assert flags == {QualityFlag.DUPLICATE: 1, QualityFlag.SIGNAL_ARTIFACT: 2}
    assert all(item.data_quality is None for item in raw)
    assert step.outputs.evaluations[0].status == EvaluationStatus.NOMINAL
    assert all(
        item.assessment.status == QualityStatus.DEGRADED for item in step.outputs.quality_windows
    )
    # Timestamp presence and usable-night coverage have different denominators.
    assert all(item.assessment.completeness == 1 for item in step.outputs.quality_windows)
    assert all(item.coverage == pytest.approx(6 / 7) for item in step.outputs.sleep_trends)


def test_sleep_checkpoints_preserve_actual_statistics_missing_nights_and_uncertainty() -> None:
    steps = replay_scenario("progressive_sleep_restriction").steps
    assert [step.outputs.evaluations[0].status for step in steps] == [
        EvaluationStatus.INSUFFICIENT_DATA,
        EvaluationStatus.ATTENTION,
        EvaluationStatus.ATTENTION,
    ]
    early = steps[0].outputs.sleep_trends[0]
    assert early.slope_per_day == -15
    assert early.signal is None
    assert "too_few_nights" in early.insufficient_reasons
    final = steps[-1].outputs.sleep_trends[0]
    assert len(final.observations) == 7
    assert len(final.expected_nights) == 9
    assert final.coverage == pytest.approx(7 / 9)
    assert final.longest_missing_run == 1
    assert final.slope_per_day == -15
    assert final.fitted_change == -120
    assert final.median_value == 430
    assert final.decreasing_fraction == 1
    assert len(final.missing_nights) == 2
    evaluation = steps[-1].outputs.evaluations[0]
    assert evaluation.findings[0].observed_value == final.median_value
    assert evaluation.findings[0].baseline_id is evaluation.findings[0].baseline_value is None
    assert evaluation.data_quality.status == QualityStatus.NOT_ASSESSED
    assert all(
        item.assessment.status == QualityStatus.DEGRADED
        for item in steps[-1].outputs.quality_windows
    )


@pytest.mark.parametrize("scenario_id", ["sensor_quality_failure", "progressive_sleep_restriction"])
def test_reported_sleep_results_equal_direct_calls_of_the_existing_algorithms(
    scenario_id: str,
) -> None:
    for step in replay_scenario(scenario_id).steps:
        arguments = {
            "crew_member_id": fixtures.CREW,
            "window_start": fixtures.SLEEP_START,
            "window_end": step.as_of,
            "config": fixtures.sleep_policy(),
        }
        assert step.outputs.sleep_trends == analyze_sleep_trends(
            step.outputs.assessed_measurements, **arguments
        )
        for window in step.outputs.quality_windows:
            assert window.assessment == assess_window(
                step.inputs.measurements,
                crew_member_id=fixtures.CREW,
                metric=window.metric,
                window_start=window.window_start,
                window_end=window.window_end,
                assessed_at=step.as_of,
                config=fixtures.daily_quality_policy(fixtures.SLEEP_METRICS),
            )
        expected_evaluation = evaluate_sleep_window(
            step.outputs.assessed_measurements,
            **arguments,
            evaluation_id=step.outputs.evaluations[0].evaluation_id,
            evaluated_at=step.as_of,
            mission_phase=MissionPhaseType.IN_FLIGHT,
            metric_data_quality={
                item.metric: item.assessment for item in step.outputs.quality_windows
            },
        )
        assert step.outputs.evaluations == (expected_evaluation,)


def test_baselines_are_real_phase_specific_references_with_quality_and_availability_limits() -> (
    None
):
    steps = replay_scenario("personalized_baseline").steps
    assert steps[0].outputs.baselines[0].status == BaselineStatus.PROVISIONAL
    assert steps[0].outputs.baselines[0].sample_count == 3
    final = {item.mission_phase: item for item in steps[2].outputs.baselines}
    pre = final[MissionPhaseType.PRE_FLIGHT]
    flight = final[MissionPhaseType.IN_FLIGHT]
    launch = final[MissionPhaseType.LAUNCH]
    assert (pre.sample_count, pre.statistics.median) == (14, 58)
    assert (flight.sample_count, flight.statistics.median) == (12, 64)
    assert pre.status == flight.status == BaselineStatus.ESTABLISHED
    assert pre.data_quality.status == QualityStatus.ACCEPTABLE
    assert flight.data_quality.status == QualityStatus.DEGRADED
    assert launch.status == BaselineStatus.INSUFFICIENT_DATA
    assert launch.sample_count == 1
    assert all(value is None for value in launch.statistics.model_dump().values())
    assert all(query.baseline is None for step in steps for query in step.outputs.baseline_queries)
    without_policy = {item.mission_phase: item for item in steps[3].outputs.baselines}
    assert without_policy[MissionPhaseType.IN_FLIGHT].status == BaselineStatus.PROVISIONAL
    assert without_policy[MissionPhaseType.PRE_FLIGHT].statistics == pre.statistics
    assert without_policy[MissionPhaseType.IN_FLIGHT].statistics == flight.statistics
    for step in steps:
        configured = (
            step.inputs.parameters["baseline_config"]["established_min_samples"] is not None
        )
        config = fixtures.baseline_policy(establishment_configured=configured)
        expected = build_baselines(
            step.inputs.measurements,
            step.inputs.mission_phases,
            computed_at=step.as_of,
            config=config,
            crew_member_ids=(fixtures.CREW,),
            metrics=(MetricType.HEART_RATE,),
        )
        assert step.outputs.baselines == tuple(expected)
        for query in step.outputs.baseline_queries:
            assert query.baseline == build_baseline(
                step.inputs.measurements,
                step.inputs.mission_phases,
                crew_member_id=fixtures.CREW,
                metric=query.metric,
                mission_phase=query.mission_phase,
                computed_at=step.as_of,
                config=config,
            )


def test_activity_runs_and_targets_use_recording_aware_actual_reports() -> None:
    steps = replay_scenario("exercise_adherence_change").steps
    for step in steps:
        assert step.outputs.activity_report == monitor_activity(step.inputs.activity_request)
        assert step.outputs.evaluations == (step.outputs.activity_report.evaluation,)
        assert step.inputs.activity_request.evaluated_at == step.as_of
        assert step.inputs.activity_request.baselines == ()
    final = steps[-1].outputs.activity_report
    duration_runs = [
        trend.values for trend in final.trends if trend.metric == MetricType.EXERCISE_DURATION
    ]
    assert duration_runs == [[60, 55, 50, 45, 40], [35, 30, 25, 20]]
    assert len(final.trends) == 4
    for day_index in (5, 12):
        assert final.days[day_index].planned_rest
        assert all(
            item.target_outcome == TargetOutcome.NOT_APPLICABLE
            for item in final.days[day_index].metrics
        )
        assert all(item.observed_total == 0 for item in final.days[day_index].metrics)
    partial = final.days[10]
    assert [item.observed_total for item in partial.metrics] == [15, None]
    assert all(not item.recording_complete for item in partial.metrics)
    assert all(item.target_outcome == TargetOutcome.UNKNOWN for item in partial.metrics)
    assert [item.observed_total for item in final.days[11].metrics] == [None, None]
    assert all(item.target_outcome == TargetOutcome.MET for item in final.weeks[0].metrics)
    assert all(item.target_outcome == TargetOutcome.UNKNOWN for item in final.weeks[1].metrics)
    assert all(item.target_outcome == TargetOutcome.MISSED for item in final.days[13].metrics)
    assert all(item.baseline_id is None for item in final.evaluation.findings)


def test_insufficient_cases_never_fabricate_values_references_or_an_alert() -> None:
    result = replay_scenario("insufficient_data")
    steps = {step.step_id: step for step in result.steps}
    for step in result.steps:
        assert all(
            item.status == EvaluationStatus.INSUFFICIENT_DATA for item in step.outputs.evaluations
        )
    missing = steps["insufficient-missing-observations"]
    assert not missing.inputs.measurements
    assert len(missing.outputs.rejected_inputs) == 1
    assert missing.outputs.rejected_inputs[0].payload["unit"] == "hours"
    assert "canonical unit" in missing.outputs.rejected_inputs[0].validation_errors[0]
    unusable = steps["insufficient-unusable-observations"]
    assert len(unusable.outputs.assessed_measurements) == 10
    assert all(
        item.data_quality.status == QualityStatus.UNUSABLE
        for item in unusable.outputs.assessed_measurements
    )
    assert all(item.observed_value is None for item in unusable.outputs.evaluations[0].findings)
    assert all(item.signal is None for item in unusable.outputs.sleep_trends)
    reference = steps["insufficient-baseline-information"].outputs.baselines[0]
    assert reference.sample_count == 1
    assert reference.status == BaselineStatus.INSUFFICIENT_DATA
    assert all(value is None for value in reference.statistics.model_dump().values())
    activity = steps["insufficient-unconfirmed-activity"].outputs.activity_report
    assert activity.days[0].metrics[0].observed_total == 30
    assert activity.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert activity.evaluation.findings[0].observed_value is None


def test_engine_entry_points_are_called_and_catalog_listing_does_not_run_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = (
        "assess_measurements",
        "assess_window",
        "build_baseline",
        "build_baselines",
        "analyze_sleep_trends",
        "evaluate_sleep_window",
        "analyze_sleep_observation",
        "monitor_activity",
    )
    spies = {}
    for name in names:
        spy = Mock(wraps=getattr(replay_module, name))
        monkeypatch.setattr(replay_module, name, spy)
        spies[name] = spy
    list_scenarios()
    assert all(spy.call_count == 0 for spy in spies.values())
    for scenario_id in SCENARIO_IDS:
        replay_scenario(scenario_id)
    assert all(spy.call_count > 0 for spy in spies.values())


def test_changed_inputs_produce_real_changed_outputs_and_failed_expectations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        fixtures,
        "restriction_records",
        lambda: fixtures.sleep_records(
            "flat-counterexample",
            (490,) * 9,
            (92,) * 9,
            missing_nights=frozenset({2, 6}),
        ),
    )
    result = replay_scenario("progressive_sleep_restriction")
    assert not result.all_checks_passed
    final = result.steps[-1]
    assert final.outputs.sleep_trends[0].slope_per_day == 0
    assert final.outputs.sleep_trends[0].signal is None
    assert final.outputs.evaluations[0].status == EvaluationStatus.NOMINAL
    slope_check = next(check for check in final.checks if check.check_id == "actual_slope")
    assert slope_check.expected == -15
    assert slope_check.actual == 0
    assert not slope_check.passed


def test_unknown_scenario_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="Unknown scenario"):
        replay_scenario("unknown-scenario")
