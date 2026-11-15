"""Deterministic synthetic histories and commands, never precomputed scientific outputs.

Fixture reuse and every additional authored value/convention are documented in
docs/mission-demo-seed.md. No value or policy is a clinical recommendation.
"""

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from app.demo_seed.acquisition import (
    ACQUISITION_PROTOCOLS,
    DASHBOARD_METRICS,
    LEGACY_VITAL_METRICS,
    MISSING_CURRENT_VITAL_DAYS,
    SEED_REVISION,
    acquisition_device_id,
)
from app.domains.physical_activity import ActivityDayPlan, ExerciseSession, RecordingCoverage
from app.models import (
    HealthDomain,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PhysiologicalMeasurement,
)
from app.scenarios import fixtures
from app.scenarios.codec import canonical_json
from app.scenarios.models import SIMULATION_NOTICE
from app.services.commands import (
    ActivityOptions,
    BaselineCommand,
    BaselineOptions,
    EvaluationCommand,
)

DATASET_ID = "orbitvitals-mission-demo-v1"
REFERENCE_START = datetime(2026, 9, 28, tzinfo=UTC)
CURRENT_START = REFERENCE_START + 14 * fixtures.DAY
COMPUTED_AT = CURRENT_START + timedelta(hours=12)
FINAL_AS_OF = CURRENT_START + 14 * fixtures.DAY + timedelta(hours=12)
VITAL_METRICS = (
    *LEGACY_VITAL_METRICS,
    *(metric for metric in DASHBOARD_METRICS if metric != MetricType.BODY_MASS),
)
METRICS = (
    *fixtures.SLEEP_METRICS,
    *fixtures.ACTIVITY_METRICS,
    *VITAL_METRICS,
    MetricType.BODY_MASS,
)


@dataclass(frozen=True)
class EvaluationSpec:
    checkpoint: str
    command: EvaluationCommand
    baseline_metrics: tuple[MetricType, ...]
    expected_status: str
    demonstration_behavior: str


@dataclass(frozen=True)
class CrewPlan:
    crew_member_id: str
    display_name: str
    scenario: str
    description: str
    reused_fixtures: tuple[str, ...]
    measurements: tuple[PhysiologicalMeasurement, ...]
    baselines: tuple[BaselineCommand, ...]
    evaluations: tuple[EvaluationSpec, ...]


def _remap(
    records: tuple[PhysiologicalMeasurement, ...], crew: str, label: str, shift: timedelta
) -> tuple[PhysiologicalMeasurement, ...]:
    return tuple(
        record.model_copy(
            update={
                "measurement_id": f"{crew}:{label}:{record.measurement_id}",
                "crew_member_id": crew,
                "device_id": f"{crew}:simulated-device",
                "measured_at": record.measured_at + shift,
                "interval_end": record.interval_end + shift if record.interval_end else None,
            }
        )
        for record in records
    )


def _activity_cycle(crew: str, start: datetime, label: str) -> tuple[tuple, ActivityOptions]:
    # Independently authored duration/energy cycles; no energy estimate is derived.
    minutes = (50, 55, 50, 55, 50, 0, 55) * 2
    energy = (220, 250, 230, 260, 240, 0, 250) * 2
    records, sessions, coverage, plans = [], [], [], []
    for day, (duration, kcal) in enumerate(zip(minutes, energy, strict=True)):
        instant = start + day * fixtures.DAY + timedelta(hours=9)
        rest = day in (5, 12)
        if rest:
            plans.append(
                ActivityDayPlan(
                    day=instant.date(), planned_rest=True, notes="SIMULATED scheduled recovery day."
                )
            )
        links = []
        for metric, value in zip(fixtures.ACTIVITY_METRICS, (duration, kcal), strict=True):
            coverage.append(
                RecordingCoverage(
                    day=instant.date(),
                    metric=metric,
                    complete=True,
                    notes="SIMULATED complete recording confirmation.",
                )
            )
            if rest:
                continue
            record = fixtures.simulated_measurement(
                f"sim-{label}-{day:02d}-{metric.value}",
                metric,
                value,
                instant,
                interval_end=instant + timedelta(hours=1),
            )
            record = _remap((record,), crew, label, timedelta(0))[0]
            records.append(record)
            links.append(record.measurement_id)
        if links:
            sessions.append(
                ExerciseSession(
                    session_id=f"{crew}:{label}:sim-session-{day:02d}",
                    start_time=instant,
                    end_time=instant + timedelta(hours=1),
                    measurement_ids=tuple(links),
                    label="SIMULATED exercise session",
                )
            )
    return tuple(records), ActivityOptions(
        sessions=tuple(sessions),
        coverage=tuple(coverage),
        day_plans=tuple(plans),
        policies=fixtures.activity_inputs()[4],
        context_notes="SIMULATED complete additive recording and explicit personal plan.",
    )


def _declining_activity(crew: str) -> tuple[tuple, ActivityOptions]:
    records, sessions, coverage, plans, policies = fixtures.activity_inputs()
    shift = CURRENT_START - fixtures.ACTIVITY_START
    mapped = _remap(records, crew, "current", shift)
    ids = {old.measurement_id: new.measurement_id for old, new in zip(records, mapped, strict=True)}
    return mapped, ActivityOptions(
        sessions=tuple(
            item.model_copy(
                update={
                    "session_id": f"{crew}:{item.session_id}",
                    "start_time": item.start_time + shift,
                    "end_time": item.end_time + shift,
                    "measurement_ids": tuple(
                        ids[identifier] for identifier in item.measurement_ids
                    ),
                }
            )
            for item in sessions
        ),
        coverage=tuple(item.model_copy(update={"day": item.day + shift}) for item in coverage),
        day_plans=tuple(item.model_copy(update={"day": item.day + shift}) for item in plans),
        policies=policies,
        context_notes="SIMULATED declining adherence, planned rest, partial and missing records.",
    )


def _unconfirmed_activity(crew: str) -> tuple[tuple, ActivityOptions]:
    records = tuple(
        fixtures.simulated_measurement(
            f"sim-telemetry-{offset}-{metric.value}",
            metric,
            value,
            CURRENT_START + offset * fixtures.DAY + timedelta(hours=9),
            interval_end=CURRENT_START + offset * fixtures.DAY + timedelta(hours=10),
        )
        for offset, metric, value in (
            (0, MetricType.EXERCISE_DURATION, 30),
            (6, MetricType.EXERCISE_DURATION, -10),
            (6, MetricType.ACTIVE_ENERGY_EXPENDITURE, -50),
        )
    )
    return _remap(records, crew, "current", timedelta(0)), ActivityOptions(
        policies=fixtures.activity_inputs()[4],
        context_notes="SIMULATED telemetry failures; complete recording is never confirmed.",
    )


def _vitals(crew: str, index: int) -> tuple[PhysiologicalMeasurement, ...]:
    raw, phases = fixtures.baseline_inputs()
    pre = next(phase for phase in phases if phase.phase == MissionPhaseType.PRE_FLIGHT)
    flight = next(phase for phase in phases if phase.phase == MissionPhaseType.IN_FLIGHT)
    reference = tuple(
        item.value for item in raw if pre.start_time <= item.measured_at < pre.end_time
    )
    shifted = tuple(
        item.value for item in raw if flight.start_time <= item.measured_at < flight.end_time
    )
    records = []
    for day in range(28):
        current = day >= 14
        offset = day % 14
        if index == 2 and current and offset in MISSING_CURRENT_VITAL_DAYS:
            continue
        heart = (shifted if current and index else reference)[offset]
        if heart < 0 and index != 2:
            heart = 64  # Replace the fixture's corruption only in the non-failure profile.
        if heart >= 0:
            heart += index * 4
        respiratory = (12, 13, 14, 13, 12, 14, 13)[day % 7] + index
        oxygen = (98, 97, 99, 98, 97, 99, 98)[day % 7]
        if index == 2 and current and offset == 4:
            oxygen = 125  # Explicit percentage-decoder failure, not a clinical deviation.
        for metric, value in zip(LEGACY_VITAL_METRICS, (heart, respiratory, oxygen), strict=True):
            records.append(
                fixtures.simulated_measurement(
                    f"sim-vitals-{day:02d}-{metric.value}",
                    metric,
                    value,
                    REFERENCE_START + day * fixtures.DAY + timedelta(hours=7, minutes=5),
                )
            )
    # New generation explicitly declares acquisition; old stored generic records
    # are never relabeled. Preflight rejects their differing timestamps/devices.
    return tuple(
        record.model_copy(update={"device_id": acquisition_device_id(crew, record.metric)})
        for record in _remap(tuple(records), crew, "vitals", timedelta(0))
    )


def _dashboard_measurements(crew: str, index: int) -> tuple[PhysiologicalMeasurement, ...]:
    """Author scalar inputs without deriving physiological findings or thresholds."""
    records = []
    for day in range(28):
        current, offset = day >= 14, day % 14
        if index == 2 and current and offset in MISSING_CURRENT_VITAL_DAYS:
            continue
        step = offset if current and index == 1 else 0
        values = (
            (54, 56, 55, 57, 53, 58, 55)[day % 7] - 4 * index - 0.5 * step,
            (116, 118, 117, 119, 115, 120, 117)[day % 7] + 3 * index + step // 4,
            (74, 75, 73, 76, 74, 77, 75)[day % 7] + 2 * index + step // 6,
            (36.6, 36.7, 36.5, 36.6, 36.8, 36.7, 36.6)[day % 7],
            (72.0, 72.1, 71.9, 72.2, 72.0, 71.8, 72.1)[day % 7] + 4 * index,
        )
        for metric, value in zip(DASHBOARD_METRICS, values, strict=True):
            protocol = ACQUISITION_PROTOCOLS[metric]
            instant = (
                REFERENCE_START + day * fixtures.DAY + timedelta(minutes=protocol["minute_of_day"])
            )
            interval = protocol["interval_minutes"]
            record = fixtures.simulated_measurement(
                f"sim-dashboard-{day:02d}-{metric.value}",
                metric,
                round(value, 2),
                instant,
                interval_end=instant + timedelta(minutes=interval) if interval else None,
            )
            mapped = _remap((record,), crew, "dashboard", timedelta(0))[0]
            records.append(
                mapped.model_copy(update={"device_id": acquisition_device_id(crew, metric)})
            )
    return tuple(records)


def _options_through(options: ActivityOptions, end: datetime) -> ActivityOptions:
    return options.model_copy(
        update={
            "sessions": tuple(item for item in options.sessions if item.start_time < end),
            "coverage": tuple(item for item in options.coverage if item.day < end.date()),
            "day_plans": tuple(item for item in options.day_plans if item.day < end.date()),
        }
    )


def build_plan() -> tuple[CrewPlan, ...]:
    """Build fresh plan containers with validated existing API command models."""
    crews = []
    for index, (name, scenario, description) in enumerate(
        (
            (
                "SIMULATED Vega",
                "stable_monitoring",
                "Variable reference history and stable recorded activity/sleep; no health claim.",
            ),
            (
                "SIMULATED Noor",
                "declining_sleep_and_activity",
                "Progressive sleep restriction, declining activity and explicit recording gaps.",
            ),
            (
                "SIMULATED Chen",
                "sensor_failures_and_missing_data",
                "Corrupt and duplicate sleep records, vital decoder failures, "
                "and unconfirmed activity.",
            ),
        )
    ):
        crew = f"sim-mission-v1-{index + 1:02d}"
        reference_sleep = _remap(
            fixtures.sleep_records(
                "reference",
                (475, 480, 485, 480, 475, 485, 480) * 2,
                (91, 92, 93, 92, 91, 93, 92) * 2,
            ),
            crew,
            "reference",
            REFERENCE_START + timedelta(hours=12) - fixtures.SLEEP_START,
        )
        reference_activity, reference_options = _activity_cycle(crew, REFERENCE_START, "reference")
        if index == 0:
            current_sleep = fixtures.sleep_records("stable", (480,) * 14, (92,) * 14)
            current_activity, current_options = _activity_cycle(crew, CURRENT_START, "current")
            sleep_steps = ((7, "nominal"), (14, "nominal"))
        elif index == 1:
            current_sleep = fixtures.restriction_records()
            current_activity, current_options = _declining_activity(crew)
            sleep_steps = ((2, "insufficient_data"), (5, "attention"), (9, "attention"))
        else:
            current_sleep = fixtures.sensor_failure_records()
            current_activity, current_options = _unconfirmed_activity(crew)
            sleep_steps = ((7, "nominal"), (14, "insufficient_data"))
        current_sleep = _remap(
            current_sleep,
            crew,
            "current",
            CURRENT_START + timedelta(hours=12) - fixtures.SLEEP_START,
        )
        phase = MissionPhase(
            phase_id="sim-mission-v1-in-flight",
            mission_id="sim-mission-v1",
            phase=MissionPhaseType.IN_FLIGHT,
            start_time=REFERENCE_START,
            end_time=FINAL_AS_OF,
            label="SIMULATED mission timeline; not a NASA mission record",
        )
        policy = fixtures.baseline_policy()
        baselines = tuple(
            BaselineCommand(
                metric=metric,
                mission_phase=MissionPhaseType.IN_FLIGHT,
                mission_phases=(phase,),
                reference_start=REFERENCE_START
                + (timedelta(hours=12) if metric in fixtures.SLEEP_METRICS else timedelta(0)),
                reference_end=CURRENT_START
                + (timedelta(hours=12) if metric in fixtures.SLEEP_METRICS else timedelta(0)),
                computed_at=COMPUTED_AT,
                aggregation="complete_active_day_total"
                if metric in fixtures.ACTIVITY_METRICS
                else "measurement",
                activity=reference_options if metric in fixtures.ACTIVITY_METRICS else None,
                config=BaselineOptions(
                    established_min_samples=policy.established_min_samples,
                    established_min_span=policy.established_min_span,
                    policy_source=(
                        "SIMULATED app.scenarios.fixtures.baseline_policy; "
                        "docs/scientific-scenarios.md; not clinical validation"
                    ),
                ),
            )
            for metric in METRICS
        )
        evaluations = []
        for days, expected in sleep_steps:
            end = CURRENT_START + days * fixtures.DAY + timedelta(hours=12)
            evaluations.append(
                EvaluationSpec(
                    checkpoint=f"sleep-day-{days:02d}",
                    command=EvaluationCommand(
                        domain=HealthDomain.SLEEP,
                        window_start=CURRENT_START + timedelta(hours=12),
                        window_end=end,
                        evaluated_at=end,
                        mission_phase=MissionPhaseType.IN_FLIGHT,
                        sleep_config=fixtures.sleep_policy(),
                    ),
                    baseline_metrics=fixtures.SLEEP_METRICS,
                    expected_status=expected,
                    demonstration_behavior=(
                        "Quality and missing-night limits remain separate "
                        "from statistical sleep screening."
                        if index == 2
                        else "Configured sleep trend screening relative to "
                        "a prior personal reference."
                    ),
                )
            )
        for days in (7, 14):
            end = CURRENT_START + days * fixtures.DAY
            options = _options_through(current_options, end).model_copy(
                update={"baselines_comparable": True}
            )
            evaluations.append(
                EvaluationSpec(
                    checkpoint=f"activity-day-{days:02d}",
                    command=EvaluationCommand(
                        domain=HealthDomain.PHYSICAL_ACTIVITY,
                        window_start=CURRENT_START,
                        window_end=end,
                        evaluated_at=end,
                        mission_phase=MissionPhaseType.IN_FLIGHT,
                        activity=options,
                    ),
                    baseline_metrics=fixtures.ACTIVITY_METRICS,
                    expected_status=("nominal", "attention", "insufficient_data")[index],
                    demonstration_behavior=(
                        "Explicit rest, targets and coverage; "
                        "missing records never imply zero activity."
                    ),
                )
            )
        records = tuple(
            sorted(
                (
                    *reference_sleep,
                    *reference_activity,
                    *current_sleep,
                    *current_activity,
                    *_vitals(crew, index),
                    *_dashboard_measurements(crew, index),
                ),
                key=lambda item: (item.measured_at, item.metric, item.measurement_id),
            )
        )
        crews.append(
            CrewPlan(
                crew,
                name,
                scenario,
                description,
                (
                    "sleep_records",
                    "activity_inputs",
                    "baseline_inputs",
                    "sleep_policy",
                    "baseline_policy",
                    *(
                        ("restriction_records",)
                        if index == 1
                        else ("sensor_failure_records",)
                        if index == 2
                        else ()
                    ),
                ),
                records,
                baselines,
                tuple(evaluations),
            )
        )
    return tuple(crews)


def plan_digest(plan: tuple[CrewPlan, ...]) -> str:
    """Fingerprint inputs, acquisition assumptions, commands and authored expectations."""
    return hashlib.sha256(
        canonical_json(
            {
                "seed_revision": SEED_REVISION,
                "acquisition_protocols": ACQUISITION_PROTOCOLS,
                "crews": [asdict(crew) for crew in plan],
            }
        ).encode("utf-8")
    ).hexdigest()


def build_manifest(plan: tuple[CrewPlan, ...] | None = None) -> dict:
    plan = build_plan() if plan is None else plan
    return {
        "dataset_id": DATASET_ID,
        "seed_revision": SEED_REVISION,
        "data_kind": "simulated",
        "notice": SIMULATION_NOTICE,
        "plan_sha256": plan_digest(plan),
        "api_prefix": "/api/v1",
        "endpoints": {
            "health": "/api/v1/health",
            "metrics": "/api/v1/metrics",
            "ingestion": "/api/v1/measurements",
        },
        "policies": {
            "sleep": asdict(fixtures.sleep_policy()),
            "baseline": plan[0].baselines[0].config.model_dump(mode="json"),
            "activity": [item.model_dump(mode="json") for item in fixtures.activity_inputs()[4]],
            "activity_reduction_run_length": ActivityOptions().reduction_run_length,
        },
        "reference_start": REFERENCE_START.isoformat(),
        "reference_computed_at": COMPUTED_AT.isoformat(),
        "latest_required_server_time": FINAL_AS_OF.isoformat(),
        "evaluated_domains": ["sleep", "physical_activity"],
        "vital_metrics": [metric.value for metric in VITAL_METRICS],
        "vital_evaluations": "Unsupported: measurements, data quality and personal baselines only.",
        "additional_dashboard_metrics": [metric.value for metric in DASHBOARD_METRICS],
        "acquisition": {
            "data_kind": "simulated",
            "waking_assumption_utc": "07:00; authored schedule, not inferred from sleep values",
            "protocols": {
                metric.value: dict(protocol) for metric, protocol in ACQUISITION_PROTOCOLS.items()
            },
            "device_id_pattern": "{crew_member_id}:{device_suffix}",
            "upgrade": "Use a fresh dedicated API; never relabel existing generic vital records.",
        },
        "crews": [
            {
                "crew_member_id": crew.crew_member_id,
                "display_name": crew.display_name,
                "scenario": crew.scenario,
                "description": crew.description,
                "measurement_count": len(crew.measurements),
                "metric_record_counts": dict(
                    sorted(Counter(item.metric.value for item in crew.measurements).items())
                ),
                "reused_fixtures": list(crew.reused_fixtures),
                "endpoints": {
                    resource: f"/api/v1/crew-members/{crew.crew_member_id}/{resource}"
                    for resource in ("measurements", "baselines", "evaluations")
                },
                "expected_demonstrations": [
                    {
                        "checkpoint": item.checkpoint,
                        "domain": item.command.domain.value,
                        "window_end": item.command.window_end.isoformat(),
                        "expected_status": item.expected_status,
                        "behavior": item.demonstration_behavior,
                    }
                    for item in crew.evaluations
                ],
            }
            for crew in plan
        ],
    }
