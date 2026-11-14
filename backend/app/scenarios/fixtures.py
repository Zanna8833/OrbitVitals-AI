"""Hand-authored simulated inputs and explicit demonstration policies, never results.

Source of every date, value, missing-record position and policy setting in this
file: docs/scientific-scenarios.md, "Fixture protocol". These engineering fixtures
are not measurements, medical thresholds, recommended targets or NASA standards.
"""

from datetime import UTC, datetime, timedelta

from app.algorithms.data_quality import DataQualityConfig
from app.algorithms.personal_baseline import BaselineConfig
from app.domains.physical_activity import (
    ActivityDayPlan,
    ActivityMetricPolicy,
    ExerciseSession,
    RecordingCoverage,
)
from app.domains.sleep import MetricThresholds, SleepConfig
from app.models import (
    METRIC_CATALOG,
    MeasurementSource,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PhysiologicalMeasurement,
)

# Fixed UTC acquisition conventions, documented in the fixture protocol.
DAY = timedelta(days=1)
CREW = "simulated-astronaut-001"
SLEEP_START = datetime(2026, 11, 1, 12, tzinfo=UTC)
BASELINE_START = datetime(2026, 10, 1, 12, tzinfo=UTC)
ACTIVITY_START = datetime(2026, 11, 2, tzinfo=UTC)
SLEEP_METRICS = (MetricType.SLEEP_DURATION, MetricType.SLEEP_EFFICIENCY)
ACTIVITY_METRICS = (MetricType.EXERCISE_DURATION, MetricType.ACTIVE_ENERGY_EXPENDITURE)


def simulated_measurement(
    identifier: str,
    metric: MetricType,
    value: float,
    at: datetime,
    *,
    interval_end: datetime | None = None,
) -> PhysiologicalMeasurement:
    """Create a canonical, explicitly simulated measurement without any assessment."""
    return PhysiologicalMeasurement(
        measurement_id=identifier,
        crew_member_id=CREW,
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        value=value,
        measured_at=at,
        interval_end=interval_end,
        source=MeasurementSource.SIMULATED,
        device_id="simulated-acquisition-device",
    )


def sleep_policy() -> SleepConfig:
    """Use explicit demonstration effect sizes, not clinical cutoffs."""
    # Source: the fixture protocol and app/domains/sleep/demo.py's demonstration
    # convention. The policy is recorded in every checkpoint that consumes it.
    return SleepConfig(
        policy_id="simulated-mission-sleep-v1",
        duration=MetricThresholds(
            minimum_slope_per_day=5,
            minimum_total_change=30,
            minimum_observation_deviation=60,
        ),
        efficiency=MetricThresholds(
            minimum_slope_per_day=0.5,
            minimum_total_change=3,
            minimum_observation_deviation=5,
        ),
        minimum_nights=4,
        minimum_coverage=0.6,
        minimum_span_days=3,
        maximum_consecutive_missing_nights=2,
        minimum_decreasing_fraction=0.75,
        night_start_hour_utc=12,
    )


def daily_quality_policy(metrics: tuple[MetricType, ...]) -> DataQualityConfig:
    """Declare the fixture's daily acquisition cadence without a sensor-range claim."""
    return DataQualityConfig(expected_intervals=dict.fromkeys(metrics, DAY))


def baseline_policy(*, establishment_configured: bool = True) -> BaselineConfig:
    """Supply a demonstration establishment rule or exercise the engine's default."""
    # These sample-count/span choices are fixture policy, not validation evidence.
    return BaselineConfig(
        quality=daily_quality_policy((MetricType.HEART_RATE,)),
        established_min_samples=10 if establishment_configured else None,
        established_min_span=9 * DAY if establishment_configured else None,
    )


def sleep_records(
    label: str,
    durations: tuple[float, ...],
    efficiencies: tuple[float, ...],
    *,
    missing_nights: frozenset[int] = frozenset(),
) -> tuple[PhysiologicalMeasurement, ...]:
    """Create one paired summary per recorded night, with explicitly absent nights."""
    records = []
    for index, values in enumerate(zip(durations, efficiencies, strict=True)):
        if index in missing_nights:
            continue
        # The fixture's primary sleep period starts at 22:00 UTC and lasts nine
        # hours. Actual metric values are supplied, never inferred from elapsed time.
        at = SLEEP_START + index * DAY + timedelta(hours=10)
        for metric, value in zip(SLEEP_METRICS, values, strict=True):
            records.append(
                simulated_measurement(
                    f"sim-{label}-{index:02d}-{metric.value}",
                    metric,
                    value,
                    at,
                    interval_end=at + timedelta(hours=9),
                )
            )
    return tuple(records)


def sensor_failure_records() -> tuple[PhysiologicalMeasurement, ...]:
    """Inject definition violations and a duplicate with a distinct opaque ID."""
    records = list(
        sleep_records(
            "sensor-quality",
            (480, 480, 480, 480, 480, -30, 480),
            (92, 92, 125, 92, 92, 92, 92),
        )
    )
    original = next(
        record
        for record in records
        if record.metric == MetricType.SLEEP_DURATION
        and record.measured_at == SLEEP_START + 3 * DAY + timedelta(hours=10)
    )
    records.append(original.model_copy(update={"measurement_id": "zz-simulated-redundant-copy"}))
    return tuple(records)


def restriction_records() -> tuple[PhysiologicalMeasurement, ...]:
    """A constructed reduction of fifteen minutes per elapsed day, with two gaps."""
    return sleep_records(
        "sleep-restriction",
        (490, 475, 460, 445, 430, 415, 400, 385, 370),
        (92,) * 9,
        missing_nights=frozenset({2, 6}),
    )


def baseline_inputs() -> tuple[tuple[PhysiologicalMeasurement, ...], tuple[MissionPhase, ...]]:
    """A fictional mission schedule with phase-specific, variable heart-rate data."""
    schedule = (
        (MissionPhaseType.PRE_FLIGHT, 0, 14),
        (MissionPhaseType.LAUNCH, 14, 16),
        (MissionPhaseType.IN_FLIGHT, 16, 30),
        (MissionPhaseType.RETURN_TO_EARTH, 30, 31),
        (MissionPhaseType.POST_FLIGHT, 31, 35),
    )
    phases = tuple(
        MissionPhase(
            phase_id=f"simulated-phase-{phase.value}",
            mission_id="simulated-mission-001",
            phase=phase,
            label=f"SIMULATED {phase.value} phase",
            start_time=BASELINE_START + first * DAY,
            end_time=BASELINE_START + last * DAY,
        )
        for phase, first, last in schedule
    )
    records = []
    for label, offset, values in (
        ("pre-flight", 0, (56, 57, 58, 59, 60, 58, 58) * 2),
        ("in-flight", 16, (62, 63, 64, 65, -5, 64, 64) * 2),
    ):
        for index, value in enumerate(values):
            records.append(
                simulated_measurement(
                    f"sim-{label}-heart-rate-{index:02d}",
                    MetricType.HEART_RATE,
                    value,
                    BASELINE_START + (offset + index) * DAY + timedelta(hours=9),
                )
            )
    records.append(
        simulated_measurement(
            "sim-launch-single-heart-rate",
            MetricType.HEART_RATE,
            61,
            BASELINE_START + 14 * DAY + timedelta(hours=1),
        )
    )
    return tuple(
        sorted(records, key=lambda record: (record.measured_at, record.measurement_id))
    ), phases


def activity_inputs() -> tuple[
    tuple[PhysiologicalMeasurement, ...],
    tuple[ExerciseSession, ...],
    tuple[RecordingCoverage, ...],
    tuple[ActivityDayPlan, ...],
    tuple[ActivityMetricPolicy, ...],
]:
    """Independent activity values, explicit rest, partial recording and a missing day."""
    # The energy sequence is independently authored; no energy-from-duration
    # conversion is performed. All targets and context are fixture instructions.
    durations = (60, 55, 50, 45, 40, 0, 35, 30, 25, 20, 15, None, 0, 10)
    energies = (300, 280, 260, 220, 200, 0, 170, 150, 120, 100, None, None, 0, 50)
    rest_days = {5, 12}
    records, sessions, coverage, plans = [], [], [], []
    for index, values in enumerate(zip(durations, energies, strict=True)):
        at = ACTIVITY_START + index * DAY + timedelta(hours=9)
        links = []
        if index in rest_days:
            plans.append(
                ActivityDayPlan(
                    day=at.date(),
                    planned_rest=True,
                    notes="SIMULATED mission plan: scheduled rest, not inferred inactivity.",
                )
            )
        if index == 11:
            # No record or coverage confirmation exists for this day.
            continue
        for metric, value in zip(ACTIVITY_METRICS, values, strict=True):
            coverage.append(
                RecordingCoverage(
                    day=at.date(),
                    metric=metric,
                    complete=index != 10,
                    notes="SIMULATED recording-workflow confirmation; not a sensor-quality score.",
                )
            )
            if value is None or index in rest_days:
                continue
            record = simulated_measurement(
                f"sim-activity-{index:02d}-{metric.value}",
                metric,
                value,
                at,
                interval_end=at + timedelta(hours=1),
            )
            records.append(record)
            links.append(record.measurement_id)
        if links:
            sessions.append(
                ExerciseSession(
                    session_id=f"sim-activity-session-{index:02d}",
                    start_time=at,
                    end_time=at + timedelta(hours=1),
                    measurement_ids=tuple(links),
                    label="SIMULATED session; missing linked metrics remain incomplete.",
                )
            )
    policies = (
        ActivityMetricPolicy(
            metric=MetricType.EXERCISE_DURATION, daily_target=40, weekly_target=240
        ),
        ActivityMetricPolicy(
            metric=MetricType.ACTIVE_ENERGY_EXPENDITURE, daily_target=200, weekly_target=1200
        ),
    )
    return tuple(records), tuple(sessions), tuple(coverage), tuple(plans), policies
