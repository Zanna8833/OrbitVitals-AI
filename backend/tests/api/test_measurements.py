"""HTTP ingestion, quality assessment, identity, filtering and per-app isolation."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.algorithms.data_quality import DataQualityConfig, SensorRange
from app.core.config import Settings
from app.main import create_app
from app.models import METRIC_CATALOG, PhysiologicalMeasurement
from tests.api.builders import PREFIX, START, simulated_measurement
from tests.api.conftest import NOW
from tests.support import load_schema


def test_catalog_uses_canonical_definitions(api_client: TestClient) -> None:
    response = api_client.get(f"{PREFIX}/metrics")
    assert response.status_code == 200
    assert response.json() == {
        "items": [value.model_dump(mode="json") for value in METRIC_CATALOG.values()]
    }


def test_ingestion_returns_real_quality_and_unchanged_measurement_values(
    api_client: TestClient,
) -> None:
    record = simulated_measurement()
    response = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]})
    assert response.status_code == 201
    value = response.json()["items"][0]
    assert value["value"] == 30
    assert value["data_quality"]["algorithm"]["name"] == "data_quality"
    assert value["data_quality"]["status"] == "acceptable"
    assert "status" not in value
    assert PhysiologicalMeasurement.model_validate(value).measurement_id == record["measurement_id"]
    Draft202012Validator(load_schema("physiological_measurement")).validate(value)
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json() == response.json()


@pytest.mark.parametrize(
    "overrides",
    [
        {"unit": "hours"},
        {"value": "bad"},
        {"value": None},
        {"metric": "unknown"},
        {"measured_at": "2026-11-02T00:00:00"},
        {"source": "unknown"},
        {"unexpected": True},
        {"crew_member_id": ""},
        {"interval_end": "2026-11-01T00:00:00Z"},
    ],
)
def test_invalid_measurement_is_422_and_does_not_write(
    api_client: TestClient, overrides: dict
) -> None:
    record = {**simulated_measurement(), **overrides}
    response = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]})
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json() == {"items": []}


@pytest.mark.parametrize("body", [{}, {"measurements": []}, [], {"measurements": [], "extra": 1}])
def test_malformed_batches_are_422(api_client: TestClient, body) -> None:
    assert api_client.post(f"{PREFIX}/measurements", json=body).status_code == 422


def test_malformed_json_is_a_json_error(api_client: TestClient) -> None:
    response = api_client.post(
        f"{PREFIX}/measurements", content="{not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


@pytest.mark.parametrize("token", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_json_values_return_a_json_validation_error(
    api_client: TestClient, token: str
) -> None:
    payload = json.dumps({"measurements": [simulated_measurement()]})
    payload = payload.replace('"value": 30', f'"value": {token}')
    response = api_client.post(
        f"{PREFIX}/measurements", content=payload, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_identical_ids_are_idempotent_across_and_within_batches(api_client: TestClient) -> None:
    record = simulated_measurement()
    first = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record, record]})
    second = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]})
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert len(second.json()["items"]) == 1
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]) == 1


def test_conflicting_ids_reject_the_entire_batch(api_client: TestClient) -> None:
    record = simulated_measurement()
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]})
    response = api_client.post(
        f"{PREFIX}/measurements",
        json={
            "measurements": [
                simulated_measurement("sim-new", instant=START + timedelta(hours=1)),
                {**record, "value": 40},
            ]
        },
    )
    assert response.status_code == 409
    assert isinstance(response.json()["detail"], str)
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]) == 1


def test_conflicting_ids_in_one_batch_do_not_partially_write(api_client: TestClient) -> None:
    record = simulated_measurement()
    assert (
        api_client.post(
            f"{PREFIX}/measurements", json={"measurements": [record, {**record, "value": 31}]}
        ).status_code
        == 409
    )
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json() == {"items": []}


def test_duplicate_observations_with_distinct_ids_use_the_real_engine(
    api_client: TestClient,
) -> None:
    response = api_client.post(
        f"{PREFIX}/measurements",
        json={"measurements": [simulated_measurement("sim-a"), simulated_measurement("sim-b")]},
    )
    values = response.json()["items"]
    assert values[0]["data_quality"]["status"] == "acceptable"
    assert values[1]["data_quality"]["status"] == "unusable"
    assert "duplicate" in values[1]["data_quality"]["flags"]


def test_conflicting_observations_across_batches_reassess_history(api_client: TestClient) -> None:
    api_client.post(
        f"{PREFIX}/measurements", json={"measurements": [simulated_measurement("sim-a", value=30)]}
    )
    api_client.post(
        f"{PREFIX}/measurements", json={"measurements": [simulated_measurement("sim-b", value=31)]}
    )
    values = api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]
    assert [value["value"] for value in values] == [30, 31]
    assert all(value["data_quality"]["status"] == "unusable" for value in values)


def test_impossible_values_do_not_become_physiological_alerts(api_client: TestClient) -> None:
    record = simulated_measurement(value=-1, data_quality={"status": "acceptable"})
    value = api_client.post(f"{PREFIX}/measurements", json={"measurements": [record]}).json()[
        "items"
    ][0]
    assert value["value"] == -1
    assert value["data_quality"]["status"] == "unusable"
    assert value["data_quality"]["flags"] == ["signal_artifact"]


def test_paired_pressure_check_works_across_requests(api_client: TestClient) -> None:
    first = simulated_measurement("sim-sys", "systolic_blood_pressure", 100)
    second = simulated_measurement("sim-dia", "diastolic_blood_pressure", 110)
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [first]})
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [second]})
    values = api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]
    assert all(value["data_quality"]["status"] == "unusable" for value in values)


def test_documented_device_range_can_be_configured() -> None:
    quality = DataQualityConfig(
        sensor_ranges={
            "sim-device": {
                "exercise_duration": SensorRange(
                    minimum=0,
                    maximum=20,
                    source="SIMULATED test-device range; not a clinical limit",
                )
            }
        }
    )
    with TestClient(
        create_app(Settings(_env_file=None, data_quality=quality), clock=lambda: NOW)
    ) as client:
        response = client.post(
            f"{PREFIX}/measurements", json={"measurements": [simulated_measurement()]}
        )
    value = response.json()["items"][0]
    assert value["data_quality"]["status"] == "degraded"
    assert value["data_quality"]["flags"] == ["out_of_sensor_range"]


def test_filters_order_and_utc_normalization(api_client: TestClient) -> None:
    records = [
        simulated_measurement("sim-later", instant=START + timedelta(days=1)),
        simulated_measurement("sim-first", measured_at="2026-11-02T02:00:00+02:00"),
        simulated_measurement("sim-energy", "active_energy_expenditure", 200),
    ]
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    response = api_client.get(
        f"{PREFIX}/crew-members/sim-crew/measurements",
        params={
            "metric": "exercise_duration",
            "start": START.isoformat(),
            "end": (START + timedelta(days=1)).isoformat(),
            "limit": 1,
        },
    )
    assert [item["measurement_id"] for item in response.json()["items"]] == ["sim-first"]
    assert response.json()["items"][0]["measured_at"] == "2026-11-02T00:00:00Z"


@pytest.mark.parametrize(
    "params",
    [
        {"metric": "bad"},
        {"limit": 0},
        {"limit": 1001},
        {"start": "2026-11-02T00:00:00"},
        {"start": "2026-11-03T00:00:00Z", "end": "2026-11-02T00:00:00Z"},
    ],
)
def test_invalid_query_filters_are_422(api_client: TestClient, params: dict) -> None:
    assert (
        api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements", params=params).status_code
        == 422
    )


def test_crew_isolation_and_global_identity_conflicts(api_client: TestClient) -> None:
    records = [
        simulated_measurement("sim-a", crew="sim-a"),
        simulated_measurement("sim-b", crew="sim-b"),
    ]
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    for crew in ("sim-a", "sim-b"):
        values = api_client.get(f"{PREFIX}/crew-members/{crew}/measurements").json()["items"]
        assert len(values) == 1 and values[0]["crew_member_id"] == crew
    collision = {**records[0], "crew_member_id": "sim-b"}
    assert (
        api_client.post(f"{PREFIX}/measurements", json={"measurements": [collision]}).status_code
        == 409
    )


def test_apps_have_separate_stores(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [simulated_measurement()]})
    with TestClient(create_app(Settings(_env_file=None))) as other:
        assert other.get(f"{PREFIX}/crew-members/sim-crew/measurements").json() == {"items": []}


def test_concurrent_retries_preserve_one_identity(api_client: TestClient) -> None:
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(
            executor.map(
                lambda _: api_client.post(
                    f"{PREFIX}/measurements", json={"measurements": [simulated_measurement()]}
                ),
                range(8),
            )
        )
    assert all(response.status_code == 201 for response in responses)
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]) == 1
