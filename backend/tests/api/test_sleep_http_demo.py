"""Real FastAPI sleep workflow, executed by the same client as the live HTTP demo."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.algorithms.data_quality import DataQualityConfig
from app.core.config import Settings
from app.main import create_app
from app.models import EvaluationResult, PersonalBaseline, PhysiologicalMeasurement
from app.services import integration
from app.services.commands import EvaluationCommand
from scripts.demo_sleep_http import (
    DemoError,
    JsonObject,
    Requester,
    build_cases,
    run_demo,
    sleep_policy,
    summarize,
    validate_responses,
)
from tests.api.conftest import NOW


def asgi_requester(client: TestClient) -> Requester:
    """Use real routes and engines without opening any network connection."""

    def request(method: str, url: str, payload: JsonObject | None) -> tuple[int, JsonObject]:
        response = (
            client.request(method, url, json=payload)
            if payload is not None
            else client.request(method, url)
        )
        return response.status_code, response.json()

    return request


def test_sleep_http_fixtures_are_deterministic_canonical_and_labelled() -> None:
    cases = build_cases()
    assert cases == build_cases()
    assert cases is not build_cases()
    assert [len(case["measurement_batch"]["measurements"]) for case in cases] == [29, 6, 10]
    for case in cases:
        assert case["crew_member_id"].startswith("sim-sleep-http-")
        for payload in case["measurement_batch"]["measurements"]:
            value = PhysiologicalMeasurement.model_validate(payload)
            assert value.source == "simulated"
            assert value.unit == {"sleep_duration": "min", "sleep_efficiency": "%"}[value.metric]
            assert value.data_quality is None
        command = EvaluationCommand.model_validate(case["evaluation_command"])
        assert command.evaluated_at == datetime(2026, 11, 11, 12, tzinfo=UTC)
        assert command.sleep_config.policy_id == "simulated-sleep-http-v1"
        assert command.window_end < command.evaluated_at
        for reference in case["baseline_commands"]:
            assert reference["reference_end"] < case["evaluation_command"]["window_start"]
            assert "SIMULATED" in reference["config"]["policy_source"]


def test_full_sleep_pipeline_uses_real_http_resources_and_scientific_results(
    api_client: TestClient,
) -> None:
    report = run_demo(requester=asgi_requester(api_client))
    assert report["all_checks_passed"]
    assert validate_responses(report) == 104
    primary, sparse, unusable = report["cases"]
    duration, efficiency = primary["baseline_responses"]
    assert (duration["status"], duration["sample_count"], duration["statistics"]["median"]) == (
        "established",
        7,
        480,
    )
    assert (
        efficiency["status"],
        efficiency["sample_count"],
        efficiency["statistics"]["median"],
    ) == ("established", 7, 92)
    assert all(
        item["algorithm"]["name"] == "personal_baseline" for item in primary["baseline_responses"]
    )
    assert Counter(
        item["data_quality"]["status"] for item in primary["ingestion_response"]["items"]
    ) == {"acceptable": 27, "unusable": 2}
    assert Counter(
        flag
        for item in primary["ingestion_response"]["items"]
        for flag in item["data_quality"]["flags"]
    ) == {"duplicate": 1, "signal_artifact": 1}
    evaluation = primary["evaluation_response"]
    assert evaluation["algorithm"]["name"] == "sleep_monitoring_trends"
    assert evaluation["status"] == "attention"
    assert evaluation["data_quality"]["status"] == "degraded"
    finding = evaluation["findings"][0]
    assert finding["observed_value"] == 430
    assert finding["baseline_value"] == 480
    assert finding["absolute_deviation"] == -50
    assert finding["relative_deviation"] == pytest.approx(-50 / 480)
    assert "Theil-Sen slope=-15 min/day" in finding["explanation"]
    assert "fitted change=-120 min" in finding["explanation"]
    assert "Included 7/9 complete night buckets" in finding["explanation"]
    assert "missing nights=2026-11-03, 2026-11-07" in finding["explanation"]
    assert "excluded non-acceptable" in finding["explanation"]
    assert evaluation["findings"][1]["observed_value"] == 92
    assert evaluation["findings"][1]["status"] == "nominal"
    assert "Included 6/9 complete night buckets" in evaluation["findings"][1]["explanation"]
    assert all(item["status"] == "insufficient_data" for item in sparse["baseline_responses"])
    assert all(item["sample_count"] == 1 for item in sparse["baseline_responses"])
    assert all(
        all(value is None for value in item["statistics"].values())
        for item in sparse["baseline_responses"]
    )
    assert sparse["evaluation_request"]["baseline_ids"] == []
    assert sparse["evaluation_response"]["status"] == "insufficient_data"
    assert sparse["evaluation_response"]["findings"][0]["observed_value"] == 472.5
    assert all(item["baseline_value"] is None for item in sparse["evaluation_response"]["findings"])
    assert unusable["baseline_responses"] == []
    assert unusable["evaluation_response"]["status"] == "insufficient_data"
    assert unusable["evaluation_response"]["data_quality"]["status"] == "unusable"
    assert all(
        item["observed_value"] is None for item in unusable["evaluation_response"]["findings"]
    )
    for case in report["cases"]:
        assert case["stored_evaluation_response"] == case["evaluation_response"]
        EvaluationResult.model_validate(case["stored_evaluation_response"])
        assert all(item["status"] != "alert" for item in case["evaluation_response"]["findings"])
        assert all(item["passed"] for item in case["checks"])
        assert all(PersonalBaseline.model_validate(item) for item in case["baseline_responses"])


def test_http_pipeline_calls_existing_scientific_functions(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spies = {}
    for name in ("assess_measurements", "assess_window", "build_baseline", "evaluate_sleep_window"):
        spy = Mock(wraps=getattr(integration, name))
        monkeypatch.setattr(integration, name, spy)
        spies[name] = spy
    assert run_demo(requester=asgi_requester(api_client))["all_checks_passed"]
    assert all(spy.call_count > 0 for spy in spies.values())
    assert spies["build_baseline"].call_count == 4
    assert spies["evaluate_sleep_window"].call_count == 3


def test_same_http_inputs_and_commands_produce_identical_stored_snapshots_on_retry(
    api_client: TestClient,
) -> None:
    first = run_demo(requester=asgi_requester(api_client))
    second = run_demo(requester=asgi_requester(api_client))
    assert second["all_checks_passed"]
    assert summarize(first) == summarize(second)
    for original, repeated in zip(first["cases"], second["cases"], strict=True):
        assert original["baseline_responses"] == repeated["baseline_responses"]
        assert original["evaluation_response"] == repeated["evaluation_response"]
        crew = original["crew_member_id"]
        assert len(api_client.get(f"/api/v1/crew-members/{crew}/evaluations").json()["items"]) == 1


def test_scientific_results_do_not_depend_on_ingestion_wall_clock() -> None:
    reports = []
    for at in (NOW, NOW + timedelta(days=5)):
        with TestClient(create_app(Settings(_env_file=None), clock=lambda at=at: at)) as client:
            reports.append(run_demo(requester=asgi_requester(client)))
    first, second = reports
    assert summarize(first) == summarize(second)
    assert first["cases"][0]["ingestion_response"] != second["cases"][0]["ingestion_response"]
    for original, repeated in zip(first["cases"], second["cases"], strict=True):
        assert original["evaluation_response"] == repeated["evaluation_response"]
        assert original["baseline_responses"] == repeated["baseline_responses"]


def test_get_verification_matches_by_id_rather_than_first_list_item(api_client: TestClient) -> None:
    initial = run_demo(requester=asgi_requester(api_client))
    primary = initial["cases"][0]
    crew = primary["crew_member_id"]
    newer = {
        **primary["evaluation_request"],
        "window_end": "2026-11-11T12:00:00Z",
        "evaluated_at": "2026-11-12T12:00:00Z",
    }
    response = api_client.post(f"/api/v1/crew-members/{crew}/evaluations", json=newer)
    assert response.status_code == 201
    rows = api_client.get(f"/api/v1/crew-members/{crew}/evaluations?domain=sleep").json()["items"]
    assert rows[0]["evaluation_id"] != primary["evaluation_response"]["evaluation_id"]
    repeated = run_demo(requester=asgi_requester(api_client))
    assert repeated["all_checks_passed"]
    assert repeated["cases"][0]["stored_evaluation_response"] == primary["evaluation_response"]


def test_namespace_contamination_is_detected_before_any_demo_post(api_client: TestClient) -> None:
    expected = build_cases()[0]["measurement_batch"]["measurements"][0]
    alien = {**expected, "measurement_id": "simulated-other-record"}
    assert (
        api_client.post("/api/v1/measurements", json={"measurements": [alien]}).status_code == 201
    )
    calls = []
    transport = asgi_requester(api_client)

    def traced(method: str, url: str, payload: JsonObject | None) -> tuple[int, JsonObject]:
        calls.append(method)
        return transport(method, url, payload)

    with pytest.raises(DemoError, match="another --namespace"):
        run_demo(requester=traced)
    assert set(calls) == {"GET"}
    assert api_client.get(
        f"/api/v1/crew-members/{expected['crew_member_id']}/baselines"
    ).json() == {"items": []}


def test_partial_prior_attempt_can_be_completed_without_resetting_server(
    api_client: TestClient,
) -> None:
    first_records = build_cases()[0]["measurement_batch"]["measurements"][:3]
    assert (
        api_client.post("/api/v1/measurements", json={"measurements": first_records}).status_code
        == 201
    )
    assert run_demo(requester=asgi_requester(api_client))["all_checks_passed"]


def test_get_content_mismatch_with_the_same_id_is_reported_not_masked(
    api_client: TestClient,
) -> None:
    transport = asgi_requester(api_client)

    def changed_get(method: str, url: str, payload: JsonObject | None) -> tuple[int, JsonObject]:
        status, body = transport(method, url, payload)
        if method == "GET" and "/evaluations?" in url and body["items"]:
            body["items"][0]["summary"] += " Changed by the test transport."
        return status, body

    report = run_demo(requester=changed_get)
    assert not report["all_checks_passed"]
    for case in report["cases"]:
        found = {check["name"]: check for check in case["checks"]}
        assert found["evaluation_id_found_once"]["passed"]
        assert not found["stored_evaluation_matches"]["passed"]
        assert (
            case["evaluation_response"]["evaluation_id"]
            == case["stored_evaluation_response"]["evaluation_id"]
        )


def test_explicit_client_sleep_policy_overrides_server_defaults() -> None:
    # A contradictory synthetic server policy proves the demo always supplies its own.
    server_config = EvaluationCommand.model_validate(
        {
            **build_cases()[0]["evaluation_command"],
            "sleep_config": {**sleep_policy(), "minimum_nights": 100},
        }
    ).sleep_config
    with TestClient(
        create_app(Settings(_env_file=None, sleep_config=server_config), clock=lambda: NOW)
    ) as client:
        assert run_demo(requester=asgi_requester(client))["all_checks_passed"]


def test_daily_acquisition_configuration_preserves_quality_and_retrieval_semantics() -> None:
    settings = Settings(
        _env_file=None,
        data_quality=DataQualityConfig(
            expected_intervals={
                "sleep_duration": timedelta(days=1),
                "sleep_efficiency": timedelta(days=1),
            }
        ),
    )
    with TestClient(create_app(settings, clock=lambda: NOW)) as client:
        report = run_demo(requester=asgi_requester(client))
    assert report["all_checks_passed"]
    duration = report["cases"][0]["evaluation_response"]["findings"][0]
    assert duration["data_quality"]["completeness"] == pytest.approx(7 / 9)
    assert (
        report["cases"][0]["stored_evaluation_response"]
        == report["cases"][0]["evaluation_response"]
    )


def test_other_synthetic_crews_are_untouched(api_client: TestClient) -> None:
    payload = {
        **build_cases()[0]["measurement_batch"]["measurements"][0],
        "measurement_id": "sim-other-workflow-record",
        "crew_member_id": "sim-other-workflow",
    }
    original = api_client.post("/api/v1/measurements", json={"measurements": [payload]}).json()
    assert run_demo(requester=asgi_requester(api_client))["all_checks_passed"]
    assert api_client.get("/api/v1/crew-members/sim-other-workflow/measurements").json() == original
