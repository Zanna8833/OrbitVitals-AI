"""Demonstrations must stay simulated and evaluations must satisfy existing contracts."""

import json

import pytest
from jsonschema import Draft202012Validator

from app.domains.physical_activity import monitor_activity
from app.domains.physical_activity.demo import build_simulated_scenarios, main
from app.models import EvaluationResult, EvaluationStatus, HealthDomain, MeasurementSource
from tests.support import load_schema


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("simulated_target_adherence", EvaluationStatus.NOMINAL),
        ("simulated_missed_targets_and_reduction", EvaluationStatus.ATTENTION),
        ("simulated_rest_and_operational_exception", EvaluationStatus.NOMINAL),
        ("simulated_missing_and_degraded_records", EvaluationStatus.INSUFFICIENT_DATA),
        ("simulated_observations_without_history_or_targets", EvaluationStatus.INSUFFICIENT_DATA),
    ],
)
def test_demonstrations_are_simulated_and_contract_compatible(
    name: str, expected: EvaluationStatus
) -> None:
    request = build_simulated_scenarios()[name]
    assert request.measurements
    assert all(item.source == MeasurementSource.SIMULATED for item in request.measurements)
    assert all(item.baseline.baseline_id.startswith("sim-") for item in request.baselines)
    report = monitor_activity(request)
    assert report.evaluation.status == expected
    assert report.evaluation.domain == HealthDomain.PHYSICAL_ACTIVITY
    assert "SIMULATED DATA" in report.evaluation.summary
    assert all("SIMULATED DATA" in item.explanation for item in report.evaluation.findings)
    assert report.evaluation.algorithm.name == "physical_activity_monitor"
    payload = json.loads(report.evaluation.model_dump_json())
    assert EvaluationResult.model_validate(payload) == report.evaluation
    Draft202012Validator(load_schema("evaluation_result")).validate(payload)
    json.dumps(report.model_dump(mode="json"), allow_nan=False)


@pytest.mark.parametrize("arguments", [[], ["--full"]])
def test_demonstration_command_outputs_labeled_json(arguments: list[str], capsys) -> None:
    assert main(arguments) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_kind"] == "simulated"
    assert len(payload["scenarios"]) == 5
    assert all(item["data_kind"] == "simulated" for item in payload["scenarios"])
    assert all(("request" in item) == bool(arguments) for item in payload["scenarios"])


def test_demo_is_deterministic() -> None:
    assert build_simulated_scenarios() == build_simulated_scenarios()
