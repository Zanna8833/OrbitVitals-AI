"""End-to-end requests use real sleep/activity modules, quality and prior personal references."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.algorithms.data_quality import DataQualityConfig, SensorRange
from app.core.config import Settings
from app.main import create_app
from app.models import EvaluationResult
from tests.api.builders import (
    PREFIX,
    START,
    activity_command,
    activity_options,
    activity_records,
    baseline_command,
    simulated_measurement,
    simulated_sleep_policy,
    sleep_command,
    sleep_records,
)
from tests.api.conftest import NOW
from tests.support import load_schema


def test_sleep_trends_run_through_ingestion_evaluation_and_retrieval(
    api_client: TestClient,
) -> None:
    records = sleep_records([480, 460, 440, 420])
    assert (
        api_client.post(f"{PREFIX}/measurements", json={"measurements": records}).status_code == 201
    )
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=sleep_command())
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["algorithm"]["name"] == "sleep_monitoring_trends"
    assert value["status"] == "attention"
    assert value["findings"][0]["observed_value"] == 450
    assert "slope=-20" in value["findings"][0]["explanation"]
    assert value["findings"][0]["data_quality"]["algorithm"]["name"] == "data_quality"
    assert value["findings"][0]["baseline_id"] is None
    assert "SIMULATED DATA" in value["summary"]
    EvaluationResult.model_validate(value)
    Draft202012Validator(load_schema("evaluation_result")).validate(value)
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json() == {
        "items": [value]
    }


def test_sleep_baseline_comparison_uses_a_real_established_prior_reference(
    api_client: TestClient,
) -> None:
    prior = START - timedelta(days=7)
    records = sleep_records([470, 480, 490], start=prior) + sleep_records([420, 420, 420])
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    baseline = {
        **baseline_command(start=prior),
        "config": {
            "established_min_samples": 3,
            "policy_source": "SIMULATED integration test criterion",
        },
    }
    created = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "established"
    command = {**sleep_command(3), "baseline_ids": [created.json()["baseline_id"]]}
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 201, response.text
    finding = response.json()["findings"][0]
    assert finding["baseline_value"] == 480
    assert finding["absolute_deviation"] == -60
    assert finding["baseline_id"] == created.json()["baseline_id"]
    assert finding["status"] == "attention"


def test_sleep_policy_is_never_filled_from_demonstration_defaults(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": sleep_records([480] * 4)})
    command = sleep_command()
    command.pop("sleep_config")
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command).json()
    assert value["status"] == "insufficient_data"
    assert value["algorithm"]["name"] == "api_orchestration"
    assert "policy is not configured" in value["summary"]
    assert all(item["observed_value"] is None for item in value["findings"])


def test_server_sleep_policy_can_be_configured_without_changing_frontend_payloads() -> None:
    settings = Settings(_env_file=None, sleep_config=simulated_sleep_policy())
    with TestClient(create_app(settings, clock=lambda: NOW)) as client:
        client.post(f"{PREFIX}/measurements", json={"measurements": sleep_records([480] * 4)})
        command = sleep_command()
        command.pop("sleep_config")
        value = client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command).json()
    assert value["algorithm"]["name"] == "sleep_monitoring_trends"
    assert value["status"] == "nominal"


@pytest.mark.parametrize("days", [0, 2])
def test_sleep_missing_or_short_history_is_insufficient(api_client: TestClient, days: int) -> None:
    records = sleep_records([480] * days)
    if records:
        api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    value = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json=sleep_command()
    ).json()
    assert value["status"] == "insufficient_data"
    assert all(item["baseline_value"] is None for item in value["findings"])
    assert all(item["status"] == "insufficient_data" for item in value["findings"])


def test_sleep_degraded_sensor_values_do_not_create_physiological_findings() -> None:
    settings = Settings(
        _env_file=None,
        data_quality=DataQualityConfig(
            sensor_ranges={
                "sim-device": {
                    "sleep_duration": SensorRange(0, 600, "SIMULATED device specification")
                }
            }
        ),
    )
    with TestClient(create_app(settings, clock=lambda: NOW)) as client:
        ingestion = client.post(
            f"{PREFIX}/measurements", json={"measurements": sleep_records([700] * 4)}
        )
        assert ingestion.json()["items"][0]["data_quality"]["status"] == "degraded"
        value = client.post(
            f"{PREFIX}/crew-members/sim-crew/evaluations", json=sleep_command()
        ).json()
    assert value["findings"][0]["status"] == "insufficient_data"
    assert value["findings"][0]["observed_value"] is None
    assert "excluded non-acceptable" in value["findings"][0]["explanation"]
    assert value["findings"][1]["status"] == "nominal"


def test_exercise_targets_and_progressive_reductions_use_the_real_module(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([40, 30, 20])})
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json=activity_command()
    )
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["algorithm"]["name"] == "physical_activity_monitor"
    assert value["status"] == "attention"
    assert value["findings"][0]["observed_value"] == 30
    assert "Progressive reduction" in value["findings"][0]["explanation"]
    assert value["findings"][1]["status"] == "nominal"
    EvaluationResult.model_validate(value)
    Draft202012Validator(load_schema("evaluation_result")).validate(value)


def test_exercise_daily_baseline_is_built_then_compared_end_to_end(api_client: TestClient) -> None:
    prior = START - timedelta(days=7)
    records = activity_records([25, 30, 35], start=prior) + activity_records([15, 15, 15])
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    baseline = {
        **baseline_command("exercise_duration", start=prior),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(start=prior),
        "config": {"established_min_samples": 3, "policy_source": "SIMULATED API test"},
    }
    created = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline)
    assert created.status_code == 201, created.text
    assert created.json()["status"] == "established"
    command = activity_command()
    command["baseline_ids"] = [created.json()["baseline_id"]]
    command["activity"]["baselines_comparable"] = True
    command["activity"]["policies"][0]["baseline_absolute_tolerance"] = 5
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 201, response.text
    finding = response.json()["findings"][0]
    assert finding["baseline_value"] == 30
    assert finding["absolute_deviation"] == -15
    assert finding["status"] == "attention"


def test_exercise_without_coverage_does_not_assume_complete_days(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([40, 30, 20])})
    command = activity_command()
    command["activity"].pop("coverage")
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command).json()
    assert value["status"] == "insufficient_data"
    assert value["findings"][0]["observed_value"] is None


def test_missing_exercise_records_are_unknown_unless_recording_is_confirmed_complete(
    api_client: TestClient,
) -> None:
    command = activity_command()
    command.pop("activity")
    value = api_client.post(f"{PREFIX}/crew-members/sim-empty/evaluations", json=command).json()
    assert value["status"] == "insufficient_data"
    assert all(item["observed_value"] is None for item in value["findings"])


def test_exercise_rest_day_does_not_create_a_missed_target(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([30, 0, 30])})
    command = activity_command()
    command["activity"]["day_plans"] = [
        {"day": (START + timedelta(days=1)).date().isoformat(), "planned_rest": True}
    ]
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command).json()
    assert value["status"] == "nominal"
    assert value["findings"][0]["observed_value"] == 30


def test_exercise_quality_failures_do_not_become_missed_targets(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([-1, -2, -3])})
    value = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json=activity_command()
    ).json()
    assert value["status"] == "insufficient_data"
    assert value["findings"][0]["observed_value"] is None
    assert value["findings"][1]["status"] == "nominal"


@pytest.mark.parametrize(
    "overrides",
    [
        {"domain": "vital_signs"},
        {"domain": "nutrition"},
        {"domain": "cognition"},
        {"window_start": "2026-11-02T00:00:00"},
        {"window_end": START.isoformat()},
        {"window_end": "2027-01-01T00:00:00Z"},
        {"evaluated_at": "2027-01-01T00:00:00Z"},
        {"unknown": True},
        {"sleep_config": {}},
    ],
)
def test_invalid_or_unintegrated_evaluation_commands_are_422(
    api_client: TestClient, overrides: dict
) -> None:
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json={**activity_command(), **overrides}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_invalid_session_links_are_422_and_do_not_store_an_evaluation(
    api_client: TestClient,
) -> None:
    command = activity_command()
    command["activity"]["sessions"] = [
        {
            "session_id": "sim-unknown",
            "start_time": START.isoformat(),
            "measurement_ids": ["missing"],
        }
    ]
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 422
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json() == {"items": []}


def test_baseline_ids_cannot_cross_crew_boundaries(api_client: TestClient) -> None:
    created = api_client.post(f"{PREFIX}/crew-members/other/baselines", json=baseline_command())
    command = {**sleep_command(), "baseline_ids": [created.json()["baseline_id"]]}
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 404


def test_session_baseline_cannot_silently_be_used_as_a_daily_activity_baseline(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([25, 30, 35])})
    created = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    command = {**activity_command(), "baseline_ids": [created.json()["baseline_id"]]}
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 422
    assert "complete_active_day_total" in response.text


def test_evaluation_retrieval_filters_order_and_crew_isolation(api_client: TestClient) -> None:
    first = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json=activity_command(2)
    ).json()
    later = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/evaluations", json=activity_command(3)
    ).json()
    response = api_client.get(
        f"{PREFIX}/crew-members/sim-crew/evaluations",
        params={"domain": "physical_activity", "limit": 1},
    )
    assert response.json() == {"items": [later]}
    assert api_client.get(f"{PREFIX}/crew-members/other/evaluations").json() == {"items": []}
    assert api_client.get(
        f"{PREFIX}/crew-members/sim-crew/evaluations", params={"domain": "sleep"}
    ).json() == {"items": []}
    bounds = {"start": first["window_end"], "end": later["window_end"]}
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations", params=bounds).json() == {
        "items": [first]
    }


def test_backfill_removes_a_stale_evaluation(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=activity_command())
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json()["items"]) == 1
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [simulated_measurement()]})
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json() == {"items": []}
