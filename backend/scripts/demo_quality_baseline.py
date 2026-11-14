"""Synthetic demonstration of the Data Quality Engine and the Personal Baseline Engine.

EVERY VALUE IN THIS MODULE IS SYNTHETIC. The numbers follow fixed arithmetic patterns
chosen to exercise the algorithms. They are not measurements, they do not model any
effect of spaceflight on the body, and they are not reference values. Differences
between mission phases are arbitrary. Every measurement is labelled
`source: "simulated"`.

Run from the `backend/` directory:

    python -m scripts.demo_quality_baseline          # readable summary
    python -m scripts.demo_quality_baseline --json   # every result as contract JSON
"""

import argparse
import json
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.algorithms.data_quality import (
    DataQualityConfig,
    SensorRange,
    assess_measurements,
    assess_window,
)
from app.algorithms.personal_baseline import BaselineConfig, OutlierHandling, build_baselines
from app.models import (
    METRIC_CATALOG,
    DataQuality,
    MeasurementSource,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)

SYNTHETIC_NOTICE = "SYNTHETIC DEMONSTRATION DATA - not real measurements, not reference values"

MISSION_ID = "mission-synthetic-001"
DEVICE_ID = "sim-wearable-01"

DAY = timedelta(days=1)
HOUR = timedelta(hours=1)

# Synthetic mission timeline.
PRE_FLIGHT_START = datetime(2026, 9, 10, tzinfo=UTC)
LAUNCH_START = PRE_FLIGHT_START + 30 * DAY
IN_FLIGHT_START = LAUNCH_START + DAY
COMPUTED_AT = IN_FLIGHT_START + 30 * DAY

# Window of the data-quality scenario: twelve hours of the last day before `COMPUTED_AT`.
QUALITY_CREW = "crew-synthetic-002"
QUALITY_WINDOW_START = COMPUTED_AT - DAY
QUALITY_WINDOW_END = QUALITY_WINDOW_START + 12 * HOUR

# Fixed offsets added to a base value, repeated every seven samples. They only give the
# synthetic series some spread; they model nothing.
_PATTERN = (0.0, 1.5, -1.0, 2.0, -2.5, 0.5, -0.5)

# Illustrative setting, chosen only so that the demonstration reaches the `established`
# status. It is not a validated criterion and must not be reused as one.
DEMO_ESTABLISHED_MIN_SAMPLES = 21

# Illustrative protocol of the synthetic device: one heart-rate reading per day.
DEMO_DAILY_PROTOCOL = DataQualityConfig(expected_intervals={MetricType.HEART_RATE: DAY})

# Measuring range of the synthetic device. It is invented for the demonstration and is
# not taken from the documentation of any real device.
DEMO_SENSOR_RANGE = SensorRange(
    minimum=70.0,
    maximum=100.0,
    source="synthetic device invented for this demonstration, not a real device document",
)


@dataclass(frozen=True)
class Scenario:
    """One synthetic scenario: the data, the timeline and the settings to run it with."""

    title: str
    purpose: str
    measurements: list[PhysiologicalMeasurement]
    mission_phases: list[MissionPhase]
    computed_at: datetime
    config: BaselineConfig
    metrics: tuple[MetricType, ...] | None = None


def synthetic_timeline() -> list[MissionPhase]:
    """Thirty days of pre-flight, one day of launch, then an open-ended flight."""
    return [
        _phase(MissionPhaseType.PRE_FLIGHT, PRE_FLIGHT_START, LAUNCH_START),
        _phase(MissionPhaseType.LAUNCH, LAUNCH_START, IN_FLIGHT_START),
        _phase(MissionPhaseType.IN_FLIGHT, IN_FLIGHT_START, None),
    ]


def phase_aware_scenario() -> Scenario:
    """One reading per day across three phases, shifted arbitrarily between them."""
    crew = "crew-synthetic-001"
    morning = timedelta(hours=8, minutes=30)
    measurements = [
        *_daily(crew, MetricType.HEART_RATE, 58.0, PRE_FLIGHT_START + morning, 30, "pre"),
        *_daily(crew, MetricType.HEART_RATE, 60.0, LAUNCH_START + morning, 1, "launch"),
        *_daily(crew, MetricType.HEART_RATE, 62.0, IN_FLIGHT_START + morning, 30, "flight"),
    ]
    return Scenario(
        title="Phase-aware personal baselines",
        purpose=(
            "One baseline per mission phase for the same crew member and metric. The launch "
            "phase holds a single reading, so its baseline is insufficient_data."
        ),
        measurements=measurements,
        mission_phases=synthetic_timeline(),
        computed_at=COMPUTED_AT,
        config=BaselineConfig(
            quality=DEMO_DAILY_PROTOCOL, established_min_samples=DEMO_ESTABLISHED_MIN_SAMPLES
        ),
    )


def quality_issue_scenario() -> Scenario:
    """A batch that contains every kind of issue the Data Quality Engine reports."""
    crew = QUALITY_CREW
    start = QUALITY_WINDOW_START
    saturation = MetricType.BLOOD_OXYGEN_SATURATION

    def spo2(name: str, hour: int, value: float) -> PhysiologicalMeasurement:
        return _measurement(f"sim-spo2-{name}", crew, saturation, value, start + hour * HOUR)

    measurements = [
        spo2("00", 0, 97.0),
        spo2("01", 1, 98.0),
        spo2("02", 2, 97.0),
        spo2("02-copy", 2, 97.0),  # redundant copy of the previous record
        # Hours 3 and 4 are missing.
        spo2("05-a", 5, 96.0),  # two records of the same observation ...
        spo2("05-b", 5, 91.0),  # ... that disagree
        spo2("06", 6, 104.0),  # impossible: a percentage above 100
        spo2("07", 7, 65.0),  # outside the measuring range of the synthetic device
        spo2("08", 8, 98.0),
        spo2("09", 9, 97.0),
        spo2("10", 10, 98.0),
        spo2("11", 11, 97.0),
        # A blood-pressure reading whose two values were swapped.
        _measurement(
            "sim-bp-systolic", crew, MetricType.SYSTOLIC_BLOOD_PRESSURE, 78.0, start + 8 * HOUR
        ),
        _measurement(
            "sim-bp-diastolic", crew, MetricType.DIASTOLIC_BLOOD_PRESSURE, 118.0, start + 8 * HOUR
        ),
        # Forty-five minutes of exercise reported for a thirty-minute interval.
        _measurement(
            "sim-exercise",
            crew,
            MetricType.EXERCISE_DURATION,
            45.0,
            start + 6 * HOUR,
            interval_end=start + 6 * HOUR + timedelta(minutes=30),
        ),
        # A reading dated one day after the assessment.
        _measurement("sim-hr-future", crew, MetricType.HEART_RATE, 60.0, COMPUTED_AT + DAY),
    ]
    return Scenario(
        title="Data quality issues",
        purpose=(
            "Missing samples, a redundant copy, conflicting records, an impossible value, a "
            "value outside the sensor range, an inconsistent blood-pressure reading, a "
            "duration longer than its interval and a timestamp in the future."
        ),
        measurements=measurements,
        mission_phases=synthetic_timeline(),
        computed_at=COMPUTED_AT,
        config=BaselineConfig(
            quality=DataQualityConfig(
                sensor_ranges={DEVICE_ID: {saturation: DEMO_SENSOR_RANGE}},
                expected_intervals={saturation: HOUR},
            )
        ),
    )


def outlier_scenario() -> Scenario:
    """Thirty daily readings, one of them replaced by an arbitrary extreme value."""
    crew = "crew-synthetic-003"
    measurements = _daily(
        crew, MetricType.HEART_RATE, 58.0, PRE_FLIGHT_START + 8 * HOUR, 30, "outlier"
    )
    measurements[12] = measurements[12].model_copy(update={"value": 96.0})
    return Scenario(
        title="A potential statistical outlier in the reference data",
        purpose=(
            "The same data with the two outlier settings. By default the value is reported "
            "and kept: the mean and the standard deviation move, the median and the MAD do "
            "not. It can be excluded by configuration."
        ),
        measurements=measurements,
        mission_phases=[_phase(MissionPhaseType.PRE_FLIGHT, PRE_FLIGHT_START, None)],
        computed_at=LAUNCH_START,
        config=BaselineConfig(
            quality=DEMO_DAILY_PROTOCOL, established_min_samples=DEMO_ESTABLISHED_MIN_SAMPLES
        ),
    )


def edge_case_scenario() -> Scenario:
    """Zero variance, a single value and a metric that was never observed."""
    crew = "crew-synthetic-004"
    start = PRE_FLIGHT_START + 8 * HOUR
    measurements = [
        *_daily(crew, MetricType.BODY_MASS, 70.0, start, 30, "mass", pattern=(0.0,)),
        _measurement("sim-resp-0000", crew, MetricType.RESPIRATORY_RATE, 14.0, start),
    ]
    return Scenario(
        title="Zero variance, insufficient data and missing observations",
        purpose=(
            "Thirty identical values give a provisional baseline with zero dispersion, a "
            "single value gives insufficient_data, and a requested metric without any "
            "measurement is reported instead of being skipped."
        ),
        measurements=measurements,
        mission_phases=[_phase(MissionPhaseType.PRE_FLIGHT, PRE_FLIGHT_START, None)],
        computed_at=LAUNCH_START,
        config=BaselineConfig(established_min_samples=DEMO_ESTABLISHED_MIN_SAMPLES),
        metrics=(MetricType.RESPIRATORY_RATE, MetricType.BODY_TEMPERATURE, MetricType.BODY_MASS),
    )


def baselines_of(
    scenario: Scenario, outlier_handling: OutlierHandling | None = None
) -> list[PersonalBaseline]:
    """Build every baseline of a scenario, optionally with another outlier setting."""
    config = scenario.config
    if outlier_handling is not None:
        config = replace(config, outlier_handling=outlier_handling)
    return build_baselines(
        scenario.measurements,
        scenario.mission_phases,
        computed_at=scenario.computed_at,
        config=config,
        metrics=scenario.metrics,
    )


def assessed_measurements_of(scenario: Scenario) -> list[PhysiologicalMeasurement]:
    """Assess every measurement of a scenario."""
    return assess_measurements(
        scenario.measurements, assessed_at=scenario.computed_at, config=scenario.config.quality
    )


def saturation_window_quality(scenario: Scenario) -> DataQuality:
    """Assess the twelve-hour oxygen-saturation window of the data-quality scenario."""
    return assess_window(
        scenario.measurements,
        crew_member_id=QUALITY_CREW,
        metric=MetricType.BLOOD_OXYGEN_SATURATION,
        window_start=QUALITY_WINDOW_START,
        window_end=QUALITY_WINDOW_END,
        assessed_at=scenario.computed_at,
        config=scenario.config.quality,
    )


def build_results() -> dict[str, dict]:
    """Run every scenario and return the results as contract JSON, keyed by scenario."""
    phase_aware = phase_aware_scenario()
    quality = quality_issue_scenario()
    outlier = outlier_scenario()
    edge_cases = edge_case_scenario()
    return {
        "phase_aware_baselines": {
            "title": phase_aware.title,
            "baselines": _dump(baselines_of(phase_aware)),
        },
        "data_quality_issues": {
            "title": quality.title,
            "measurements": _dump(assessed_measurements_of(quality)),
            "blood_oxygen_saturation_window": saturation_window_quality(quality).model_dump(
                mode="json"
            ),
        },
        "potential_outlier": {
            "title": outlier.title,
            **{
                f"baselines_outliers_{handling.value}": _dump(baselines_of(outlier, handling))
                for handling in OutlierHandling
            },
        },
        "edge_cases": {"title": edge_cases.title, "baselines": _dump(baselines_of(edge_cases))},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the synthetic scenarios of the data-quality and baseline engines."
    )
    parser.add_argument("--json", action="store_true", help="print every result as contract JSON")
    args = parser.parse_args(argv)

    if args.json:
        print(json.dumps({"notice": SYNTHETIC_NOTICE, "scenarios": build_results()}, indent=2))
        return 0

    rule = "=" * len(SYNTHETIC_NOTICE)
    print(f"{rule}\n{SYNTHETIC_NOTICE}\n{rule}")

    scenario = phase_aware_scenario()
    _print_heading(1, scenario)
    for baseline in baselines_of(scenario):
        _print_baseline(baseline)

    scenario = quality_issue_scenario()
    _print_heading(2, scenario)
    for item in assessed_measurements_of(scenario):
        quality = item.data_quality
        flags = ", ".join(flag.value for flag in quality.flags) or "-"
        print(f"  {item.measurement_id:<18} {quality.status.value:<10} flags: {flags}")
        if quality.notes:
            print(f"      {quality.notes}")
    print("  Window of blood_oxygen_saturation, 12 hours:")
    _print_quality(saturation_window_quality(scenario))

    scenario = outlier_scenario()
    _print_heading(3, scenario)
    for handling in OutlierHandling:
        print(f"  outlier_handling = {handling.value}")
        for baseline in baselines_of(scenario, handling):
            _print_baseline(baseline)

    scenario = edge_case_scenario()
    _print_heading(4, scenario)
    for baseline in baselines_of(scenario):
        _print_baseline(baseline)

    print(f"\n{rule}\n{SYNTHETIC_NOTICE}\n{rule}")
    return 0


def _phase(kind: MissionPhaseType, start: datetime, end: datetime | None) -> MissionPhase:
    return MissionPhase(
        phase_id=f"phase-synthetic-{kind.value}",
        mission_id=MISSION_ID,
        phase=kind,
        label=f"Synthetic {kind.value} phase",
        start_time=start,
        end_time=end,
    )


def _measurement(
    measurement_id: str,
    crew_member_id: str,
    metric: MetricType,
    value: float,
    measured_at: datetime,
    *,
    interval_end: datetime | None = None,
) -> PhysiologicalMeasurement:
    return PhysiologicalMeasurement(
        measurement_id=measurement_id,
        crew_member_id=crew_member_id,
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        value=value,
        measured_at=measured_at,
        interval_end=interval_end,
        source=MeasurementSource.SIMULATED,
        device_id=DEVICE_ID,
    )


def _daily(
    crew_member_id: str,
    metric: MetricType,
    base: float,
    start: datetime,
    days: int,
    label: str,
    *,
    pattern: tuple[float, ...] = _PATTERN,
) -> list[PhysiologicalMeasurement]:
    """One synthetic reading per day: `base` plus the repeating `pattern`."""
    return [
        _measurement(
            f"sim-{label}-{day:04d}",
            crew_member_id,
            metric,
            base + pattern[day % len(pattern)],
            start + day * DAY,
        )
        for day in range(days)
    ]


def _dump(models: list) -> list[dict]:
    return [model.model_dump(mode="json") for model in models]


def _print_heading(number: int, scenario: Scenario) -> None:
    print(f"\n[{number}] {scenario.title} (synthetic)")
    print(f"    {scenario.purpose}")


def _print_baseline(baseline: PersonalBaseline) -> None:
    statistics = baseline.statistics
    summary = (
        "no statistic"
        if statistics.mean is None
        else (
            f"mean {statistics.mean:.2f}, SD {statistics.standard_deviation:.2f}, "
            f"median {statistics.median:.2f}, MAD {statistics.median_absolute_deviation:.2f} "
            f"{baseline.unit}"
        )
    )
    print(
        f"  {baseline.crew_member_id}  {baseline.metric.value}  {baseline.mission_phase.value}: "
        f"{baseline.status.value}, values used: {baseline.sample_count}, {summary}"
    )
    _print_quality(baseline.data_quality)


def _print_quality(quality: DataQuality) -> None:
    score = "-" if quality.score is None else f"{quality.score:.2f}"
    completeness = "-" if quality.completeness is None else f"{quality.completeness:.2f}"
    flags = ", ".join(flag.value for flag in quality.flags) or "-"
    print(
        f"      data quality: {quality.status.value}, score {score}, "
        f"completeness {completeness}, flags: {flags}"
    )
    print(f"      {quality.notes}")


if __name__ == "__main__":
    sys.exit(main())
