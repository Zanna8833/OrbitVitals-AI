"""Demonstrations are deterministic, fully labelled and compatible with shared contracts."""

from json import loads

import pytest
from jsonschema import Draft202012Validator

from app.domains.sleep.demo import demonstration_scenarios, main
from app.models import (
    EvaluationResult,
    EvaluationStatus,
    MeasurementSource,
    PhysiologicalMeasurement,
)
from tests.domains.sleep.helpers import evaluate
from tests.support import load_schema


@pytest.mark.parametrize(
    ("name", "status"),
    [
        ("stable", EvaluationStatus.NOMINAL),
        ("duration_reduction", EvaluationStatus.ATTENTION),
        ("efficiency_decrease", EvaluationStatus.ATTENTION),
        ("efficiency_increase", EvaluationStatus.ATTENTION),
        ("missing_nights", EvaluationStatus.ATTENTION),
        ("insufficient_data", EvaluationStatus.INSUFFICIENT_DATA),
        ("irregular_timestamps", EvaluationStatus.ATTENTION),
        ("isolated_outlier", EvaluationStatus.NOMINAL),
        ("partial_window", EvaluationStatus.ATTENTION),
    ],
)
def test_demonstration_expected_behavior(name: str, status: EvaluationStatus) -> None:
    scenario = next(item for item in demonstration_scenarios() if item.name == name)
    assert all(item.source == MeasurementSource.SIMULATED for item in scenario.measurements)
    result = evaluate(
        scenario.measurements,
        window_start=scenario.window_start,
        window_end=scenario.window_end,
        evaluated_at=scenario.window_end,
    )
    assert result.status == status
    assert all(item.status != EvaluationStatus.ALERT for item in result.findings)


def test_scenarios_are_reproducible_fresh_objects() -> None:
    first = demonstration_scenarios()
    second = demonstration_scenarios()
    assert first == second
    assert first is not second
    assert first[0].measurements[0] is not second[0].measurements[0]


def test_demo_prints_labelled_json_and_validates_all_contracts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    main()
    output = loads(capsys.readouterr().out)
    assert output["synthetic"] is True
    assert len(output["scenarios"]) == 9
    evaluation_schema = Draft202012Validator(load_schema("evaluation_result"))
    measurement_schema = Draft202012Validator(load_schema("physiological_measurement"))
    for scenario in output["scenarios"]:
        evaluation_schema.validate(scenario["evaluation"])
        EvaluationResult.model_validate(scenario["evaluation"])
        assert scenario["first_observation_without_baseline"]["status"] == "insufficient_data"
        for payload in scenario["measurements"]:
            measurement_schema.validate(payload)
            item = PhysiologicalMeasurement.model_validate(payload)
            assert item.source == MeasurementSource.SIMULATED
