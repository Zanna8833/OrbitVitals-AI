"""Frontend-facing OpenAPI, stable resource shapes and JSON CORS preflights."""

import json

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.core.config import Settings
from app.main import create_app
from tests.api.builders import PREFIX, activity_command, simulated_sleep_policy, sleep_command


def test_openapi_generation_contains_implemented_paths_and_valid_component_schemas(
    api_client: TestClient,
) -> None:
    response = api_client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    expected = {
        f"{PREFIX}/health": {"get"},
        f"{PREFIX}/metrics": {"get"},
        f"{PREFIX}/nasa-evidence": {"get"},
        f"{PREFIX}/measurements": {"post"},
        f"{PREFIX}/crew-members/{{crew_member_id}}/measurements": {"get"},
        f"{PREFIX}/crew-members/{{crew_member_id}}/baselines": {"get", "post"},
        f"{PREFIX}/crew-members/{{crew_member_id}}/evaluations": {"get", "post"},
    }
    assert set(document["paths"]) == set(expected)
    identifiers = []
    for path, methods in expected.items():
        assert set(document["paths"][path]) == methods
        identifiers.extend(document["paths"][path][method]["operationId"] for method in methods)
    assert len(set(identifiers)) == len(identifiers)
    for schema in document["components"]["schemas"].values():
        Draft202012Validator.check_schema(schema)
    json.dumps(document, allow_nan=False)

    def resolve_references(value) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                target = document
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
            for item in value.values():
                resolve_references(item)
        elif isinstance(value, list):
            for item in value:
                resolve_references(item)

    resolve_references(document)


@pytest.mark.parametrize(
    "origin", ["http://localhost:5173", "http://localhost:53124", "http://127.0.0.1:3000"]
)
def test_development_json_preflights_allow_react_and_flutter_origins(
    api_client: TestClient, origin: str
) -> None:
    response = api_client.options(
        f"{PREFIX}/measurements",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_unknown_browser_origin_is_not_granted_access(api_client: TestClient) -> None:
    response = api_client.options(
        f"{PREFIX}/measurements",
        headers={
            "Origin": "https://unknown.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_explicit_frontend_origin_can_be_configured() -> None:
    origin = "https://frontend.example"
    with TestClient(create_app(Settings(_env_file=None, cors_allow_origins=[origin]))) as client:
        response = client.get(f"{PREFIX}/metrics", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("resource", ["measurements", "baselines", "evaluations"])
def test_empty_data_is_an_empty_list_envelope(api_client: TestClient, resource: str) -> None:
    response = api_client.get(f"{PREFIX}/crew-members/sim-no-data/{resource}")
    assert response.status_code == 200
    assert response.json() == {"items": []}


def test_validation_errors_are_json_and_include_cors_headers(api_client: TestClient) -> None:
    response = api_client.post(
        f"{PREFIX}/measurements", json={}, headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 422
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["content-type"] == "application/json"
    assert response.json()["detail"][0]["loc"][0] == "body"


@pytest.mark.parametrize("mutation", ["unknown", "negative", "missing"])
def test_sleep_policy_validation_does_not_silently_ignore_invalid_fields(
    api_client: TestClient, mutation: str
) -> None:
    command = sleep_command()
    policy = simulated_sleep_policy()
    if mutation == "unknown":
        policy["duration"]["unknown_threshold"] = 1
    elif mutation == "negative":
        policy["duration"]["minimum_slope_per_day"] = -1
    else:
        policy.pop("duration")
    command["sleep_config"] = policy
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 422


def test_evaluation_replay_with_explicit_time_is_deterministic(api_client: TestClient) -> None:
    command = {**activity_command(), "evaluated_at": "2026-11-10T00:00:00Z"}
    first = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    second = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json() == {
        "items": [first.json()]
    }
