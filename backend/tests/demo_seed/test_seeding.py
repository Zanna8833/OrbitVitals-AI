"""The seeder relies on real endpoint results, including failures and missing data."""

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.core.config import Settings
from app.demo_seed.client import SeedError, seed_api
from app.demo_seed.dataset import build_plan
from app.main import create_app
from app.models import EvaluationResult, PersonalBaseline
from app.scenarios import fixtures
from tests.demo_seed.support import TestApi
from tests.support import load_schema


def test_seed_uses_real_endpoints_and_preserves_schema_valid_computed_results(
    api_client: TestClient,
) -> None:
    api = TestApi(api_client)
    report = seed_api(api, batch_size=37)
    assert report["all_checks_passed"] is True
    assert sum(crew["stored_measurement_count"] for crew in report["crews"]) == 893
    assert sum(len(crew["baselines"]) for crew in report["crews"]) == 36
    assert sum(len(crew["evaluations"]) for crew in report["crews"]) == 13
    last_ingest = max(
        index for index, call in enumerate(api.calls) if call == ("POST", "/measurements")
    )
    first_compute = min(
        index
        for index, (method, path) in enumerate(api.calls)
        if method == "POST" and path != "/measurements"
    )
    assert last_ingest < first_compute
    for crew in report["crews"]:
        for payload in crew["baselines"]:
            value = PersonalBaseline.model_validate(payload)
            assert value.algorithm.name == "personal_baseline"
            assert value.crew_member_id == crew["crew_member_id"]
            Draft202012Validator(load_schema("personal_baseline")).validate(payload)
        for item in crew["evaluations"]:
            value = EvaluationResult.model_validate(item["result"])
            assert value.crew_member_id == crew["crew_member_id"]
            assert value.domain.value in ("sleep", "physical_activity")
            assert value.status.value != "alert"
            assert "SIMULATED DATA" in value.summary
            Draft202012Validator(load_schema("evaluation_result")).validate(item["result"])
    assert report["crews"][2]["quality_status_counts"]["unusable"] == 7


def test_seed_is_idempotent_and_keeps_other_crew_histories(api_client: TestClient) -> None:
    record = (
        build_plan()[0]
        .measurements[0]
        .model_copy(
            update={
                "measurement_id": "sim-unrelated-measurement",
                "crew_member_id": "sim-unrelated",
            }
        )
    )
    api_client.post("/api/v1/measurements", json={"measurements": [record.model_dump(mode="json")]})
    api = TestApi(api_client)
    first = seed_api(api)
    second = seed_api(api)
    assert first == second
    for crew in second["crews"]:
        root = f"/api/v1/crew-members/{crew['crew_member_id']}"
        assert len(api_client.get(root + "/baselines").json()["items"]) == 12
        assert len(api_client.get(root + "/evaluations").json()["items"]) == len(
            crew["evaluations"]
        )
    assert (
        len(api_client.get("/api/v1/crew-members/sim-unrelated/measurements").json()["items"]) == 1
    )


@pytest.mark.parametrize("conflict", ["value", "unexpected_id"])
def test_reserved_crew_conflicts_fail_before_any_write(
    api_client: TestClient, conflict: str
) -> None:
    original = build_plan()[0].measurements[0]
    changes = (
        {"value": original.value + 1}
        if conflict == "value"
        else {"measurement_id": "sim-unexpected"}
    )
    value = original.model_copy(update=changes)
    api_client.post("/api/v1/measurements", json={"measurements": [value.model_dump(mode="json")]})
    api = TestApi(api_client)
    with pytest.raises(SeedError, match="unexpected/conflicting"):
        seed_api(api)
    assert all(method == "GET" for method, _ in api.calls)


def test_changed_fixture_inputs_cannot_be_hidden_by_predefined_results(
    api_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        fixtures,
        "restriction_records",
        lambda: fixtures.sleep_records(
            "flat-counterexample", (490,) * 9, (92,) * 9, missing_nights=frozenset({2, 6})
        ),
    )
    report = seed_api(TestApi(api_client))
    assert report["all_checks_passed"] is False
    declining = report["crews"][1]
    final = next(item for item in declining["evaluations"] if item["checkpoint"] == "sleep-day-09")
    assert final["result"]["status"] == "nominal"
    check = next(item for item in declining["checks"] if item["check_id"] == "sleep-day-09")
    assert (check["expected"], check["actual"], check["passed"]) == ("attention", "nominal", False)


def test_old_server_clock_is_rejected_before_any_writes() -> None:
    class OldClockApi:
        def __init__(self) -> None:
            self.calls = []

        def request(self, method, path, payload=None):
            self.calls.append((method, path))
            return {"status": "ok", "timestamp": "2026-01-01T00:00:00Z"}

    api = OldClockApi()
    with pytest.raises(SeedError, match="Server clock"):
        seed_api(api)
    assert api.calls == [("GET", "/health")]


@pytest.mark.parametrize("size", [0, -1, 1001])
def test_invalid_batch_size_cannot_send_requests(size: int, api_client: TestClient) -> None:
    api = TestApi(api_client)
    with pytest.raises(SeedError, match="batch-size"):
        seed_api(api, batch_size=size)
    assert api.calls == []


def test_incompatible_server_catalog_is_rejected_before_ingestion(api_client: TestClient) -> None:
    delegate = TestApi(api_client)

    class IncompatibleApi:
        def request(self, method: str, path: str, payload=None) -> dict:
            result = delegate.request(method, path, payload)
            if path == "/metrics":
                result["items"] = []
            return result

    with pytest.raises(SeedError, match="incompatible"):
        seed_api(IncompatibleApi())
    assert all(method == "GET" for method, _ in delegate.calls)


def test_computed_reports_are_reproducible_after_a_fresh_api_restart() -> None:
    from datetime import UTC, datetime

    reports = []
    for day in (14, 15):
        app = create_app(
            Settings(_env_file=None), clock=lambda day=day: datetime(2026, 11, day, tzinfo=UTC)
        )
        with TestClient(app) as client:
            reports.append(seed_api(TestApi(client)))
    # Ingestion assessment times differ; fixed baseline/evaluation horizons and
    # unchanged input/policy produce the same real scientific results and IDs.
    assert reports[0] == reports[1]
