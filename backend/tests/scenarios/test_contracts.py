"""Local envelope safety and validation against every existing shared JSON Schema."""

import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.models import CONTRACT_MODELS, MeasurementSource
from app.scenarios import ReplayResult, canonical_json, replay_scenario, validate_contracts
from app.scenarios.codec import json_value
from app.scenarios.models import BehaviorCheck, ReplayInputs, ReplayOutputs
from app.scenarios.validation import SCHEMA_DIRECTORY, _contract_objects
from tests.scenarios.test_replay import SCENARIO_IDS


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_serialized_replay_and_every_shared_payload_validate(scenario_id: str) -> None:
    result = replay_scenario(scenario_id)
    encoded = canonical_json(result)
    restored = ReplayResult.model_validate_json(encoded)
    assert canonical_json(restored) == encoded
    assert validate_contracts(result) > 0
    assert json.loads(encoded)["data_kind"] == "simulated"


def test_validation_covers_all_five_published_contract_types_and_standalone_findings() -> None:
    kinds = {
        name
        for scenario_id in SCENARIO_IDS
        for _, name, _ in _contract_objects(replay_scenario(scenario_id))
    }
    assert kinds == {*CONTRACT_MODELS, "metric_finding"}


def test_invalid_typed_contract_cannot_be_hidden_in_a_valid_outer_envelope() -> None:
    result = replay_scenario("sensor_quality_failure")
    result.steps[0].outputs.evaluations[0].findings[0].unit = "hours"
    with pytest.raises(ValidationError, match="canonical unit"):
        validate_contracts(result)


def test_validator_reads_committed_schema_files_not_only_current_pydantic_models(
    tmp_path: Path,
) -> None:
    for name in CONTRACT_MODELS:
        schema = json.loads((SCHEMA_DIRECTORY / f"{name}.schema.json").read_text(encoding="utf-8"))
        if name == "evaluation_result":
            schema["properties"]["status"] = {"const": "alert"}
        (tmp_path / f"{name}.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(ValueError, match="Existing schema validation failed"):
        validate_contracts(replay_scenario("sensor_quality_failure"), schema_directory=tmp_path)


def test_missing_committed_schemas_fail_explicitly(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_contracts(replay_scenario("sensor_quality_failure"), schema_directory=tmp_path)


def test_malformed_committed_schema_fails_with_a_clear_error(tmp_path: Path) -> None:
    for name in CONTRACT_MODELS:
        schema = json.loads((SCHEMA_DIRECTORY / f"{name}.schema.json").read_text(encoding="utf-8"))
        if name == "physiological_measurement":
            schema["type"] = "invalid-json-schema-type"
        (tmp_path / f"{name}.schema.json").write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid committed schema physiological_measurement"):
        validate_contracts(replay_scenario("sensor_quality_failure"), schema_directory=tmp_path)


def test_rejected_payload_remains_outside_measurement_contract_validation() -> None:
    result = replay_scenario("insufficient_data")
    rejected = [item for step in result.steps for item in step.outputs.rejected_inputs]
    assert len(rejected) == 1
    assert rejected[0].data_kind == "simulated"
    assert rejected[0].payload["source"] == "simulated"
    assert rejected[0].validation_errors
    assert validate_contracts(result) > 0


@pytest.mark.parametrize("model", [ReplayInputs, ReplayOutputs])
def test_scenario_measurement_collections_reject_real_data(model: type) -> None:
    result = replay_scenario("sensor_quality_failure")
    measurement = (
        result.steps[0]
        .inputs.measurements[0]
        .model_copy(update={"source": MeasurementSource.WEARABLE})
    )
    field = "measurements" if model is ReplayInputs else "assessed_measurements"
    with pytest.raises(ValidationError, match="simulated"):
        model(**{field: (measurement,)})


def test_activity_request_sources_are_checked_in_the_envelope() -> None:
    request = replay_scenario("exercise_adherence_change").steps[0].inputs.activity_request
    request.measurements[0].source = MeasurementSource.WEARABLE
    with pytest.raises(ValidationError, match="simulated"):
        ReplayInputs(activity_request=request)


def test_rejected_candidates_must_keep_their_simulated_label() -> None:
    with pytest.raises(ValidationError, match="simulated"):
        ReplayInputs(rejected_candidates=({"source": "wearable"},))


def test_expected_actual_comparisons_cannot_claim_a_false_pass() -> None:
    with pytest.raises(ValidationError, match="expected versus actual"):
        BehaviorCheck(
            check_id="bad-check",
            description="Contradictory metadata",
            expected="nominal",
            actual="alert",
            passed=True,
        )


def test_aggregate_success_cannot_hide_failed_checks_or_blockers() -> None:
    payload = json.loads(canonical_json(replay_scenario("sensor_quality_failure")))
    payload["steps"][0]["checks"][0]["actual"] = "insufficient_data"
    payload["steps"][0]["checks"][0]["passed"] = False
    with pytest.raises(ValidationError, match="all_checks_passed"):
        ReplayResult.model_validate(payload)
    payload["all_checks_passed"] = False
    assert not ReplayResult.model_validate(payload).all_checks_passed
    payload = json.loads(canonical_json(replay_scenario("sensor_quality_failure")))
    payload["steps"][0]["blockers"] = ["A documented missing interface."]
    with pytest.raises(ValidationError, match="all_checks_passed"):
        ReplayResult.model_validate(payload)


@pytest.mark.parametrize("change", ["unknown_field", "duplicate_step", "empty_steps"])
def test_envelope_rejects_contract_drift_and_ambiguous_step_lists(change: str) -> None:
    payload = json.loads(canonical_json(replay_scenario("sensor_quality_failure")))
    if change == "unknown_field":
        payload["unexpected"] = "unknown"
    elif change == "duplicate_step":
        payload["steps"].append(payload["steps"][0])
    else:
        payload["steps"] = []
    with pytest.raises(ValidationError):
        ReplayResult.model_validate(payload)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_json_output_never_emits_non_finite_numbers(value: float) -> None:
    with pytest.raises(ValueError):
        canonical_json({"value": value})


def test_configuration_encoding_sorts_sets_and_makes_duration_units_explicit() -> None:
    from app.scenarios import fixtures

    encoded = json_value(fixtures.baseline_policy())
    assert encoded["quality"]["expected_intervals"]["heart_rate"] == {"seconds": 86400.0}
    assert encoded["established_min_span"] == {"seconds": 777600.0}
    assert canonical_json({"set": frozenset({"degraded", "acceptable"})}) == canonical_json(
        {"set": ["acceptable", "degraded"]}
    )


def test_naive_configuration_times_are_rejected_instead_of_using_host_timezone() -> None:
    with pytest.raises(ValueError, match="time zone"):
        canonical_json({"as_of": datetime(2026, 11, 1)})


def test_unknown_json_types_fail_explicitly() -> None:
    with pytest.raises(TypeError, match="Unsupported replay JSON value"):
        canonical_json(object())


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_every_timestamp_in_machine_readable_outputs_is_utc(scenario_id: str) -> None:
    time_fields = {
        "as_of",
        "measured_at",
        "interval_end",
        "computed_at",
        "assessed_at",
        "evaluated_at",
        "window_start",
        "window_end",
        "start_time",
        "end_time",
    }

    def inspect(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in time_fields and item is not None:
                    assert isinstance(item, str) and item.endswith("Z")
                inspect(item)
        elif isinstance(value, list):
            for item in value:
                inspect(item)

    inspect(json.loads(canonical_json(replay_scenario(scenario_id))))


def test_all_replays_and_schema_validation_work_with_network_connections_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def disallow(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Scenario execution and validation must be offline")

    monkeypatch.setattr(socket, "create_connection", disallow)
    monkeypatch.setattr(socket.socket, "connect", disallow)
    for scenario_id in SCENARIO_IDS:
        assert validate_contracts(replay_scenario(scenario_id)) > 0
