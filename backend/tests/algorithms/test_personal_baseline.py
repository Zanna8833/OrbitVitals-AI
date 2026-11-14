"""Personal Baseline Engine. All measurements are synthetic."""

import math
from datetime import datetime, timedelta, timezone

import pytest
from jsonschema import Draft202012Validator

from app.algorithms.data_quality import DataQualityConfig, SensorRange
from app.algorithms.personal_baseline import (
    ALGORITHM,
    BaselineConfig,
    OutlierHandling,
    build_baseline,
    build_baselines,
)
from app.models import (
    BaselineStatistics,
    BaselineStatus,
    MeasurementSource,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from tests.algorithms.builders import (
    CREW,
    DAY,
    DEVICE,
    HOUR,
    IN_FLIGHT_START,
    LAUNCH_START,
    T0,
    measurement,
    phase,
    series,
    timeline,
)
from tests.support import load_schema

PRE_FLIGHT = MissionPhaseType.PRE_FLIGHT
LAUNCH = MissionPhaseType.LAUNCH
IN_FLIGHT = MissionPhaseType.IN_FLIGHT

# After the 30 days of pre-flight and the day of launch, 9 days into the flight.
NOW = T0 + 40 * DAY

# Mean 60, median 60, sample standard deviation sqrt(10), MAD 2. No potential outlier.
FIVE_VALUES = [56.0, 58.0, 60.0, 62.0, 64.0]


def baseline_of(
    measurements: list[PhysiologicalMeasurement],
    *,
    mission_phase: MissionPhaseType = PRE_FLIGHT,
    metric: MetricType = MetricType.HEART_RATE,
    crew_member_id: str = CREW,
    computed_at: datetime = NOW,
    config: BaselineConfig | None = None,
    **options: object,
) -> PersonalBaseline:
    baseline = build_baseline(
        measurements,
        timeline(),
        crew_member_id=crew_member_id,
        metric=metric,
        mission_phase=mission_phase,
        computed_at=computed_at,
        config=config,
        **options,
    )
    assert baseline is not None
    return baseline


# --- Content of a baseline ---------------------------------------------------------


def test_a_baseline_describes_the_measurements_of_its_phase() -> None:
    baseline = baseline_of(series(FIVE_VALUES))

    assert baseline.crew_member_id == CREW
    assert baseline.metric is MetricType.HEART_RATE
    assert baseline.unit == "bpm"
    assert baseline.mission_phase is PRE_FLIGHT
    assert baseline.window_start == T0
    assert baseline.window_end == LAUNCH_START
    assert baseline.sample_count == 5
    assert baseline.statistics == BaselineStatistics(
        mean=60.0,
        standard_deviation=math.sqrt(10),
        median=60.0,
        median_absolute_deviation=2.0,
        minimum=56.0,
        maximum=64.0,
    )
    assert baseline.algorithm == ALGORITHM
    assert baseline.computed_at == NOW


def test_a_baseline_carries_the_quality_of_its_reference_data() -> None:
    quality = baseline_of(series(FIVE_VALUES)).data_quality

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.flags == []
    assert quality.assessed_at == NOW
    assert "5 records in the window: 5 acceptable" in quality.notes


def test_baseline_output_matches_the_published_schema() -> None:
    validator = Draft202012Validator(load_schema("personal_baseline"))

    for values in ([], [58.0], FIVE_VALUES):
        baseline = baseline_of(series(values))
        validator.validate(baseline.model_dump(mode="json"))
        assert PersonalBaseline.model_validate(baseline.model_dump(mode="json")) == baseline


def test_times_are_reported_in_utc() -> None:
    baseline = baseline_of(series(FIVE_VALUES))

    for moment in (baseline.window_start, baseline.window_end, baseline.computed_at):
        assert moment.utcoffset() == timedelta(0)


# --- Mission phases ----------------------------------------------------------------


def test_each_mission_phase_has_its_own_baseline() -> None:
    batch = [
        *series([56.0, 58.0, 60.0], start=T0),
        *series([70.0, 72.0, 74.0, 76.0], start=IN_FLIGHT_START),
    ]

    pre_flight = baseline_of(batch, mission_phase=PRE_FLIGHT)
    in_flight = baseline_of(batch, mission_phase=IN_FLIGHT)

    assert (pre_flight.sample_count, pre_flight.statistics.mean) == (3, 58.0)
    assert (in_flight.sample_count, in_flight.statistics.mean) == (4, 73.0)
    assert pre_flight.statistics.maximum < in_flight.statistics.minimum
    assert pre_flight.baseline_id != in_flight.baseline_id


def test_a_phase_includes_its_start_and_excludes_its_end() -> None:
    batch = [
        measurement(58.0, LAUNCH_START - timedelta(seconds=1)),
        measurement(60.0, LAUNCH_START),
        measurement(62.0, IN_FLIGHT_START - timedelta(seconds=1)),
        measurement(64.0, IN_FLIGHT_START),
    ]

    launch = baseline_of(batch, mission_phase=LAUNCH)

    assert launch.sample_count == 2
    assert (launch.statistics.minimum, launch.statistics.maximum) == (60.0, 62.0)
    assert (launch.window_start, launch.window_end) == (LAUNCH_START, IN_FLIGHT_START)


def test_an_ongoing_phase_ends_at_the_computation_time() -> None:
    batch = series([70.0, 72.0, 74.0, 76.0, 78.0], start=IN_FLIGHT_START)

    in_flight = baseline_of(batch, mission_phase=IN_FLIGHT, computed_at=IN_FLIGHT_START + 3 * DAY)

    assert in_flight.window_start == IN_FLIGHT_START
    assert in_flight.window_end == IN_FLIGHT_START + 3 * DAY
    # The measurement taken exactly at the computation time is not part of the window.
    assert in_flight.sample_count == 3
    assert in_flight.statistics.maximum == 74.0


def test_a_phase_that_has_not_started_has_no_baseline() -> None:
    during_pre_flight = T0 + 10 * DAY

    assert (
        build_baseline(
            series(FIVE_VALUES),
            timeline(),
            crew_member_id=CREW,
            metric=MetricType.HEART_RATE,
            mission_phase=IN_FLIGHT,
            computed_at=during_pre_flight,
        )
        is None
    )
    phases = {
        baseline.mission_phase
        for baseline in build_baselines(
            series(FIVE_VALUES), timeline(), computed_at=during_pre_flight
        )
    }
    assert phases == {PRE_FLIGHT}


def test_a_phase_missing_from_the_timeline_has_no_baseline() -> None:
    assert (
        build_baseline(
            series(FIVE_VALUES),
            timeline(),
            crew_member_id=CREW,
            metric=MetricType.HEART_RATE,
            mission_phase=MissionPhaseType.POST_FLIGHT,
            computed_at=NOW,
        )
        is None
    )
    assert build_baselines(series(FIVE_VALUES), [], computed_at=NOW) == []


def test_measurements_outside_every_phase_are_not_used() -> None:
    batch = [*series(FIVE_VALUES), measurement(200.0, T0 - DAY)]

    baseline = baseline_of(batch)

    assert baseline.sample_count == 5
    assert baseline.statistics.maximum == 64.0


def test_entries_of_the_same_phase_are_pooled() -> None:
    phases = [
        phase(IN_FLIGHT, T0, T0 + 2 * DAY, phase_id="flight-early"),
        phase(LAUNCH, T0 + 2 * DAY, T0 + 3 * DAY, phase_id="burn"),
        phase(IN_FLIGHT, T0 + 3 * DAY, T0 + 5 * DAY, phase_id="flight-late"),
    ]
    batch = series([56.0, 58.0, 99.0, 62.0, 64.0])

    baseline = build_baseline(
        batch,
        phases,
        crew_member_id=CREW,
        metric=MetricType.HEART_RATE,
        mission_phase=IN_FLIGHT,
        computed_at=NOW,
    )

    assert baseline.sample_count == 4
    assert baseline.statistics.maximum == 64.0
    assert (baseline.window_start, baseline.window_end) == (T0, T0 + 5 * DAY)


def test_the_reference_window_can_be_narrowed() -> None:
    batch = series([float(value) for value in range(20)])

    baseline = baseline_of(batch, reference_start=T0 + 5 * DAY, reference_end=T0 + 15 * DAY)

    assert baseline.sample_count == 10
    assert (baseline.statistics.minimum, baseline.statistics.maximum) == (5.0, 14.0)
    assert (baseline.window_start, baseline.window_end) == (T0 + 5 * DAY, T0 + 15 * DAY)


def test_a_reference_window_outside_the_phase_leaves_no_baseline() -> None:
    assert (
        build_baseline(
            series(FIVE_VALUES),
            timeline(),
            crew_member_id=CREW,
            metric=MetricType.HEART_RATE,
            mission_phase=PRE_FLIGHT,
            computed_at=NOW,
            reference_start=IN_FLIGHT_START,
        )
        is None
    )


@pytest.mark.parametrize(
    ("phases", "message"),
    [
        (
            [
                phase(PRE_FLIGHT, T0, T0 + 10 * DAY, phase_id="first"),
                phase(IN_FLIGHT, T0 + 9 * DAY, phase_id="second"),
            ],
            "'first' and 'second' overlap",
        ),
        (
            [phase(PRE_FLIGHT, T0, phase_id="open"), phase(IN_FLIGHT, T0 + DAY, phase_id="next")],
            "'open' and 'next' overlap",
        ),
        (
            [
                phase(PRE_FLIGHT, T0, T0 + DAY, mission_id="mission-a"),
                phase(IN_FLIGHT, T0 + DAY, mission_id="mission-b"),
            ],
            "single mission",
        ),
    ],
)
def test_an_ambiguous_timeline_is_refused(phases: list, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        build_baselines(series(FIVE_VALUES), phases, computed_at=NOW)


def test_the_computation_time_must_carry_a_time_zone() -> None:
    with pytest.raises(ValueError, match="computed_at must carry a time zone"):
        build_baselines(series(FIVE_VALUES), timeline(), computed_at=datetime(2026, 10, 1))


# --- Personal and per metric -------------------------------------------------------


def test_a_baseline_uses_the_measurements_of_its_crew_member_and_metric_only() -> None:
    batch = [
        *series(FIVE_VALUES),
        *series([90.0, 92.0, 94.0], crew_member_id="crew-test-002"),
        *series([14.0, 15.0, 16.0], metric=MetricType.RESPIRATORY_RATE),
    ]

    baseline = baseline_of(batch)
    other_person = baseline_of(batch, crew_member_id="crew-test-002")
    other_metric = baseline_of(batch, metric=MetricType.RESPIRATORY_RATE)

    assert (baseline.sample_count, baseline.statistics.mean) == (5, 60.0)
    assert (other_person.sample_count, other_person.statistics.mean) == (3, 92.0)
    assert (other_metric.sample_count, other_metric.statistics.mean) == (3, 15.0)
    assert other_metric.unit == "breaths/min"


def test_baselines_cover_every_crew_member_metric_and_phase_in_a_stable_order() -> None:
    batch = [
        *series([14.0, 15.0], metric=MetricType.RESPIRATORY_RATE),
        *series([90.0, 92.0], crew_member_id="crew-test-002"),
        *series(FIVE_VALUES),
    ]

    baselines = build_baselines(batch, timeline(), computed_at=NOW)

    assert [(b.crew_member_id, b.metric, b.mission_phase) for b in baselines] == [
        (CREW, MetricType.HEART_RATE, PRE_FLIGHT),
        (CREW, MetricType.HEART_RATE, LAUNCH),
        (CREW, MetricType.HEART_RATE, IN_FLIGHT),
        (CREW, MetricType.RESPIRATORY_RATE, PRE_FLIGHT),
        (CREW, MetricType.RESPIRATORY_RATE, LAUNCH),
        (CREW, MetricType.RESPIRATORY_RATE, IN_FLIGHT),
        ("crew-test-002", MetricType.HEART_RATE, PRE_FLIGHT),
        ("crew-test-002", MetricType.HEART_RATE, LAUNCH),
        ("crew-test-002", MetricType.HEART_RATE, IN_FLIGHT),
    ]
    assert len({baseline.baseline_id for baseline in baselines}) == len(baselines)


def test_build_baselines_agrees_with_build_baseline() -> None:
    batch = [*series(FIVE_VALUES), *series([70.0, 72.0, 74.0], start=IN_FLIGHT_START)]

    for baseline in build_baselines(batch, timeline(), computed_at=NOW):
        assert baseline == baseline_of(batch, mission_phase=baseline.mission_phase)


# --- Missing observations and insufficient data ------------------------------------


def test_missing_observations_yield_a_baseline_without_statistics() -> None:
    baseline = baseline_of(series(FIVE_VALUES), metric=MetricType.BODY_TEMPERATURE)

    assert baseline.status is BaselineStatus.INSUFFICIENT_DATA
    assert baseline.sample_count == 0
    assert baseline.statistics == BaselineStatistics()
    assert baseline.unit == "degC"
    assert baseline.data_quality.status is QualityStatus.UNUSABLE
    assert baseline.data_quality.flags == [QualityFlag.INSUFFICIENT_SAMPLES]
    assert "No record in the window." in baseline.data_quality.notes
    assert "No baseline statistic is reported." in baseline.data_quality.notes


def test_requested_crew_members_and_metrics_are_reported_even_without_data() -> None:
    baselines = build_baselines(
        series(FIVE_VALUES),
        timeline(),
        computed_at=NOW,
        crew_member_ids=[CREW, "crew-test-absent"],
        metrics=[MetricType.BODY_MASS, MetricType.HEART_RATE],
    )

    assert len(baselines) == 2 * 2 * 3
    by_key = {(b.crew_member_id, b.metric, b.mission_phase): b for b in baselines}
    assert by_key[(CREW, MetricType.HEART_RATE, PRE_FLIGHT)].sample_count == 5
    assert all(
        baseline.status is BaselineStatus.INSUFFICIENT_DATA
        for key, baseline in by_key.items()
        if key != (CREW, MetricType.HEART_RATE, PRE_FLIGHT)
    )


def test_a_metric_observed_in_one_phase_is_reported_as_missing_in_the_others() -> None:
    baselines = build_baselines(series(FIVE_VALUES), timeline(), computed_at=NOW)

    statuses = {baseline.mission_phase: baseline.status for baseline in baselines}

    assert statuses == {
        PRE_FLIGHT: BaselineStatus.PROVISIONAL,
        LAUNCH: BaselineStatus.INSUFFICIENT_DATA,
        IN_FLIGHT: BaselineStatus.INSUFFICIENT_DATA,
    }


def test_a_single_value_is_insufficient_and_reports_no_statistic() -> None:
    baseline = baseline_of([measurement(58.0)])

    assert baseline.status is BaselineStatus.INSUFFICIENT_DATA
    assert baseline.sample_count == 1
    assert baseline.statistics == BaselineStatistics()
    assert baseline.data_quality.status is QualityStatus.UNUSABLE
    assert baseline.data_quality.flags == [QualityFlag.INSUFFICIENT_SAMPLES]
    assert "1 usable value, fewer than the 2 required" in baseline.data_quality.notes


def test_two_values_give_a_provisional_baseline() -> None:
    baseline = baseline_of(series([58.0, 62.0]))

    assert baseline.status is BaselineStatus.PROVISIONAL
    assert baseline.sample_count == 2
    assert baseline.statistics.mean == 60.0
    assert baseline.statistics.standard_deviation == pytest.approx(math.sqrt(8))
    assert QualityFlag.INSUFFICIENT_SAMPLES not in baseline.data_quality.flags


def test_the_minimum_number_of_values_is_configurable() -> None:
    config = BaselineConfig(minimum_samples=6)

    baseline = baseline_of(series(FIVE_VALUES), config=config)

    assert baseline.status is BaselineStatus.INSUFFICIENT_DATA
    assert baseline.sample_count == 5
    assert baseline.statistics == BaselineStatistics()
    assert "5 usable values, fewer than the 6 required" in baseline.data_quality.notes


# --- Status ------------------------------------------------------------------------


def test_no_baseline_is_established_without_a_configured_criterion() -> None:
    baseline = baseline_of(series([58.0 + day % 5 for day in range(30)]))

    assert baseline.sample_count == 30
    assert baseline.status is BaselineStatus.PROVISIONAL
    assert "No criterion for an established baseline is configured" in baseline.data_quality.notes


@pytest.mark.parametrize(
    ("criteria", "value_count", "status"),
    [
        ({"established_min_samples": 5}, 5, BaselineStatus.ESTABLISHED),
        ({"established_min_samples": 5}, 4, BaselineStatus.PROVISIONAL),
        ({"established_min_span": 4 * DAY}, 5, BaselineStatus.ESTABLISHED),
        ({"established_min_span": 4 * DAY + HOUR}, 5, BaselineStatus.PROVISIONAL),
        (
            {"established_min_samples": 5, "established_min_span": 4 * DAY},
            5,
            BaselineStatus.ESTABLISHED,
        ),
        (
            {"established_min_samples": 6, "established_min_span": 4 * DAY},
            5,
            BaselineStatus.PROVISIONAL,
        ),
        (
            {"established_min_samples": 5, "established_min_span": 5 * DAY},
            5,
            BaselineStatus.PROVISIONAL,
        ),
    ],
)
def test_a_baseline_is_established_when_every_configured_criterion_is_met(
    criteria: dict, value_count: int, status: BaselineStatus
) -> None:
    values = [56.0 + 2 * day for day in range(value_count)]

    baseline = baseline_of(series(values), config=BaselineConfig(**criteria))

    assert baseline.status is status


def test_the_status_is_explained_in_plain_language() -> None:
    config = BaselineConfig(established_min_samples=5, established_min_span=7 * DAY)

    provisional = baseline_of(series(FIVE_VALUES), config=config)
    established = baseline_of(series(FIVE_VALUES, step=2 * DAY), config=config)

    assert (
        "The baseline is provisional: the configured criteria are at least 5 values and values "
        "spanning at least 7 days; 5 values spanning 4 days were used."
    ) in provisional.data_quality.notes
    assert (
        "The configured criteria for an established baseline are met (at least 5 values and "
        "values spanning at least 7 days); 5 values spanning 8 days were used."
    ) in established.data_quality.notes


# --- Zero variance -----------------------------------------------------------------


def test_identical_values_give_a_provisional_baseline_with_zero_dispersion() -> None:
    config = BaselineConfig(established_min_samples=5)

    baseline = baseline_of(
        series([70.0] * 10, metric=MetricType.BODY_MASS),
        metric=MetricType.BODY_MASS,
        config=config,
    )

    assert baseline.status is BaselineStatus.PROVISIONAL  # although the criterion is met
    assert baseline.sample_count == 10
    assert baseline.statistics == BaselineStatistics(
        mean=70.0,
        standard_deviation=0.0,
        median=70.0,
        median_absolute_deviation=0.0,
        minimum=70.0,
        maximum=70.0,
    )
    assert "All the values used are identical" in baseline.data_quality.notes
    assert "not screened" not in baseline.data_quality.notes
    # Zero dispersion is a property of the baseline, not a defect of the data.
    assert baseline.data_quality.status is QualityStatus.ACCEPTABLE


def test_a_zero_median_absolute_deviation_is_reported_and_not_divided_by() -> None:
    # Most values are identical: the MAD is zero although the values vary.
    values = [60.0, 60.0, 60.0, 60.0, 61.0, 59.0, 200.0]
    config = BaselineConfig(established_min_samples=5, outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series(values), config=config)

    assert baseline.statistics.median_absolute_deviation == 0.0
    assert baseline.statistics.standard_deviation > 0
    # Nothing is excluded on a criterion that is undefined.
    assert baseline.sample_count == 7
    assert baseline.statistics.maximum == 200.0
    assert baseline.status is BaselineStatus.ESTABLISHED
    notes = baseline.data_quality.notes
    assert "Potential outliers were not screened" in notes
    assert "The median absolute deviation of the values used is zero" in notes


# --- Outliers ----------------------------------------------------------------------

# Median 61, MAD 3: the modified z-score of 120 is 0.6745 * 59 / 3, about 13.3.
WITH_OUTLIER = [*FIVE_VALUES, 120.0]


def test_potential_outliers_are_reported_and_kept_by_default() -> None:
    baseline = baseline_of(series(WITH_OUTLIER))

    assert baseline.sample_count == 6
    assert baseline.statistics.maximum == 120.0
    assert baseline.statistics.mean == 70.0
    # The robust statistics barely move.
    assert baseline.statistics.median == 61.0
    assert baseline.statistics.median_absolute_deviation == 3.0
    notes = baseline.data_quality.notes
    assert "Potential statistical outliers among the 6 admitted values: 1" in notes
    assert "absolute modified z-score above 3.5; Iglewicz and Hoaglin, 1993" in notes
    assert "kept in the statistics" in notes
    assert "neither a measurement error nor a health condition" in notes


def test_a_potential_outlier_is_not_a_data_quality_issue() -> None:
    quality = baseline_of(series(WITH_OUTLIER)).data_quality

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.flags == []
    assert quality.score == 1.0


def test_potential_outliers_can_be_excluded() -> None:
    config = BaselineConfig(outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series(WITH_OUTLIER), config=config)

    assert baseline.sample_count == 5
    assert baseline.statistics == baseline_of(series(FIVE_VALUES)).statistics
    assert "excluded from the statistics" in baseline.data_quality.notes


def test_potential_outliers_are_found_on_both_sides_of_the_median() -> None:
    # Median 59, MAD 3: the modified z-score of 2 is 0.6745 * -57 / 3, about -12.8.
    config = BaselineConfig(outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series([*FIVE_VALUES, 2.0]), config=config)

    assert baseline.sample_count == 5
    assert baseline.statistics.minimum == 56.0
    assert "admitted values: 1" in baseline.data_quality.notes


def test_outliers_are_screened_once() -> None:
    # Median 60, MAD 2: the modified z-score of 150 is about 30.4 and that of 69 is about
    # 3.04, below the cut-off. Without 150 the MAD falls to 1 and the score of 69 doubles
    # to about 6.07: a second screening would remove it too, and narrow the baseline.
    values = [58.0, 58.0, 60.0, 60.0, 60.0, 69.0, 150.0]
    config = BaselineConfig(outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series(values), config=config)

    assert "admitted values: 1" in baseline.data_quality.notes
    assert baseline.sample_count == 6
    assert baseline.statistics.maximum == 69.0
    assert baseline.statistics.median_absolute_deviation == 1.0


def test_the_outlier_cutoff_is_configurable() -> None:
    lenient = BaselineConfig(outlier_cutoff=20.0, outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series(WITH_OUTLIER), config=lenient)

    assert baseline.sample_count == 6
    assert "outliers" not in baseline.data_quality.notes


def test_outlier_screening_can_be_disabled() -> None:
    config = BaselineConfig(outlier_cutoff=None, outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series(WITH_OUTLIER), config=config)

    assert baseline.sample_count == 6
    assert "the screening is disabled" in baseline.data_quality.notes


def test_excluding_outliers_can_leave_too_few_values() -> None:
    config = BaselineConfig(minimum_samples=3, outlier_handling=OutlierHandling.EXCLUDE)

    baseline = baseline_of(series([58.0, 59.0, 300.0]), config=config)

    assert baseline.status is BaselineStatus.INSUFFICIENT_DATA
    assert baseline.sample_count == 2
    assert baseline.statistics == BaselineStatistics()
    assert baseline.data_quality.flags == [QualityFlag.INSUFFICIENT_SAMPLES]


# --- Data quality of the reference data --------------------------------------------


def test_unusable_measurements_never_enter_a_baseline() -> None:
    batch = [
        *series(FIVE_VALUES),
        measurement(-10.0, T0 + 6 * DAY),  # impossible by definition
        measurement(58.0, T0 + DAY),  # redundant copy of the second value
        measurement(61.0, T0 + 7 * DAY),  # two records of one observation ...
        measurement(99.0, T0 + 7 * DAY),  # ... that disagree
    ]

    baseline = baseline_of(batch)

    assert baseline.sample_count == 5
    assert baseline.statistics == baseline_of(series(FIVE_VALUES)).statistics
    quality = baseline.data_quality
    assert quality.status is QualityStatus.DEGRADED
    assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT, QualityFlag.DUPLICATE]
    assert "9 records in the window: 5 acceptable, 0 degraded, 4 unusable" in quality.notes
    assert "Records not admitted to the baseline: 4 of 9" in quality.notes


def test_degraded_measurements_are_left_out_unless_admitted() -> None:
    quality = DataQualityConfig(
        sensor_ranges={
            DEVICE: {MetricType.HEART_RATE: SensorRange(40.0, 100.0, "Synthetic range for tests")}
        }
    )
    batch = [*series(FIVE_VALUES), measurement(150.0, T0 + 6 * DAY)]

    conservative = baseline_of(batch, config=BaselineConfig(quality=quality))
    permissive = baseline_of(
        batch,
        config=BaselineConfig(
            quality=quality,
            admitted_quality=frozenset({QualityStatus.ACCEPTABLE, QualityStatus.DEGRADED}),
        ),
    )

    assert conservative.sample_count == 5
    assert conservative.statistics.maximum == 64.0
    assert "Records not admitted to the baseline: 1 of 6" in conservative.data_quality.notes
    assert permissive.sample_count == 6
    assert permissive.statistics.maximum == 150.0
    assert QualityFlag.OUT_OF_SENSOR_RANGE in permissive.data_quality.flags


def test_completeness_of_the_reference_data_is_reported() -> None:
    daily = DataQualityConfig(expected_intervals={MetricType.HEART_RATE: DAY})

    baseline = baseline_of(series(FIVE_VALUES), config=BaselineConfig(quality=daily))

    assert baseline.data_quality.completeness == pytest.approx(5 / 30)
    assert baseline.data_quality.flags == [QualityFlag.MISSING_DATA]
    assert baseline.data_quality.status is QualityStatus.DEGRADED
    # Data quality and baseline status are separate notions.
    assert baseline.status is BaselineStatus.PROVISIONAL


def test_a_baseline_built_from_simulated_data_says_so() -> None:
    simulated = baseline_of(series(FIVE_VALUES))
    recorded = baseline_of(series(FIVE_VALUES, source=MeasurementSource.WEARABLE))

    assert "Simulated (synthetic) records: 5 of 5." in simulated.data_quality.notes
    assert "Simulated" not in recorded.data_quality.notes


# --- Determinism -------------------------------------------------------------------


def test_the_same_input_gives_the_same_baseline() -> None:
    batch = [*series(WITH_OUTLIER), measurement(58.0, T0 + DAY)]

    assert baseline_of(batch) == baseline_of(batch)


def test_the_order_of_the_input_does_not_matter() -> None:
    batch = [
        *series(WITH_OUTLIER),
        measurement(58.0, T0 + DAY, measurement_id="meas-copy"),
        *series([70.0, 72.0], start=IN_FLIGHT_START),
    ]
    reordered = batch[::-1]

    assert build_baselines(reordered, timeline()[::-1], computed_at=NOW) == build_baselines(
        batch, timeline(), computed_at=NOW
    )


def test_the_time_span_does_not_depend_on_the_order_or_the_identifiers() -> None:
    # Identifiers sort in the opposite order of the measurement times.
    batch = [
        measurement(value, T0 + day * DAY, measurement_id=f"meas-span-{9 - day}")
        for day, value in enumerate(FIVE_VALUES)
    ]
    config = BaselineConfig(established_min_span=4 * DAY)

    for ordering in (batch, batch[::-1]):
        baseline = baseline_of(ordering, config=config)
        assert baseline.status is BaselineStatus.ESTABLISHED
        assert "5 values spanning 4 days were used" in baseline.data_quality.notes


def test_the_identifier_follows_the_content() -> None:
    first = baseline_of(series(FIVE_VALUES))
    same_values = baseline_of(series(FIVE_VALUES))
    other_values = baseline_of(series([56.0, 58.0, 60.0, 62.0, 65.0]))
    later = baseline_of(series(FIVE_VALUES), computed_at=NOW + DAY)

    assert first.baseline_id == same_values.baseline_id
    assert len({first.baseline_id, other_values.baseline_id, later.baseline_id}) == 3
    assert 1 <= len(first.baseline_id) <= 128


def test_times_in_another_time_zone_give_the_same_baseline() -> None:
    two_hours_ahead = timezone(timedelta(hours=2))

    assert baseline_of(
        series(FIVE_VALUES), computed_at=NOW.astimezone(two_hours_ahead)
    ) == baseline_of(series(FIVE_VALUES), computed_at=NOW)


# --- Wording and configuration -----------------------------------------------------

FORBIDDEN_WORDS = ("diagnos", "abnormal", "disease", "patholog", "nominal", "alert", "attention")


def test_notes_describe_data_and_never_read_as_a_diagnosis() -> None:
    quality = DataQualityConfig(expected_intervals={MetricType.HEART_RATE: DAY})
    scenarios = [
        baseline_of(series(values), config=BaselineConfig(quality=quality, **settings))
        for values in ([], [58.0], [70.0] * 6, FIVE_VALUES, WITH_OUTLIER)
        for settings in (
            {},
            {"established_min_samples": 5, "outlier_handling": OutlierHandling.EXCLUDE},
        )
    ]

    for baseline in scenarios:
        notes = baseline.data_quality.notes.lower()
        assert not [word for word in FORBIDDEN_WORDS if word in notes]


def test_settings_given_as_plain_values_are_not_silently_ignored() -> None:
    config = BaselineConfig(outlier_handling="exclude", admitted_quality={"acceptable", "degraded"})

    assert config.outlier_handling is OutlierHandling.EXCLUDE
    assert config.admitted_quality == frozenset({QualityStatus.ACCEPTABLE, QualityStatus.DEGRADED})
    assert baseline_of(series(WITH_OUTLIER), config=config).sample_count == 5

    with pytest.raises(ValueError, match="not a valid OutlierHandling"):
        BaselineConfig(outlier_handling="delete")


def test_the_default_configuration_is_conservative() -> None:
    config = BaselineConfig()

    assert config.admitted_quality == frozenset({QualityStatus.ACCEPTABLE})
    assert config.minimum_samples == 2
    # No sourced criterion exists, so none is configured.
    assert config.established_min_samples is None
    assert config.established_min_span is None
    assert config.outlier_cutoff == 3.5
    assert config.outlier_handling is OutlierHandling.REPORT
    assert config.quality == DataQualityConfig()


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"minimum_samples": 1}, "at least 2"),
        ({"minimum_samples": 5, "established_min_samples": 4}, "must not be lower"),
        ({"established_min_span": timedelta(0)}, "must be positive"),
        ({"outlier_cutoff": 0.0}, "positive number"),
        ({"outlier_cutoff": float("inf")}, "positive number"),
        ({"admitted_quality": frozenset()}, "non-empty subset"),
        ({"admitted_quality": frozenset({QualityStatus.UNUSABLE})}, "non-empty subset"),
        ({"admitted_quality": frozenset({QualityStatus.NOT_ASSESSED})}, "non-empty subset"),
    ],
)
def test_invalid_settings_are_rejected(settings: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        BaselineConfig(**settings)
