"""Configuration, aggregation provenance and invalidation of dependent results."""

import json
from datetime import timedelta

from fastapi.testclient import TestClient

from app.algorithms.data_quality import DataQualityConfig, SensorRange
from app.core.config import Settings
from app.main import create_app
from app.models import MetricType
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
)
from tests.api.conftest import NOW


def test_scientific_settings_support_json_environment_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "ORBITVITALS_DATA_QUALITY", json.dumps({"expected_intervals": {"sleep_duration": "P1D"}})
    )
    monkeypatch.setenv("ORBITVITALS_SLEEP_CONFIG", json.dumps(simulated_sleep_policy()))
    settings = Settings(_env_file=None)
    assert settings.data_quality.expected_intervals[MetricType.SLEEP_DURATION] == timedelta(days=1)
    assert settings.sleep_config.policy_id == "simulated-api-test-policy"


def test_daily_totals_do_not_inherit_individual_record_sensor_ranges() -> None:
    settings = Settings(
        _env_file=None,
        data_quality=DataQualityConfig(
            sensor_ranges={
                "sim-device": {
                    MetricType.EXERCISE_DURATION: SensorRange(
                        0, 25, "SIMULATED per-session instrument range"
                    )
                }
            },
            expected_intervals={MetricType.EXERCISE_DURATION: timedelta(hours=12)},
        ),
    )
    records = [
        simulated_measurement(
            f"sim-range-{day}-{hour}",
            value=value,
            instant=START + timedelta(days=day, hours=hour),
            interval_end=(START + timedelta(days=day, hours=hour, minutes=30)).isoformat(),
        )
        for day, value in enumerate([10, 15, 20])
        for hour in (9, 10)
    ]
    command = {
        **baseline_command("exercise_duration"),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(),
        "config": {"established_min_samples": 3, "policy_source": "SIMULATED test criterion"},
    }
    with TestClient(create_app(settings, clock=lambda: NOW)) as client:
        ingested = client.post(f"{PREFIX}/measurements", json={"measurements": records})
        assert all(
            value["data_quality"]["status"] == "acceptable" for value in ingested.json()["items"]
        )
        response = client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert response.status_code == 201, response.text
    assert response.json()["statistics"]["mean"] == 30
    assert response.json()["status"] == "established"
    assert response.json()["data_quality"]["status"] == "acceptable"


def test_daily_baseline_rejects_ambiguous_source_types(api_client: TestClient) -> None:
    records = [
        simulated_measurement("sim-source-a", instant=START + timedelta(hours=9)),
        simulated_measurement(
            "sim-source-b", instant=START + timedelta(hours=11), source="manual_entry"
        ),
    ]
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    command = {
        **baseline_command("exercise_duration", days=1),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(1),
    }
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert response.status_code == 422
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json() == {"items": []}


def test_daily_baseline_use_requires_explicit_comparability(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([25, 30, 35])})
    command = {
        **baseline_command("exercise_duration"),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(),
    }
    baseline = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).json()
    evaluation = {**activity_command(), "baseline_ids": [baseline["baseline_id"]]}
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=evaluation)
    assert response.status_code == 422
    assert "baselines_comparable" in response.text


def test_baseline_backfill_invalidates_a_later_dependent_evaluation(api_client: TestClient) -> None:
    prior = START - timedelta(days=7)
    records = activity_records([25, 30, 35], start=prior) + activity_records([30, 30, 30])
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    command = {
        **baseline_command("exercise_duration", start=prior),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(start=prior),
        "config": {"established_min_samples": 3, "policy_source": "SIMULATED criterion"},
    }
    baseline = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).json()
    evaluation = {**activity_command(), "baseline_ids": [baseline["baseline_id"]]}
    evaluation["activity"]["baselines_comparable"] = True
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=evaluation)
    assert value.status_code == 201
    assert value.json()["findings"][0]["baseline_id"] == baseline["baseline_id"]
    backfill = simulated_measurement("sim-prior-backfill", instant=prior + timedelta(hours=12))
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [backfill]})
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json() == {"items": []}
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/evaluations").json() == {"items": []}


def test_unconfigured_sleep_output_still_normalizes_utc_timestamps(api_client: TestClient) -> None:
    command = sleep_command()
    command.pop("sleep_config")
    command["window_start"] = "2026-11-02T14:00:00+02:00"
    command["window_end"] = "2026-11-06T14:00:00+02:00"
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/evaluations", json=command)
    assert response.status_code == 201
    assert response.json()["window_start"] == "2026-11-02T12:00:00Z"
    assert response.json()["window_end"] == "2026-11-06T12:00:00Z"


def test_future_measurement_is_a_quality_failure_not_a_fabricated_observation(
    api_client: TestClient,
) -> None:
    record = simulated_measurement("sim-future", instant=NOW + timedelta(days=1))
    response = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]})
    assert response.status_code == 201
    assert response.json()["items"][0]["data_quality"]["status"] == "unusable"
    assert "later than the assessment time" in response.json()["items"][0]["data_quality"]["notes"]
