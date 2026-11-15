"""Seed a fresh API with the observations of the approved frontend scenario.

The observations in `approved_observations.json` are exported, unchanged, from the
frontend's synthetic generators (`integrations/approved-demo/export_observations.mjs`).
They are SIMULATED data, never astronaut records.

Only observations are authored here. Data quality is assessed by the backend on
ingestion, and personal baselines are computed by the backend Personal Baseline engine.
No evaluation, flag or band is copied from the interface.

    python -m app.demo_seed.approved --base-url http://127.0.0.1:8000/api/v1
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.demo_seed.client import HttpApi, SeedError
from app.models import (
    EvaluationResult,
    HealthDomain,
    MissionPhase,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)
from app.scenarios import fixtures
from app.scenarios.models import SIMULATION_NOTICE
from app.services.commands import (
    BaselineCommand,
    BaselineOptions,
    EvaluationCommand,
    Items,
    MeasurementBatch,
)

FIXTURE = Path(__file__).with_name("approved_observations.json")
CREW = ("sim-mission-v1-01", "sim-mission-v1-02", "sim-mission-v1-03")
SLEEP = {"sleep_duration", "sleep_efficiency"}
# Measurement-level metrics whose baseline the engine computes. Activity totals need
# day plans (complete_active_day_total) that the approved scenario does not define, so the
# interface labels their band as computed in the interface.
BASELINE_METRICS = (
    "heart_rate",
    "heart_rate_variability_rmssd",
    "respiratory_rate",
    "blood_oxygen_saturation",
    "body_temperature",
    "systolic_blood_pressure",
    "diastolic_blood_pressure",
    "sleep_duration",
    "sleep_efficiency",
    "body_mass",
)
# Reference window = mission days 1-7, the baseline window of the approved interface
# (frontend/src/data/mock/daily.ts). Sleep belongs to the night that ends on the day.
DAY1 = datetime(2026, 10, 31, tzinfo=UTC)
REFERENCE = {
    "default": (DAY1, datetime(2026, 11, 7, tzinfo=UTC)),
    "sleep": (datetime(2026, 10, 30, 12, tzinfo=UTC), datetime(2026, 11, 6, 12, tzinfo=UTC)),
}
COMPUTED_AT = datetime(2026, 11, 7, 12, tzinfo=UTC)
# Nights ending on mission days 8-15 (2026-11-07 .. 2026-11-14).
SLEEP_WINDOW = (datetime(2026, 11, 6, 12, tzinfo=UTC), datetime(2026, 11, 14, 12, tzinfo=UTC))
# SIMULATED establishment policy, taken from the approved interface's own rule: at least
# five readings in mission days 1-7 (`baselineOf`, frontend/src/data/mock/daily.ts); five
# daily readings span at least four days. A presentation choice for this synthetic demo,
# not a validated or clinical rule.
ESTABLISHED_MIN_SAMPLES = 5
ESTABLISHED_MIN_SPAN = timedelta(days=4)


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def seed(api: HttpApi, batch_size: int = 1000) -> dict:
    data = load_fixture()
    for crew in CREW:
        existing = api.request("GET", f"/crew-members/{crew}/measurements")
        if existing.get("items"):
            raise SeedError(f"{crew} already has measurements; use a fresh local API process.")
    records = [PhysiologicalMeasurement.model_validate(m) for m in data["measurements"]]
    for offset in range(0, len(records), batch_size):
        batch = MeasurementBatch(measurements=records[offset : offset + batch_size])
        response = Items[PhysiologicalMeasurement].model_validate(
            api.request("POST", "/measurements", batch.model_dump(mode="json"))
        )
        original = {m.measurement_id: m for m in batch.measurements}
        for item in response.items:
            if item.model_dump(exclude={"data_quality"}) != original[
                item.measurement_id
            ].model_dump(exclude={"data_quality"}):
                raise SeedError("Ingestion changed an authored observation")
    phase = MissionPhase(
        phase_id="approved-demo-in-flight",
        mission_id="approved-demo",
        phase=MissionPhaseType.IN_FLIGHT,
        start_time=REFERENCE["sleep"][0],
        end_time=datetime(2026, 11, 15, tzinfo=UTC),
        label="SIMULATED mission timeline of the approved frontend scenario",
    )
    report: dict = {"dataset": data["dataset"], "notice": SIMULATION_NOTICE, "crews": {}}
    for crew in CREW:
        statuses = {}
        created: dict[str, PersonalBaseline] = {}
        for metric in BASELINE_METRICS:
            start, end = REFERENCE["sleep" if metric in SLEEP else "default"]
            command = BaselineCommand(
                metric=metric,
                mission_phase=MissionPhaseType.IN_FLIGHT,
                mission_phases=(phase,),
                reference_start=start,
                reference_end=end,
                computed_at=COMPUTED_AT,
                aggregation="measurement",
                config=BaselineOptions(
                    established_min_samples=ESTABLISHED_MIN_SAMPLES,
                    established_min_span=ESTABLISHED_MIN_SPAN,
                    policy_source=(
                        "SIMULATED: approved interface baseline window, mission days 1-7 "
                        "(frontend/src/data/mock/daily.ts); not clinical validation"
                    ),
                ),
            )
            try:
                value = PersonalBaseline.model_validate(
                    api.request(
                        "POST", f"/crew-members/{crew}/baselines", command.model_dump(mode="json")
                    )
                )
                statuses[metric] = value.status.value
                created[metric] = value
            except SeedError as error:
                statuses[metric] = f"not computed: {error}"
        # Sleep screening by the backend sleep engine: nights of mission days 8-15 against
        # the days 1-7 baseline, with the documented SIMULATED fixture policy of the
        # official seed. The resulting status is whatever the engine computes.
        evaluation = None
        sleep_ids = tuple(created[m].baseline_id for m in fixtures.SLEEP_METRICS if m in created)
        if len(sleep_ids) == len(fixtures.SLEEP_METRICS):
            command = EvaluationCommand(
                domain=HealthDomain.SLEEP,
                window_start=SLEEP_WINDOW[0],
                window_end=SLEEP_WINDOW[1],
                evaluated_at=SLEEP_WINDOW[1],
                mission_phase=MissionPhaseType.IN_FLIGHT,
                sleep_config=fixtures.sleep_policy(),
                baseline_ids=sleep_ids,
            )
            try:
                result = EvaluationResult.model_validate(
                    api.request(
                        "POST", f"/crew-members/{crew}/evaluations", command.model_dump(mode="json")
                    )
                )
                evaluation = result.status.value
            except SeedError as error:
                evaluation = f"not computed: {error}"
        report["crews"][crew] = {
            "measurements": sum(1 for m in records if m.crew_member_id == crew),
            "baselines": statuses,
            "sleep_evaluation_days_8_15": evaluation,
        }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args(argv)
    print(json.dumps(seed(HttpApi(args.base_url)), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
