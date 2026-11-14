"""Mission-aware baseline computation, daily aggregation semantics and safe retrieval."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.models import PersonalBaseline
from tests.api.builders import (
    PREFIX,
    START,
    activity_options,
    activity_records,
    baseline_command,
    simulated_measurement,
)
from tests.support import load_schema


def test_baseline_generation_uses_validated_history_and_is_provisional_by_default(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["algorithm"]["name"] == "personal_baseline"
    assert value["sample_count"] == 3
    assert value["statistics"]["mean"] == 30
    assert value["statistics"]["standard_deviation"] == 10
    assert value["status"] == "provisional"
    assert "measurement" in value["data_quality"]["notes"]
    PersonalBaseline.model_validate(value)
    Draft202012Validator(load_schema("personal_baseline")).validate(value)
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json() == {"items": [value]}


def test_explicit_sourced_criteria_can_establish_a_baseline(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    command = baseline_command("exercise_duration")
    command["config"] = {
        "established_min_samples": 3,
        "policy_source": "SIMULATED integration-test policy",
    }
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "established"
    assert "SIMULATED integration-test policy" in response.json()["data_quality"]["notes"]
    repeated = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert repeated.json() == response.json()
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json()["items"]) == 1


@pytest.mark.parametrize(
    "config",
    [
        {"established_min_samples": 3},
        {"established_min_span": "P2D", "policy_source": " "},
        {"minimum_samples": 1},
        {"minimum_samples": 4, "established_min_samples": 3, "policy_source": "sim"},
        {"outlier_cutoff": 0},
        {"unknown": 10},
    ],
)
def test_invalid_or_unsourced_baseline_settings_are_422(
    api_client: TestClient, config: dict
) -> None:
    command = {**baseline_command(), "config": config}
    assert (
        api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).status_code
        == 422
    )


def test_quality_failures_are_excluded_from_baseline_statistics(api_client: TestClient) -> None:
    records = activity_records([20, 30, 40])
    records.append(
        simulated_measurement("sim-invalid", value=-100, instant=START + timedelta(hours=12))
    )
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    assert response.status_code == 201
    assert response.json()["statistics"]["mean"] == 30
    assert response.json()["sample_count"] == 3
    assert "Records not admitted" in response.json()["data_quality"]["notes"]


def test_empty_history_returns_an_explained_insufficient_baseline(api_client: TestClient) -> None:
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-empty/baselines", json=baseline_command()
    )
    assert response.status_code == 201
    assert response.json()["status"] == "insufficient_data"
    assert response.json()["sample_count"] == 0
    assert all(value is None for value in response.json()["statistics"].values())
    assert response.json()["data_quality"]["notes"]


@pytest.mark.parametrize(
    "kind", ["overlap", "different_missions", "wrong_phase", "duplicate_id", "future"]
)
def test_ambiguous_or_unavailable_mission_context_is_422(api_client: TestClient, kind: str) -> None:
    command = baseline_command()
    phase = command["mission_phases"][0]
    if kind == "overlap":
        command["mission_phases"].append(
            {**phase, "phase_id": "sim-other", "start_time": START.isoformat()}
        )
    elif kind == "different_missions":
        phase["end_time"] = "2026-10-10T00:00:00Z"
        command["mission_phases"].append(
            {
                **phase,
                "phase_id": "sim-other",
                "mission_id": "sim-other",
                "start_time": START.isoformat(),
                "end_time": None,
            }
        )
    elif kind == "wrong_phase":
        command["mission_phase"] = "pre_flight"
    elif kind == "duplicate_id":
        command["mission_phases"].append(dict(phase))
    else:
        command["computed_at"] = "2027-01-01T00:00:00Z"
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_baseline_reference_does_not_pool_measurements_across_phases(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    command = baseline_command("exercise_duration")
    command["mission_phases"][0]["end_time"] = (START + timedelta(days=2)).isoformat()
    command["mission_phases"].append(
        {
            "phase_id": "sim-return",
            "mission_id": "sim-mission",
            "phase": "return_to_earth",
            "start_time": (START + timedelta(days=2)).isoformat(),
        }
    )
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).json()
    assert value["sample_count"] == 2
    assert value["statistics"]["mean"] == 25


def test_daily_activity_baselines_sum_sessions_before_calling_the_real_engine(
    api_client: TestClient,
) -> None:
    records = [
        simulated_measurement(
            f"sim-{day}-{hour}",
            value=reading,
            instant=START + timedelta(days=day, hours=hour),
            interval_end=(START + timedelta(days=day, hours=hour, minutes=30)).isoformat(),
        )
        for day, reading in enumerate([10, 15, 20])
        for hour in (9, 10)
    ]
    api_client.post(f"{PREFIX}/measurements", json={"measurements": records})
    command = {
        **baseline_command("exercise_duration"),
        "aggregation": "complete_active_day_total",
        "activity": activity_options(),
        "config": {"established_min_samples": 3, "policy_source": "SIMULATED test criterion"},
    }
    response = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command)
    assert response.status_code == 201, response.text
    value = response.json()
    assert value["sample_count"] == 3
    assert value["statistics"]["mean"] == 30  # Daily totals [20, 30, 40], not six session values.
    assert value["status"] == "established"
    assert "transient" in value["data_quality"]["notes"]
    assert len(api_client.get(f"{PREFIX}/crew-members/sim-crew/measurements").json()["items"]) == 6


def test_missing_daily_coverage_is_not_silently_promoted_to_an_established_reference(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    command = {**baseline_command("exercise_duration"), "aggregation": "complete_active_day_total"}
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).json()
    assert value["status"] == "insufficient_data"
    assert value["sample_count"] == 0
    assert "missing_data" in value["data_quality"]["flags"]


def test_missing_reference_days_remain_visible_even_when_sample_criteria_pass(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    options = activity_options()
    options["coverage"] = [
        item for item in options["coverage"] if item["day"] != START.date().isoformat()
    ]
    command = {
        **baseline_command("exercise_duration"),
        "aggregation": "complete_active_day_total",
        "activity": options,
        "config": {"established_min_samples": 2, "policy_source": "SIMULATED test criterion"},
    }
    value = api_client.post(f"{PREFIX}/crew-members/sim-crew/baselines", json=command).json()
    assert value["sample_count"] == 2
    assert value["data_quality"]["status"] == "degraded"
    assert value["data_quality"]["completeness"] == pytest.approx(2 / 3)


def test_crew_baselines_and_filters_are_isolated(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    assert api_client.get(f"{PREFIX}/crew-members/other/baselines").json() == {"items": []}
    assert api_client.get(
        f"{PREFIX}/crew-members/sim-crew/baselines", params={"metric": "sleep_duration"}
    ).json() == {"items": []}
    assert api_client.get(
        f"{PREFIX}/crew-members/sim-crew/baselines", params={"mission_phase": "pre_flight"}
    ).json() == {"items": []}


def test_backfill_invalidates_affected_baselines_without_deleting_other_crew_data(
    api_client: TestClient,
) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    api_client.post(
        f"{PREFIX}/crew-members/other/baselines", json=baseline_command("exercise_duration")
    )
    backfill = simulated_measurement("sim-backfill", instant=START + timedelta(hours=12))
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [backfill]})
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json() == {"items": []}
    assert len(api_client.get(f"{PREFIX}/crew-members/other/baselines").json()["items"]) == 1


def test_new_data_after_reference_window_preserves_prior_baselines(api_client: TestClient) -> None:
    api_client.post(f"{PREFIX}/measurements", json={"measurements": activity_records([20, 30, 40])})
    response = api_client.post(
        f"{PREFIX}/crew-members/sim-crew/baselines", json=baseline_command("exercise_duration")
    )
    later = simulated_measurement("sim-later", instant=START + timedelta(days=5))
    api_client.post(f"{PREFIX}/measurements", json={"measurements": [later]})
    assert api_client.get(f"{PREFIX}/crew-members/sim-crew/baselines").json() == {
        "items": [response.json()]
    }
