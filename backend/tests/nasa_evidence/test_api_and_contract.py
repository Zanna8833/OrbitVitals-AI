"""GET-only HTTP integration, additive schema and synthetic JSON example checks."""

import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.api.routes.nasa_evidence import get_evidence_adapter
from app.core.config import Settings
from app.main import create_app
from app.nasa_data.source import REPO_ROOT
from app.nasa_evidence import DatasetId, EvidenceTopic, encode_response
from app.nasa_evidence.__main__ import main
from scripts import export_nasa_evidence_schema
from tests.support import load_example


@pytest.mark.parametrize("topic", list(EvidenceTopic))
def test_http_returns_the_documented_contract(client: TestClient, topic) -> None:
    response = client.get("/api/v1/nasa-evidence", params={"topic": topic})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    Draft202012Validator(export_nasa_evidence_schema.build_document()).validate(response.json())
    assert response.json()["status"] == "ok"


def test_http_synthetic_end_to_end_does_not_touch_crew_resources(adapter) -> None:
    app = create_app(Settings(_env_file=None))
    app.dependency_overrides[get_evidence_adapter] = lambda: adapter
    with TestClient(app) as client:
        measurement = load_example("physiological_measurement")
        measurement["crew_member_id"] = "sim-mission-v1-02"
        measurement["source"] = "simulated"
        assert (
            client.post("/api/v1/measurements", json={"measurements": [measurement]}).status_code
            == 201
        )
        before = client.get("/api/v1/crew-members/sim-mission-v1-02/measurements").json()
        response = client.get("/api/v1/nasa-evidence?topic=data_quality")
        assert response.status_code == 200
        assert response.json()["contains_synthetic_findings"] is True
        assert response.json()["items"][1]["structural_findings"][0]["value"] == 7
        after = client.get("/api/v1/crew-members/sim-mission-v1-02/measurements").json()
        assert before == after and len(after["items"]) == 1
        assert after["items"][0]["source"] == "simulated"
        schema = client.get("/openapi.json").json()
        assert set(schema["paths"]["/api/v1/nasa-evidence"]) == {"get"}


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_endpoint_has_no_write_operations(client, method) -> None:
    assert getattr(client, method)("/api/v1/nasa-evidence?topic=sleep").status_code == 405


@pytest.mark.parametrize("query", ["", "?topic=diagnosis", "?topic=sleep&dataset_id=unknown"])
def test_invalid_retrieval_requests_are_rejected(client, query) -> None:
    assert client.get("/api/v1/nasa-evidence" + query).status_code == 422


def test_no_matching_topic_dataset_is_an_explained_empty_result(client) -> None:
    response = client.get(
        "/api/v1/nasa-evidence", params={"topic": "sleep", "dataset_id": DatasetId.MR001G}
    )
    assert response.status_code == 200 and response.json()["status"] == "no_matching_evidence"


def test_cache_settings_are_opt_in_and_isolated_between_apps(tmp_path) -> None:
    configured = create_app(Settings(_env_file=None, nasa_actigraphy_cache=tmp_path))
    default = create_app(Settings(_env_file=None))
    assert configured.state.nasa_evidence_adapter.retrieve("sleep").status == "partial"
    assert default.state.nasa_evidence_adapter.retrieve("sleep").status == "ok"


def test_evidence_cli_returns_safe_json_without_network(capsys) -> None:
    assert main(["--topic", "heart_rate"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["items"][0]["source_verification"]["state"] == "not_configured"
    assert not result["items"][0]["structural_findings"]


def test_evidence_cli_reports_missing_sources_without_private_paths(tmp_path, capsys) -> None:
    assert main(["--topic", "sleep", "--actigraphy-cache", str(tmp_path)]) == 2
    output = capsys.readouterr().out
    assert (
        str(tmp_path) not in output
        and json.loads(output)["failures"][0]["code"] == "source_missing"
    )


def test_additive_schema_is_valid_and_up_to_date() -> None:
    Draft202012Validator.check_schema(export_nasa_evidence_schema.build_document())
    assert export_nasa_evidence_schema.main(["--check"]) == 0


def test_schema_rejects_mr001g_units_and_unverified_numeric_findings(client) -> None:
    validator = Draft202012Validator(export_nasa_evidence_schema.build_document())
    mr001g = client.get("/api/v1/nasa-evidence?topic=heart_rate").json()
    mr001g["items"][0]["relevant_variables"][0]["canonical_unit"] = "min"
    assert not validator.is_valid(mr001g)
    mr001g = client.get("/api/v1/nasa-evidence?topic=heart_rate").json()
    mr001g["items"][0]["source_verification"]["state"] = "verified"
    assert not validator.is_valid(mr001g)
    mr001g["items"][0]["source_verification"] = {"state": "verified"}
    assert not validator.is_valid(mr001g)


def test_committed_example_uses_only_reproducible_synthetic_findings(adapter) -> None:
    example = json.loads((REPO_ROOT / "docs/examples/nasa-evidence-synthetic.json").read_text())
    expected = json.loads(encode_response(adapter.retrieve("data_quality")))
    assert example == expected
    assert example["contains_synthetic_findings"] is True
    Draft202012Validator(export_nasa_evidence_schema.build_document()).validate(example)


def test_schema_rejects_synthetic_findings_mislabeled_as_nasa_evidence(adapter) -> None:
    validator = Draft202012Validator(export_nasa_evidence_schema.build_document())
    payload = json.loads(encode_response(adapter.retrieve("data_quality")))
    payload["contains_synthetic_findings"] = False
    assert not validator.is_valid(payload)
    payload = json.loads(encode_response(adapter.retrieve("data_quality")))
    payload["items"][0]["structural_findings"][0]["data_origin"] = "verified_nasa_source_files"
    assert not validator.is_valid(payload)
