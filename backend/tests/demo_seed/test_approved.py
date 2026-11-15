"""The approved-frontend observations: simulated, valid and unchanged from the export."""

from app.demo_seed.approved import CREW, load_fixture
from app.models import PhysiologicalMeasurement


def test_fixture_is_simulated_valid_and_unique() -> None:
    data = load_fixture()
    ids = [m["measurement_id"] for m in data["measurements"]]

    assert "SIMULATED" in data["notice"]
    assert len(ids) == len(set(ids))
    for record in data["measurements"]:
        assert record["source"] == "simulated"
        assert record["crew_member_id"] in CREW
        PhysiologicalMeasurement.model_validate(record)


def test_fixture_matches_the_approved_daily_values() -> None:
    data = load_fixture()
    by_id = {m["measurement_id"]: m for m in data["measurements"]}
    crew_a = data["daily_reference"]["sim-mission-v1-01"]

    assert data["generator"]["now"] == "2026-11-14T10:40:00Z"
    assert data["generator"]["mission_start"] == "2026-10-31"
    day15 = {k: next(d for d in v if d["mission_day"] == 15)["value"] for k, v in crew_a.items()}
    assert (day15["resting_hr"], day15["hrv_rmssd"], day15["sleep_duration"]) == (65, 47, 6)
    assert by_id["approved-sim-mission-v1-01-resting_hr-2026-11-14"]["value"] == 65
    assert by_id["approved-sim-mission-v1-01-sleep_duration-2026-11-14"]["value"] == 360
    for crew, series in data["daily_reference"].items():
        for indicator, days in series.items():
            for day in days:
                key = f"approved-{crew}-{indicator}-{day['date']}"
                present = day["value"] is not None and day["quality"] != "missing"
                assert (key in by_id) == present
