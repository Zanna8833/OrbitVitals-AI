"""Deterministic SIMULATED scenarios, never real crew records or exercise prescriptions.

Run from backend/: python -m app.domains.physical_activity.demo [--full]
"""

import argparse
import json
from datetime import UTC, datetime, timedelta

from app.domains.physical_activity.models import (
    ACTIVITY_METRICS,
    ActivityDayPlan,
    ActivityMetricPolicy,
    ActivityRequest,
    DailyBaselineReference,
    ExerciseSession,
    RecordingCoverage,
)
from app.domains.physical_activity.service import monitor_activity
from app.models import (
    METRIC_CATALOG,
    AlgorithmInfo,
    BaselineStatistics,
    BaselineStatus,
    DataQuality,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityStatus,
)

SIMULATED_START = datetime(2026, 11, 2, tzinfo=UTC)


def _simulated_request(
    name: str,
    durations: list[float | None],
    energies: list[float | None],
    *,
    plans: tuple[ActivityDayPlan, ...] = (),
    with_baselines: bool = True,
    with_policies: bool = True,
    degraded_day: int | None = None,
) -> ActivityRequest:
    records = []
    sessions = []
    coverage = []
    for offset, (duration, energy) in enumerate(zip(durations, energies, strict=True)):
        start = SIMULATED_START + timedelta(days=offset, hours=9)
        end = start + timedelta(hours=1)
        links = []
        for metric, value in zip(ACTIVITY_METRICS, (duration, energy), strict=True):
            coverage.append(
                RecordingCoverage(day=start.date(), metric=metric, complete=value is not None)
            )
            if value is None or value == 0:
                continue
            identifier = f"sim-{name}-{offset}-{metric.value}"
            quality = None
            if offset == degraded_day:
                quality = DataQuality(
                    status=QualityStatus.DEGRADED,
                    notes="SIMULATED measurement-quality degradation for demonstration.",
                )
            records.append(
                PhysiologicalMeasurement(
                    measurement_id=identifier,
                    crew_member_id="sim-crew-001",
                    metric=metric,
                    unit=METRIC_CATALOG[metric].unit,
                    value=value,
                    measured_at=start,
                    interval_end=end,
                    source=MeasurementSource.SIMULATED,
                    device_id="sim-activity-device",
                    data_quality=quality,
                )
            )
            links.append(identifier)
        if links:
            sessions.append(
                ExerciseSession(
                    session_id=f"sim-session-{name}-{offset}",
                    start_time=start,
                    end_time=end,
                    measurement_ids=tuple(links),
                    label="SIMULATED exercise session",
                )
            )
    baselines = []
    if with_baselines:
        for metric, mean in zip(ACTIVITY_METRICS, (45, 220), strict=True):
            baselines.append(
                DailyBaselineReference(
                    baseline=PersonalBaseline(
                        baseline_id=f"sim-baseline-{metric.value}",
                        crew_member_id="sim-crew-001",
                        metric=metric,
                        unit=METRIC_CATALOG[metric].unit,
                        mission_phase=MissionPhaseType.IN_FLIGHT,
                        status=BaselineStatus.ESTABLISHED,
                        window_start=SIMULATED_START - timedelta(days=28),
                        window_end=SIMULATED_START - timedelta(days=7),
                        sample_count=21,
                        statistics=BaselineStatistics(mean=mean),
                        algorithm=AlgorithmInfo(
                            name="simulated_reference_fixture", version="0.1.0"
                        ),
                        computed_at=SIMULATED_START - timedelta(days=6),
                    ),
                    comparison_basis="complete_active_day_total",
                    comparable=True,
                )
            )
    policies = ()
    if with_policies:
        # All values below are fabricated scenario settings, not recommended targets,
        # validated review cutoffs, or values copied from a spaceflight standard.
        policies = (
            ActivityMetricPolicy(
                metric=MetricType.EXERCISE_DURATION,
                daily_target=30,
                weekly_target=240,
                baseline_absolute_tolerance=15,
            ),
            ActivityMetricPolicy(
                metric=MetricType.ACTIVE_ENERGY_EXPENDITURE,
                daily_target=150,
                weekly_target=1200,
                baseline_absolute_tolerance=80,
            ),
        )
    return ActivityRequest(
        crew_member_id="sim-crew-001",
        window_start=SIMULATED_START,
        window_end=SIMULATED_START + timedelta(days=len(durations)),
        evaluated_at=SIMULATED_START + timedelta(days=len(durations)),
        evaluation_id=f"sim-evaluation-{name}",
        measurements=tuple(records),
        sessions=tuple(sessions),
        coverage=tuple(coverage),
        policies=policies,
        baselines=tuple(baselines),
        day_plans=plans,
        mission_phase=MissionPhaseType.IN_FLIGHT,
        context_notes="SIMULATED scenario; all records, references and plan values are fabricated.",
    )


def build_simulated_scenarios() -> dict[str, ActivityRequest]:
    """Return isolated hypothetical scenarios; no external service or real data is read."""
    rest_day = ActivityDayPlan(
        day=(SIMULATED_START + timedelta(days=6)).date(),
        planned_rest=True,
        notes="SIMULATED scheduled rest.",
    )
    exception = ActivityDayPlan(
        day=(SIMULATED_START + timedelta(days=3)).date(),
        comparisons_enabled=False,
        notes="SIMULATED equipment maintenance; exercise comparisons suspended.",
    )
    return {
        "simulated_target_adherence": _simulated_request(
            "adherence", [45] * 6 + [0], [220] * 6 + [0], plans=(rest_day,)
        ),
        "simulated_missed_targets_and_reduction": _simulated_request(
            "reduction", [45, 40, 35, 30, 25, 20, 15], [220, 200, 180, 160, 140, 120, 100]
        ),
        "simulated_rest_and_operational_exception": _simulated_request(
            "context",
            [45, 45, 45, 0, 45, 45, 0],
            [220, 220, 220, 0, 220, 220, 0],
            plans=(rest_day, exception),
        ),
        "simulated_missing_and_degraded_records": _simulated_request(
            "missing",
            [45, None, 30, 45, None, 45, 0],
            [220, None, None, 220, 200, 220, 0],
            plans=(rest_day,),
            degraded_day=2,
        ),
        "simulated_observations_without_history_or_targets": _simulated_request(
            "cold-start", [45, 45, 45], [220, 220, 220], with_baselines=False, with_policies=False
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SIMULATED physical-activity scenarios.")
    parser.add_argument("--full", action="store_true", help="Include complete inputs and reports.")
    args = parser.parse_args(argv)
    scenarios = []
    for name, request in build_simulated_scenarios().items():
        report = monitor_activity(request)
        item = {
            "name": name,
            "data_kind": "simulated",
            "status": report.evaluation.status.value,
            "summary": report.evaluation.summary,
            "reduction_runs": len(report.trends),
        }
        if args.full:
            item.update(
                request=request.model_dump(mode="json"), report=report.model_dump(mode="json")
            )
        scenarios.append(item)
    print(json.dumps({"data_kind": "simulated", "scenarios": scenarios}, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
