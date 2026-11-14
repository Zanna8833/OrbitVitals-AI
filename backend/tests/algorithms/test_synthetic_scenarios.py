"""The synthetic demonstration scenarios run end to end and stay labelled as synthetic."""

import json

import pytest
from jsonschema import Draft202012Validator

from app.algorithms.personal_baseline import OutlierHandling
from app.models import (
    BaselineStatus,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    QualityFlag,
    QualityStatus,
)
from scripts.demo_quality_baseline import (
    SYNTHETIC_NOTICE,
    Scenario,
    assessed_measurements_of,
    baselines_of,
    build_results,
    edge_case_scenario,
    main,
    outlier_scenario,
    phase_aware_scenario,
    quality_issue_scenario,
    saturation_window_quality,
)
from tests.support import load_schema

SCENARIOS = [
    phase_aware_scenario(),
    quality_issue_scenario(),
    outlier_scenario(),
    edge_case_scenario(),
]

ACCEPTABLE = QualityStatus.ACCEPTABLE
DEGRADED = QualityStatus.DEGRADED
UNUSABLE = QualityStatus.UNUSABLE


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.title)
def test_every_scenario_measurement_is_labelled_simulated(scenario: Scenario) -> None:
    assert scenario.measurements
    assert all(item.source is MeasurementSource.SIMULATED for item in scenario.measurements)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.title)
def test_every_scenario_baseline_says_that_its_data_are_simulated(scenario: Scenario) -> None:
    for baseline in baselines_of(scenario):
        if baseline.data_quality.notes.startswith("No record"):
            continue
        assert "Simulated (synthetic) records" in baseline.data_quality.notes


def test_phase_aware_scenario_gives_one_baseline_per_phase() -> None:
    baselines = {
        baseline.mission_phase: baseline for baseline in baselines_of(phase_aware_scenario())
    }

    assert {phase: baseline.status for phase, baseline in baselines.items()} == {
        MissionPhaseType.PRE_FLIGHT: BaselineStatus.ESTABLISHED,
        MissionPhaseType.LAUNCH: BaselineStatus.INSUFFICIENT_DATA,
        MissionPhaseType.IN_FLIGHT: BaselineStatus.ESTABLISHED,
    }
    pre_flight = baselines[MissionPhaseType.PRE_FLIGHT]
    in_flight = baselines[MissionPhaseType.IN_FLIGHT]
    assert (pre_flight.sample_count, pre_flight.statistics.median) == (30, 58.0)
    assert (in_flight.sample_count, in_flight.statistics.median) == (30, 62.0)
    assert pre_flight.data_quality.status is ACCEPTABLE
    assert pre_flight.data_quality.completeness == 1.0
    assert baselines[MissionPhaseType.LAUNCH].statistics.mean is None


def test_quality_issue_scenario_reports_every_kind_of_issue() -> None:
    scenario = quality_issue_scenario()

    found = {
        item.measurement_id: (item.data_quality.status, item.data_quality.flags)
        for item in assessed_measurements_of(scenario)
    }

    assert found == {
        "sim-spo2-00": (ACCEPTABLE, []),
        "sim-spo2-01": (ACCEPTABLE, []),
        "sim-spo2-02": (ACCEPTABLE, []),
        "sim-spo2-02-copy": (UNUSABLE, [QualityFlag.DUPLICATE]),
        "sim-spo2-05-a": (UNUSABLE, [QualityFlag.DUPLICATE]),
        "sim-spo2-05-b": (UNUSABLE, [QualityFlag.DUPLICATE]),
        "sim-spo2-06": (
            UNUSABLE,
            [QualityFlag.OUT_OF_SENSOR_RANGE, QualityFlag.SIGNAL_ARTIFACT],
        ),
        "sim-spo2-07": (DEGRADED, [QualityFlag.OUT_OF_SENSOR_RANGE]),
        "sim-spo2-08": (ACCEPTABLE, []),
        "sim-spo2-09": (ACCEPTABLE, []),
        "sim-spo2-10": (ACCEPTABLE, []),
        "sim-spo2-11": (ACCEPTABLE, []),
        "sim-bp-systolic": (UNUSABLE, [QualityFlag.SIGNAL_ARTIFACT]),
        "sim-bp-diastolic": (UNUSABLE, [QualityFlag.SIGNAL_ARTIFACT]),
        "sim-exercise": (UNUSABLE, [QualityFlag.SIGNAL_ARTIFACT]),
        "sim-hr-future": (UNUSABLE, []),
    }


def test_quality_issue_scenario_summarizes_its_window() -> None:
    quality = saturation_window_quality(quality_issue_scenario())

    assert quality.status is DEGRADED
    assert quality.completeness == pytest.approx(10 / 12)
    assert quality.score == pytest.approx(7 / 12)
    assert quality.flags == [
        QualityFlag.MISSING_DATA,
        QualityFlag.OUT_OF_SENSOR_RANGE,
        QualityFlag.SIGNAL_ARTIFACT,
        QualityFlag.DUPLICATE,
    ]
    assert "12 records in the window: 7 acceptable, 1 degraded, 4 unusable" in quality.notes
    assert "Longest interval without an observation: 3 hours" in quality.notes


def test_quality_issue_scenario_keeps_issues_out_of_the_baseline() -> None:
    baselines = {
        (baseline.metric, baseline.mission_phase): baseline
        for baseline in baselines_of(quality_issue_scenario())
    }

    saturation = baselines[(MetricType.BLOOD_OXYGEN_SATURATION, MissionPhaseType.IN_FLIGHT)]
    assert saturation.sample_count == 7
    assert (saturation.statistics.minimum, saturation.statistics.maximum) == (97.0, 98.0)
    for metric in (MetricType.SYSTOLIC_BLOOD_PRESSURE, MetricType.EXERCISE_DURATION):
        assert baselines[(metric, MissionPhaseType.IN_FLIGHT)].sample_count == 0


def test_outlier_scenario_shows_both_settings() -> None:
    scenario = outlier_scenario()

    (reported,) = baselines_of(scenario, OutlierHandling.REPORT)
    (excluded,) = baselines_of(scenario, OutlierHandling.EXCLUDE)

    assert baselines_of(scenario) == [reported]  # reporting is the default
    assert (reported.sample_count, reported.statistics.maximum) == (30, 96.0)
    assert (excluded.sample_count, excluded.statistics.maximum) == (29, 60.0)
    # The robust statistics are the same with and without the extreme value.
    assert reported.statistics.median == excluded.statistics.median == 58.0
    assert reported.statistics.median_absolute_deviation == 1.0
    assert excluded.statistics.median_absolute_deviation == 1.0
    assert reported.statistics.standard_deviation > 4 * excluded.statistics.standard_deviation
    assert reported.data_quality.status is ACCEPTABLE


def test_edge_case_scenario_handles_each_case_safely() -> None:
    baselines = {baseline.metric: baseline for baseline in baselines_of(edge_case_scenario())}

    single_value = baselines[MetricType.RESPIRATORY_RATE]
    never_observed = baselines[MetricType.BODY_TEMPERATURE]
    constant = baselines[MetricType.BODY_MASS]

    assert (single_value.status, single_value.sample_count) == (
        BaselineStatus.INSUFFICIENT_DATA,
        1,
    )
    assert (never_observed.status, never_observed.sample_count) == (
        BaselineStatus.INSUFFICIENT_DATA,
        0,
    )
    assert single_value.statistics.mean is None
    assert never_observed.statistics.mean is None
    assert (constant.status, constant.sample_count) == (BaselineStatus.PROVISIONAL, 30)
    assert constant.statistics.standard_deviation == 0.0
    assert constant.statistics.median_absolute_deviation == 0.0


def test_results_are_valid_contract_json_and_reproducible() -> None:
    results = build_results()
    baseline_validator = Draft202012Validator(load_schema("personal_baseline"))
    measurement_validator = Draft202012Validator(load_schema("physiological_measurement"))
    quality_validator = Draft202012Validator(load_schema("data_quality"))

    baselines = [
        baseline
        for scenario in results.values()
        for key, items in scenario.items()
        if key.startswith("baselines")
        for baseline in items
    ]
    assert len(baselines) == 3 + 2 + 3
    for baseline in baselines:
        baseline_validator.validate(baseline)
    for item in results["data_quality_issues"]["measurements"]:
        measurement_validator.validate(item)
    quality_validator.validate(results["data_quality_issues"]["blood_oxygen_saturation_window"])

    assert build_results() == results


def test_the_summary_is_labelled_synthetic(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0

    output = capsys.readouterr().out
    assert output.count(SYNTHETIC_NOTICE) == 2
    assert output.count("(synthetic)\n") == len(SCENARIOS)


def test_the_json_output_is_labelled_synthetic(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--json"]) == 0

    document = json.loads(capsys.readouterr().out)
    assert document["notice"] == SYNTHETIC_NOTICE
    assert document["scenarios"] == build_results()
