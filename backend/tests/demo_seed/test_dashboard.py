"""Synthetic dashboard coverage without changing the original scientific scenarios."""

import hashlib
from datetime import timedelta
from statistics import median

import pytest
from fastapi.testclient import TestClient

from app.demo_seed.client import SeedError, seed_api
from app.demo_seed.dataset import (
    ACQUISITION_PROTOCOLS,
    CURRENT_START,
    DASHBOARD_METRICS,
    METRICS,
    REFERENCE_START,
    acquisition_device_id,
    build_plan,
)
from app.models import (
    METRIC_CATALOG,
    MeasurementSource,
    MetricType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from app.scenarios import fixtures
from app.scenarios.codec import canonical_json
from tests.demo_seed.support import TestApi

NEW_METRICS = frozenset(
    {
        MetricType.HEART_RATE_VARIABILITY_RMSSD,
        MetricType.SYSTOLIC_BLOOD_PRESSURE,
        MetricType.DIASTOLIC_BLOOD_PRESSURE,
        MetricType.BODY_TEMPERATURE,
        MetricType.BODY_MASS,
    }
)
LEGACY_SCENARIO_METRICS = frozenset((*fixtures.SLEEP_METRICS, *fixtures.ACTIVITY_METRICS))
# Captured from origin/main 14125559a1a1b64c54ec86214d858296a73075a8.
# These pin the existing synthetic inputs and actual engine results, not diagnoses.
LEGACY_INPUT_HASHES = (
    "07ca212dc8377ac679e9eeabeff12780f8d1c617c65da3730fcd615795c19cee",
    "6393b00a991bfb900f9d57cab694f83ebe2b3a6828fa6e385cf0b6a7b00d7b2e",
    "da1f81d198eb27fc1c02822d9be7352cf8415afc99e9a1f34468435485bf2c1a",
)
LEGACY_COMMAND_HASHES = (
    "59b1ac076dda18f8adcb771abb02f3d26c35570ae82ed5d98b7c8a1923d11b78",
    "33766ba5ed764cf6baaba43a389c8fd4b140d6a80c8bab402eed8e6645752978",
    "31fd53ad08f76a80d005f2e70e3b9229fbd0cf74d440a825ca3fa7929d0fddf1",
)
LEGACY_REFERENCE_COMMAND_HASHES = (
    "8fc16079de526748ee2afa9c05065424db803eb795b4e1a8de3d4bf287cf540b",
    "ef154428c6789014017d370a20e365e14e0bc39aff808d1a331ebd00ff2dc7b9",
    "baed1259159f81543ec2ae31b625787822edd59a38f320efce7694d48272ed6a",
)
LEGACY_SCIENTIFIC_RESULT_HASHES = (
    "af3f2f3e59940a3dc845ca37ccee4cf59290ad881e04a421594b5c9781664706",
    "284b38bdcbc6d98075ccb0992fad12c9809afac8210dff9e3b334f39092eb573",
    "38497df0c6d03ffaf165d7b508bd2208c888694a36ac9bb86ffff90ea867b1cc",
)


def _digest(value) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@pytest.mark.parametrize("crew_index", range(3))
def test_original_sleep_and_activity_inputs_and_commands_are_unchanged(crew_index: int) -> None:
    crew = build_plan()[crew_index]
    records = [
        item.model_dump(mode="json")
        for item in crew.measurements
        if item.metric in LEGACY_SCENARIO_METRICS
    ]
    commands = [item.command.model_dump(mode="json") for item in crew.evaluations]
    references = [
        item.model_dump(mode="json")
        for item in crew.baselines
        if item.metric in LEGACY_SCENARIO_METRICS
    ]
    assert len(records) == (104, 87, 70)[crew_index]
    assert _digest(records) == LEGACY_INPUT_HASHES[crew_index]
    assert _digest(commands) == LEGACY_COMMAND_HASHES[crew_index]
    assert _digest(references) == LEGACY_REFERENCE_COMMAND_HASHES[crew_index]


def test_dashboard_records_cover_the_authored_timeline_and_preserve_gaps() -> None:
    plan = build_plan()
    assert set(DASHBOARD_METRICS) == NEW_METRICS
    assert len(METRICS) == 12
    assert [len(crew.measurements) for crew in plan] == [328, 311, 254]
    for index, crew in enumerate(plan):
        assert {item.metric for item in crew.baselines} == set(METRICS)
        expected_dates = {
            (REFERENCE_START + day * fixtures.DAY).date()
            for day in range(28)
            if not (index == 2 and day >= 14 and day % 14 in (2, 6, 10, 11, 12))
        }
        for metric in NEW_METRICS:
            records = [item for item in crew.measurements if item.metric == metric]
            assert len(records) == len(expected_dates)
            assert {item.measured_at.date() for item in records} == expected_dates
            assert len({item.measurement_id for item in records}) == len(records)
            for record in records:
                assert record.value > 0
                assert record.source == MeasurementSource.SIMULATED
                assert record.unit == METRIC_CATALOG[metric].unit
                assert record.data_quality is None
                assert record.measurement_id.startswith(crew.crew_member_id)


def test_acquisition_context_supports_resting_labels_and_pairs_cuff_readings() -> None:
    expected_minutes = {
        MetricType.HEART_RATE: 7 * 60 + 5,
        MetricType.RESPIRATORY_RATE: 7 * 60 + 5,
        MetricType.BLOOD_OXYGEN_SATURATION: 7 * 60 + 5,
        MetricType.HEART_RATE_VARIABILITY_RMSSD: 7 * 60,
        MetricType.SYSTOLIC_BLOOD_PRESSURE: 7 * 60 + 10,
        MetricType.DIASTOLIC_BLOOD_PRESSURE: 7 * 60 + 10,
        MetricType.BODY_TEMPERATURE: 7 * 60 + 10,
        MetricType.BODY_MASS: 7 * 60 + 15,
    }
    for crew in build_plan():
        records = [item for item in crew.measurements if item.metric in expected_minutes]
        for item in records:
            assert item.metric in ACQUISITION_PROTOCOLS
            assert item.device_id == acquisition_device_id(crew.crew_member_id, item.metric)
            assert item.device_id != f"{crew.crew_member_id}:simulated-device"
            assert (
                item.measured_at.hour * 60 + item.measured_at.minute
                == expected_minutes[item.metric]
            )
            if item.metric == MetricType.HEART_RATE_VARIABILITY_RMSSD:
                assert item.interval_end == item.measured_at + timedelta(minutes=5)
            else:
                assert item.interval_end is None
        systolic = {
            item.measured_at: item
            for item in records
            if item.metric == MetricType.SYSTOLIC_BLOOD_PRESSURE
        }
        diastolic = {
            item.measured_at: item
            for item in records
            if item.metric == MetricType.DIASTOLIC_BLOOD_PRESSURE
        }
        assert systolic.keys() == diastolic.keys()
        for instant, high in systolic.items():
            low = diastolic[instant]
            assert high.device_id == low.device_id
            assert high.interval_end == low.interval_end
            assert high.source == low.source
            assert high.value > low.value


def test_http_records_baselines_and_original_scientific_results(api_client: TestClient) -> None:
    report = seed_api(TestApi(api_client), batch_size=37)
    assert report["all_checks_passed"] is True
    assert sum(item["stored_measurement_count"] for item in report["crews"]) == 893
    assert sum(len(item["baselines"]) for item in report["crews"]) == 36
    assert sum(len(item["evaluations"]) for item in report["crews"]) == 13
    for index, crew in enumerate(build_plan()):
        root = f"/api/v1/crew-members/{crew.crew_member_id}"
        response = api_client.get(root + "/measurements")
        assert response.status_code == 200
        stored = {
            item["measurement_id"]: PhysiologicalMeasurement.model_validate(item)
            for item in response.json()["items"]
        }
        assert stored.keys() == {item.measurement_id for item in crew.measurements}
        for item in crew.measurements:
            assert stored[item.measurement_id].model_dump(exclude={"data_quality"}) == (
                item.model_dump(exclude={"data_quality"})
            )
        for metric in NEW_METRICS:
            expected = {
                item.measurement_id: item for item in crew.measurements if item.metric == metric
            }
            response = api_client.get(root + "/measurements", params={"metric": metric.value})
            assert response.status_code == 200
            actual = [
                PhysiologicalMeasurement.model_validate(item) for item in response.json()["items"]
            ]
            assert {item.measurement_id for item in actual} == expected.keys()
            for item in actual:
                assert item.model_dump(exclude={"data_quality"}) == expected[
                    item.measurement_id
                ].model_dump(exclude={"data_quality"})
                assert item.data_quality is not None
                assert item.data_quality.algorithm.name == "data_quality"
                assert item.data_quality.status == QualityStatus.ACCEPTABLE
                assert item.data_quality.completeness is None
                assert item.data_quality.score is None
            response = api_client.get(root + "/baselines", params={"metric": metric.value})
            assert response.status_code == 200
            assert len(response.json()["items"]) == 1
            baseline = PersonalBaseline.model_validate(response.json()["items"][0])
            reference = [
                item.value for item in expected.values() if item.measured_at < CURRENT_START
            ]
            assert baseline.metric == metric
            assert baseline.unit == METRIC_CATALOG[metric].unit
            assert baseline.algorithm.name == "personal_baseline"
            assert baseline.status.value == "established"
            assert baseline.sample_count == len(reference) == 14
            assert baseline.statistics.median == median(reference)
            assert baseline.statistics.minimum == min(reference)
            assert baseline.statistics.maximum == max(reference)
        # Existing evaluation IDs incorporate all crew history, so additions change
        # identities while the domain calculations and every other field remain exact.
        results = [
            {key: value for key, value in item["result"].items() if key != "evaluation_id"}
            for item in report["crews"][index]["evaluations"]
        ]
        assert _digest(results) == LEGACY_SCIENTIFIC_RESULT_HASHES[index]
    assert report["crews"][2]["quality_status_counts"]["unusable"] == 7


def test_legacy_generic_acquisition_fails_before_any_seed_write(api_client: TestClient) -> None:
    crew = build_plan()[0]
    original = next(item for item in crew.measurements if item.metric == MetricType.HEART_RATE)
    legacy = original.model_copy(
        update={
            "measured_at": original.measured_at.replace(hour=8, minute=0),
            "device_id": f"{crew.crew_member_id}:simulated-device",
        }
    )
    response = api_client.post(
        "/api/v1/measurements", json={"measurements": [legacy.model_dump(mode="json")]}
    )
    assert response.is_success
    api = TestApi(api_client)
    with pytest.raises(SeedError, match="unexpected/conflicting"):
        seed_api(api)
    assert all(method == "GET" for method, _ in api.calls)
    stored = api_client.get(f"/api/v1/crew-members/{crew.crew_member_id}/measurements").json()[
        "items"
    ]
    assert len(stored) == 1
    assert stored[0]["device_id"] == legacy.device_id
    assert PhysiologicalMeasurement.model_validate(stored[0]).measured_at == legacy.measured_at


@pytest.mark.parametrize("metric", sorted(NEW_METRICS))
def test_new_metric_value_conflicts_fail_before_any_seed_write(
    api_client: TestClient, metric: MetricType
) -> None:
    original = next(item for item in build_plan()[0].measurements if item.metric == metric)
    conflicting = original.model_copy(update={"value": original.value + 1})
    response = api_client.post(
        "/api/v1/measurements", json={"measurements": [conflicting.model_dump(mode="json")]}
    )
    assert response.is_success
    api = TestApi(api_client)
    with pytest.raises(SeedError, match="unexpected/conflicting"):
        seed_api(api)
    assert all(method == "GET" for method, _ in api.calls)


def test_inverted_synthetic_pressure_pair_is_preserved_and_unusable(api_client: TestClient) -> None:
    crew = build_plan()[0]
    selected = [
        next(item for item in crew.measurements if item.metric == metric)
        for metric in (MetricType.SYSTOLIC_BLOOD_PRESSURE, MetricType.DIASTOLIC_BLOOD_PRESSURE)
    ]
    inverted = [
        item.model_copy(update={"value": value})
        for item, value in zip(selected, (75, 90), strict=True)
    ]
    response = api_client.post(
        "/api/v1/measurements",
        json={"measurements": [item.model_dump(mode="json") for item in inverted]},
    )
    assert response.is_success
    response = api_client.get(f"/api/v1/crew-members/{crew.crew_member_id}/measurements")
    assert response.status_code == 200
    actual = {
        item["measurement_id"]: PhysiologicalMeasurement.model_validate(item)
        for item in response.json()["items"]
    }
    assert len(actual) == 2
    for original in inverted:
        item = actual[original.measurement_id]
        assert item.model_dump(exclude={"data_quality"}) == original.model_dump(
            exclude={"data_quality"}
        )
        assert item.unit == "mmHg"
        assert item.data_quality is not None
        assert item.data_quality.status == QualityStatus.UNUSABLE
        assert QualityFlag.SIGNAL_ARTIFACT in item.data_quality.flags
        assert item.data_quality.algorithm.name == "data_quality"
