"""HTTP interface of the agent service."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from orbit_agent.api import create_app
from orbit_agent.config import API_PREFIX, load_settings
from orbit_agent.models import AgentResponse
from tests.support import CHEN, NOOR, FakeBackend, FakeOllama, make_agent

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "agent_response.schema.json"


def _client(**agent_arguments) -> TestClient:
    return TestClient(create_app(make_agent(**agent_arguments)))


def test_health_reports_dependencies() -> None:
    body = _client().get(f"{API_PREFIX}/health").json()

    assert body["status"] == "ok" and body["service"] == "orbitvitals-agent"
    assert body["backend"]["reachable"] is True
    assert body["primary_model"] == {
        "name": "qwen3.5:4b",
        "available": True,
        "unavailable_reason": None,
    }
    assert body["specialist"] == {"configured": "none", "available": False}
    assert body["evidence_corpus"]["passages"] == 25


def test_health_reports_a_missing_model_without_failing() -> None:
    client = _client(ollama=FakeOllama(reachable=False), backend=FakeBackend(reachable=False))
    body = client.get(f"{API_PREFIX}/health").json()

    assert body["status"] == "ok"
    assert body["backend"]["reachable"] is False
    assert body["primary_model"]["unavailable_reason"] == "ollama_unreachable"


def test_explanation_endpoint_returns_the_contract() -> None:
    response = _client().post(
        f"{API_PREFIX}/explanations",
        json={"crew_member_id": CHEN, "mode": "deterministic"},
    )

    assert response.status_code == 200
    parsed = AgentResponse.model_validate(response.json())
    assert parsed.crew_member_id == CHEN
    assert parsed.generation.mode == "deterministic_fallback"
    assert parsed.verification.passed
    assert parsed.disclaimer.startswith("Research prototype, not a medical device.")


def test_unknown_fields_and_values_are_rejected() -> None:
    client = _client()

    assert (
        client.post(
            f"{API_PREFIX}/explanations", json={"crew_member_id": NOOR, "prescribe": True}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{API_PREFIX}/explanations", json={"crew_member_id": NOOR, "domain": "cardiology"}
        ).status_code
        == 422
    )
    assert client.post(f"{API_PREFIX}/explanations", json={}).status_code == 422


def test_backend_failure_is_a_gateway_error() -> None:
    response = _client(backend=FakeBackend(reachable=False)).post(
        f"{API_PREFIX}/explanations", json={"crew_member_id": NOOR}
    )

    assert response.status_code == 502
    assert "could not be read" in response.json()["detail"]


def test_service_exposes_no_write_operation_on_crew_data() -> None:
    paths = _client().get("/openapi.json").json()["paths"]

    assert set(paths) == {
        f"{API_PREFIX}/health",
        f"{API_PREFIX}/explanations",
        f"{API_PREFIX}/evidence",
    }
    assert set(paths[f"{API_PREFIX}/explanations"]) == {"post"}


def test_evidence_search_returns_attributed_summaries() -> None:
    body = _client().get(f"{API_PREFIX}/evidence", params={"query": "exercise fitness"}).json()

    assert body["items"]
    assert all(item["url"].startswith("https://www.nasa.gov/") for item in body["items"])
    assert all(item["text_kind"] == "independent_summary" for item in body["items"])
    assert all("quote" not in item for item in body["items"])
    assert (
        _client().get(f"{API_PREFIX}/evidence", params={"query": "zzzz qqqq"}).json()["items"] == []
    )


def test_cors_allows_local_development_origins() -> None:
    response = _client().options(
        f"{API_PREFIX}/explanations",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_published_schema_matches_the_models() -> None:
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8")) == AgentResponse.model_json_schema()


def test_settings_are_read_from_the_environment() -> None:
    settings = load_settings(
        {
            "ORBITVITALS_AGENT_BACKEND_BASE_URL": "http://127.0.0.1:9000/api/v1",
            "ORBITVITALS_AGENT_MODEL_THINK": "true",
            "ORBITVITALS_AGENT_EVIDENCE_TOP_K": "5",
        }
    )

    assert settings.backend_base_url == "http://127.0.0.1:9000/api/v1"
    assert settings.model_think is True and settings.evidence_top_k == 5
    assert load_settings({}).primary_model == "qwen3.5:4b"
