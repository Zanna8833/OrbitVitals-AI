"""Data Quality Engine. All measurements are synthetic."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from jsonschema import Draft202012Validator

from app.algorithms.data_quality import (
    ALGORITHM,
    DEFINITION_BOUNDS,
    INTERVAL_BOUNDED_DURATIONS,
    METRICS_WITHOUT_DEFINITION_BOUND,
    DataQualityConfig,
    SensorRange,
    assess_measurements,
    assess_window,
    format_duration,
    summarize_series,
)
from app.models import (
    METRIC_CATALOG,
    DataQuality,
    EvaluationStatus,
    MeasurementSource,
    MetricType,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from tests.algorithms.builders import CREW, DAY, DEVICE, HOUR, T0, measurement, series
from tests.support import load_schema

NOW = T0 + 100 * DAY

SYSTOLIC = MetricType.SYSTOLIC_BLOOD_PRESSURE
DIASTOLIC = MetricType.DIASTOLIC_BLOOD_PRESSURE

# Synthetic measuring range, used only to exercise the check.
TEST_RANGE = SensorRange(minimum=40.0, maximum=100.0, source="Synthetic range for tests")
RANGE_CONFIG = DataQualityConfig(sensor_ranges={DEVICE: {MetricType.HEART_RATE: TEST_RANGE}})
HOURLY = DataQualityConfig(expected_intervals={MetricType.HEART_RATE: HOUR})


def quality_by_id(
    batch: list[PhysiologicalMeasurement], config: DataQualityConfig | None = None
) -> dict[str, DataQuality]:
    assessed = assess_measurements(batch, assessed_at=NOW, config=config)
    return {item.measurement_id: item.data_quality for item in assessed}


def quality_of(
    item: PhysiologicalMeasurement, config: DataQualityConfig | None = None
) -> DataQuality:
    return quality_by_id([item], config)[item.measurement_id]


def window_quality(
    batch: list[PhysiologicalMeasurement],
    config: DataQualityConfig | None = HOURLY,
    *,
    hours: int = 6,
    assessed_at: datetime = NOW,
) -> DataQuality:
    return assess_window(
        batch,
        crew_member_id=CREW,
        metric=MetricType.HEART_RATE,
        window_start=T0,
        window_end=T0 + hours * HOUR,
        assessed_at=assessed_at,
        config=config,
    )


# --- Single measurements -----------------------------------------------------------


def test_a_measurement_without_issue_is_acceptable() -> None:
    quality = quality_of(measurement(58.0))

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.flags == []
    assert quality.notes is None
    assert quality.score is None
    assert quality.completeness is None
    assert quality.algorithm == ALGORITHM
    assert quality.assessed_at == NOW


def test_assessment_returns_copies_in_input_order_and_leaves_the_input_untouched() -> None:
    batch = series([58.0, 59.0, 60.0])

    assessed = assess_measurements(batch, assessed_at=NOW)

    assert [item.measurement_id for item in assessed] == [item.measurement_id for item in batch]
    assert [item.value for item in assessed] == [58.0, 59.0, 60.0]
    assert all(item.data_quality is None for item in batch)
    assert all(item.data_quality is not None for item in assessed)


def test_assessment_replaces_an_earlier_one_and_is_idempotent() -> None:
    batch = [measurement(58.0), measurement(-1.0, T0 + HOUR)]

    once = assess_measurements(batch, assessed_at=NOW)
    twice = assess_measurements(once, assessed_at=NOW)

    assert twice == once


def test_assessment_output_matches_the_published_schema() -> None:
    validator = Draft202012Validator(load_schema("physiological_measurement"))

    for item in assess_measurements([measurement(58.0), measurement(-1.0)], assessed_at=NOW):
        validator.validate(item.model_dump(mode="json"))


def test_assessment_time_is_reported_in_utc() -> None:
    rome = timezone(timedelta(hours=1))

    assessed = assess_measurements(
        [measurement(58.0)], assessed_at=datetime(2026, 12, 1, 10, 0, tzinfo=rome)
    )

    assert assessed[0].data_quality.assessed_at == datetime(2026, 12, 1, 9, 0, tzinfo=UTC)
    assert assessed[0].data_quality.assessed_at.utcoffset() == timedelta(0)


def test_assessment_time_must_carry_a_time_zone() -> None:
    with pytest.raises(ValueError, match="assessed_at must carry a time zone"):
        assess_measurements([measurement(58.0)], assessed_at=datetime(2026, 12, 1))


# Definition bounds


def test_every_metric_is_either_bounded_by_its_definition_or_listed_as_unbounded() -> None:
    assert set(DEFINITION_BOUNDS) | METRICS_WITHOUT_DEFINITION_BOUND == set(MetricType)
    assert set(DEFINITION_BOUNDS).isdisjoint(METRICS_WITHOUT_DEFINITION_BOUND)


def test_definition_bounds_are_limited_to_zero_and_one_hundred_percent() -> None:
    # Guards against a clinical threshold slipping into the definition bounds.
    for metric, (lower, upper) in DEFINITION_BOUNDS.items():
        assert lower == 0.0
        assert upper is None or (upper == 100.0 and METRIC_CATALOG[metric].unit == "%")


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        (MetricType.HEART_RATE, -1.0),
        (MetricType.SLEEP_DURATION, -30.0),
        (MetricType.BLOOD_OXYGEN_SATURATION, 100.5),
        (MetricType.SLEEP_EFFICIENCY, 120.0),
        (MetricType.BODY_MASS, -0.5),
    ],
)
def test_a_value_impossible_by_definition_is_an_unusable_artifact(
    metric: MetricType, value: float
) -> None:
    quality = quality_of(measurement(value, metric=metric))

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT]
    assert "impossible" in quality.notes
    assert metric.value in quality.notes


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        (MetricType.HEART_RATE, 0.0),
        (MetricType.BLOOD_OXYGEN_SATURATION, 0.0),
        (MetricType.BLOOD_OXYGEN_SATURATION, 100.0),
        (MetricType.BODY_TEMPERATURE, -5.0),
        (MetricType.SYSTOLIC_BLOOD_PRESSURE, -5.0),
    ],
)
def test_a_value_allowed_by_definition_is_not_an_artifact(metric: MetricType, value: float) -> None:
    assert quality_of(measurement(value, metric=metric)).status is QualityStatus.ACCEPTABLE


@pytest.mark.parametrize("value", [1.0, 30.0, 250.0, 100000.0])
def test_an_unusual_value_is_never_a_data_quality_issue(value: float) -> None:
    # No clinical threshold: without a documented sensor range, how high or how low a
    # value is says nothing about the quality of the data.
    quality = quality_of(measurement(value, metric=MetricType.HEART_RATE))

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.flags == []


# Sensor range


@pytest.mark.parametrize("value", [39.9, 100.1, 250.0])
def test_a_value_outside_the_documented_sensor_range_is_degraded(value: float) -> None:
    quality = quality_of(measurement(value), RANGE_CONFIG)

    assert quality.status is QualityStatus.DEGRADED
    assert quality.flags == [QualityFlag.OUT_OF_SENSOR_RANGE]
    assert "40 to 100 bpm" in quality.notes
    assert TEST_RANGE.source in quality.notes


@pytest.mark.parametrize("value", [40.0, 58.0, 100.0])
def test_a_value_inside_the_sensor_range_is_acceptable(value: float) -> None:
    assert quality_of(measurement(value), RANGE_CONFIG).status is QualityStatus.ACCEPTABLE


def test_the_sensor_range_applies_to_its_device_and_metric_only() -> None:
    other_device = measurement(250.0, device_id="sim-device-02")
    no_device = measurement(250.0, device_id=None)
    other_metric = measurement(250.0, metric=MetricType.RESPIRATORY_RATE)

    for item in (other_device, no_device, other_metric):
        assert quality_of(item, RANGE_CONFIG).status is QualityStatus.ACCEPTABLE


@pytest.mark.parametrize(
    ("minimum", "maximum", "source", "message"),
    [
        (100.0, 40.0, "Synthetic", "must not exceed"),
        (float("nan"), 40.0, "Synthetic", "finite"),
        (40.0, float("inf"), "Synthetic", "finite"),
        (40.0, 100.0, "", "cite"),
        (40.0, 100.0, "   ", "cite"),
    ],
)
def test_a_sensor_range_must_be_well_formed_and_cite_its_source(
    minimum: float, maximum: float, source: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        SensorRange(minimum=minimum, maximum=maximum, source=source)


# Duration against its observation interval


@pytest.mark.parametrize("metric", sorted(INTERVAL_BOUNDED_DURATIONS))
def test_interval_bounded_durations_are_expressed_in_minutes(metric: MetricType) -> None:
    assert METRIC_CATALOG[metric].unit == "min"


@pytest.mark.parametrize("metric", sorted(INTERVAL_BOUNDED_DURATIONS))
def test_a_duration_longer_than_its_interval_is_an_unusable_artifact(metric: MetricType) -> None:
    quality = quality_of(measurement(481.0, metric=metric, interval_end=T0 + 8 * HOUR))

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT]
    assert "longer than the observation interval" in quality.notes
    assert "480 min" in quality.notes


def test_a_duration_that_fills_its_interval_is_acceptable() -> None:
    item = measurement(480.0, metric=MetricType.SLEEP_DURATION, interval_end=T0 + 8 * HOUR)

    assert quality_of(item).status is QualityStatus.ACCEPTABLE


def test_the_interval_tolerance_absorbs_rounded_timestamps() -> None:
    item = measurement(480.5, metric=MetricType.SLEEP_DURATION, interval_end=T0 + 8 * HOUR)
    tolerant = DataQualityConfig(interval_tolerance=timedelta(minutes=1))

    assert quality_of(item).status is QualityStatus.UNUSABLE
    assert quality_of(item, tolerant).status is QualityStatus.ACCEPTABLE


def test_the_interval_check_needs_an_interval_and_a_duration_metric() -> None:
    instantaneous = measurement(481.0, metric=MetricType.SLEEP_DURATION)
    not_a_duration = measurement(481.0, metric=MetricType.ENERGY_INTAKE, interval_end=T0 + HOUR)

    assert quality_of(instantaneous).status is QualityStatus.ACCEPTABLE
    assert quality_of(not_a_duration).status is QualityStatus.ACCEPTABLE


# Timestamps


def test_a_timestamp_after_the_assessment_time_is_unusable_without_a_flag() -> None:
    quality = quality_of(measurement(58.0, NOW + timedelta(seconds=1)))

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == []  # the contract has no flag for an inconsistent timestamp
    assert "later than the assessment time" in quality.notes


def test_an_interval_that_ends_after_the_assessment_time_is_unusable() -> None:
    item = measurement(
        400.0, NOW - 7 * HOUR, metric=MetricType.SLEEP_DURATION, interval_end=NOW + HOUR
    )

    assert quality_of(item).status is QualityStatus.UNUSABLE


def test_a_timestamp_at_the_assessment_time_is_acceptable() -> None:
    assert quality_of(measurement(58.0, NOW)).status is QualityStatus.ACCEPTABLE


def test_the_clock_tolerance_absorbs_clock_differences() -> None:
    item = measurement(58.0, NOW + timedelta(seconds=30))
    tolerant = DataQualityConfig(clock_tolerance=timedelta(minutes=1))

    assert quality_of(item, tolerant).status is QualityStatus.ACCEPTABLE


# Duplicates


@pytest.mark.parametrize("reverse", [False, True])
def test_identical_copies_keep_one_record_whatever_the_order(reverse: bool) -> None:
    batch = [measurement(58.0, measurement_id="meas-a"), measurement(58.0, measurement_id="meas-b")]

    quality = quality_by_id(batch[::-1] if reverse else batch)

    assert quality["meas-a"].status is QualityStatus.ACCEPTABLE
    assert quality["meas-a"].flags == []
    assert quality["meas-b"].status is QualityStatus.UNUSABLE
    assert quality["meas-b"].flags == [QualityFlag.DUPLICATE]
    assert "Redundant copy of measurement 'meas-a'" in quality["meas-b"].notes


def test_a_record_received_twice_keeps_one_copy() -> None:
    item = measurement(58.0)

    first, second = assess_measurements([item, item.model_copy()], assessed_at=NOW)

    assert first.data_quality.status is QualityStatus.ACCEPTABLE
    assert second.data_quality.status is QualityStatus.UNUSABLE
    assert second.data_quality.flags == [QualityFlag.DUPLICATE]
    assert "received more than once" in second.data_quality.notes


def test_three_identical_copies_keep_exactly_one() -> None:
    batch = [measurement(58.0) for _ in range(3)]

    statuses = [quality.status for quality in quality_by_id(batch).values()]

    assert statuses.count(QualityStatus.ACCEPTABLE) == 1
    assert statuses.count(QualityStatus.UNUSABLE) == 2


def test_records_of_one_observation_that_disagree_are_all_unusable() -> None:
    batch = [measurement(58.0), measurement(71.0), measurement(58.0)]

    for quality in quality_by_id(batch).values():
        assert quality.status is QualityStatus.UNUSABLE
        assert quality.flags == [QualityFlag.DUPLICATE]
        assert "3 records describe this observation" in quality.notes
        assert "true value cannot be determined" in quality.notes


def test_a_shared_identifier_with_different_content_is_unusable() -> None:
    batch = [
        measurement(58.0, T0, measurement_id="meas-shared"),
        measurement(59.0, T0 + HOUR, measurement_id="meas-shared"),
    ]

    for item in assess_measurements(batch, assessed_at=NOW):
        assert item.data_quality.status is QualityStatus.UNUSABLE
        assert item.data_quality.flags == [QualityFlag.DUPLICATE]
        assert "measurement_id is shared by 2 records" in item.data_quality.notes


@pytest.mark.parametrize(
    "other",
    [
        {"at": T0 + timedelta(seconds=1)},
        {"device_id": "sim-device-02"},
        {"device_id": None},
        {"crew_member_id": "crew-test-002"},
        {"metric": MetricType.RESPIRATORY_RATE},
        {"source": MeasurementSource.MANUAL_ENTRY},
        {"metric": MetricType.SLEEP_DURATION, "interval_end": T0 + 8 * HOUR},
    ],
)
def test_distinct_observations_are_not_duplicates(other: dict) -> None:
    batch = [measurement(58.0), measurement(58.0, **other)]

    assert all(
        quality.status is QualityStatus.ACCEPTABLE for quality in quality_by_id(batch).values()
    )


def test_the_same_instant_in_another_time_zone_is_the_same_observation() -> None:
    rome = timezone(timedelta(hours=2))
    batch = [measurement(58.0, T0), measurement(58.0, T0.astimezone(rome))]

    statuses = sorted(quality.status for quality in quality_by_id(batch).values())

    assert statuses == [QualityStatus.ACCEPTABLE, QualityStatus.UNUSABLE]


# Blood pressure


def blood_pressure(systolic: float, diastolic: float, **fields: object) -> list:
    return [
        measurement(systolic, metric=SYSTOLIC, **fields),
        measurement(diastolic, metric=DIASTOLIC, **fields),
    ]


def test_a_diastolic_value_above_the_systolic_value_makes_the_reading_unusable() -> None:
    for quality in quality_by_id(blood_pressure(80.0, 120.0)).values():
        assert quality.status is QualityStatus.UNUSABLE
        assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT]
        assert "contradicts their definitions" in quality.notes


@pytest.mark.parametrize(("systolic", "diastolic"), [(120.0, 80.0), (100.0, 100.0)])
def test_a_reading_that_respects_the_definitions_is_acceptable(
    systolic: float, diastolic: float
) -> None:
    assert all(
        quality.status is QualityStatus.ACCEPTABLE
        for quality in quality_by_id(blood_pressure(systolic, diastolic)).values()
    )


def test_blood_pressure_values_are_paired_within_one_reading_only() -> None:
    separate_times = [
        measurement(80.0, T0, metric=SYSTOLIC),
        measurement(120.0, T0 + HOUR, metric=DIASTOLIC),
    ]
    separate_people = [
        measurement(80.0, metric=SYSTOLIC),
        measurement(120.0, metric=DIASTOLIC, crew_member_id="crew-test-002"),
    ]
    separate_devices = [
        measurement(80.0, metric=SYSTOLIC),
        measurement(120.0, metric=DIASTOLIC, device_id="sim-device-02"),
    ]

    for batch in (separate_times, separate_people, separate_devices):
        assert all(
            quality.status is QualityStatus.ACCEPTABLE for quality in quality_by_id(batch).values()
        )


def test_a_redundant_copy_does_not_hide_an_inconsistent_reading() -> None:
    batch = [*blood_pressure(80.0, 120.0), measurement(80.0, metric=SYSTOLIC)]

    assert all(
        QualityFlag.SIGNAL_ARTIFACT in quality.flags for quality in quality_by_id(batch).values()
    )


# Several issues at once


def test_issues_accumulate_in_a_stable_order() -> None:
    item = measurement(-5.0, NOW + HOUR)

    quality = quality_of(item, RANGE_CONFIG)

    assert quality.status is QualityStatus.UNUSABLE
    # Flags follow the order of the contract enumeration.
    assert quality.flags == [QualityFlag.OUT_OF_SENSOR_RANGE, QualityFlag.SIGNAL_ARTIFACT]
    assert quality.notes.index("impossible") < quality.notes.index("measuring range")
    assert quality.notes.index("measuring range") < quality.notes.index("assessment time")


def test_data_quality_never_uses_the_vocabulary_of_the_physiological_status() -> None:
    batch = [
        measurement(-5.0, NOW + HOUR),
        measurement(250.0),
        measurement(250.0),
        *blood_pressure(80.0, 120.0),
    ]
    statuses = {status.value for status in EvaluationStatus}

    for quality in quality_by_id(batch, RANGE_CONFIG).values():
        assert quality.status.value not in statuses
        assert not statuses & set(quality.notes.lower().replace(".", " ").split())


# --- Configuration -----------------------------------------------------------------


def test_the_default_configuration_holds_no_device_or_protocol_fact() -> None:
    config = DataQualityConfig()

    assert config.sensor_ranges == {}
    assert config.expected_intervals == {}
    # Strictest values: any missing sample or flagged record degrades a window.
    assert config.clock_tolerance == timedelta(0)
    assert config.interval_tolerance == timedelta(0)
    assert config.minimum_usable_samples == 1
    assert config.acceptable_min_completeness == 1.0
    assert config.acceptable_max_flagged_fraction == 0.0


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"expected_intervals": {MetricType.HEART_RATE: timedelta(0)}}, "must be positive"),
        ({"clock_tolerance": timedelta(seconds=-1)}, "must not be negative"),
        ({"interval_tolerance": timedelta(seconds=-1)}, "must not be negative"),
        ({"minimum_usable_samples": 0}, "at least 1"),
        ({"acceptable_min_completeness": 1.5}, "between 0 and 1"),
        ({"acceptable_max_flagged_fraction": -0.1}, "between 0 and 1"),
    ],
)
def test_invalid_settings_are_rejected(settings: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        DataQualityConfig(**settings)


@pytest.mark.parametrize(
    ("duration", "text"),
    [
        (timedelta(days=1), "1 day"),
        (timedelta(days=14), "14 days"),
        (timedelta(hours=36), "36 hours"),
        (timedelta(minutes=5), "5 minutes"),
        (timedelta(minutes=90), "90 minutes"),
        (timedelta(seconds=1.5), "1.5 seconds"),
        (timedelta(0), "0 seconds"),
    ],
)
def test_durations_are_rendered_in_the_largest_exact_unit(duration: timedelta, text: str) -> None:
    assert format_duration(duration) == text


# --- Windows -----------------------------------------------------------------------


def test_a_complete_window_without_issue_is_acceptable() -> None:
    quality = window_quality(series([58.0] * 6, step=HOUR))

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.completeness == 1.0
    assert quality.score == 1.0
    assert quality.flags == []
    assert "6 distinct observation times for 6 expected (one every 1 hour)" in quality.notes
    assert quality.algorithm == ALGORITHM
    assert quality.assessed_at == NOW


def test_missing_samples_degrade_the_window() -> None:
    present = [measurement(58.0, T0 + hour * HOUR) for hour in (0, 1, 4, 5)]

    quality = window_quality(present)

    assert quality.status is QualityStatus.DEGRADED
    assert quality.flags == [QualityFlag.MISSING_DATA]
    assert quality.completeness == pytest.approx(4 / 6)
    assert quality.score == pytest.approx(4 / 6)
    assert "4 distinct observation times for 6 expected" in quality.notes
    assert "Longest interval without an observation: 3 hours" in quality.notes


def test_an_empty_window_with_an_expectation_is_unusable_and_reports_missing_data() -> None:
    quality = window_quality([])

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.MISSING_DATA, QualityFlag.INSUFFICIENT_SAMPLES]
    assert quality.completeness == 0.0
    assert quality.score == 0.0
    assert "No record in the window." in quality.notes
    assert "0 usable values, fewer than the 1 required" in quality.notes


def test_an_empty_window_without_an_expectation_cannot_report_completeness() -> None:
    quality = window_quality([], config=None)

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.INSUFFICIENT_SAMPLES]
    assert quality.completeness is None
    assert quality.score is None
    assert "no expected sampling interval is configured for heart_rate" in quality.notes


def test_without_an_expected_interval_completeness_is_not_assessed() -> None:
    quality = window_quality(series([58.0, 59.0], step=HOUR), config=None)

    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.completeness is None
    assert quality.score == 1.0
    assert QualityFlag.MISSING_DATA not in quality.flags
    assert "Completeness is not assessed" in quality.notes


def test_a_window_shorter_than_the_sampling_interval_has_no_completeness() -> None:
    daily = DataQualityConfig(expected_intervals={MetricType.HEART_RATE: DAY})

    quality = window_quality([measurement(58.0)], daily)

    assert quality.completeness is None
    assert quality.status is QualityStatus.ACCEPTABLE
    assert "shorter than the expected sampling interval (1 day)" in quality.notes


def test_duplicates_do_not_inflate_completeness() -> None:
    present = [measurement(58.0, T0 + hour * HOUR) for hour in (0, 0, 0, 1, 2)]

    quality = window_quality(present)

    assert quality.completeness == pytest.approx(3 / 6)
    assert quality.score == pytest.approx(3 / 6)
    assert quality.flags == [QualityFlag.MISSING_DATA, QualityFlag.DUPLICATE]
    assert "5 records in the window: 3 acceptable, 0 degraded, 2 unusable" in quality.notes
    assert "Records per flag: duplicate 2." in quality.notes


def test_unusable_records_lower_the_score_but_not_the_completeness() -> None:
    batch = series([58.0, 59.0, -1.0, 60.0, 61.0, 62.0], step=HOUR)

    quality = window_quality(batch)

    assert quality.completeness == 1.0
    assert quality.score == pytest.approx(5 / 6)
    assert quality.status is QualityStatus.DEGRADED
    assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT]


def test_more_observations_than_expected_do_not_push_the_score_above_one() -> None:
    batch = series([58.0] * 12, step=timedelta(minutes=30))

    quality = window_quality(batch)

    assert quality.completeness == 1.0
    assert quality.score == 1.0


def test_a_window_whose_records_are_all_unusable_is_unusable() -> None:
    quality = window_quality(series([-1.0, -2.0], step=HOUR), config=None)

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.SIGNAL_ARTIFACT, QualityFlag.INSUFFICIENT_SAMPLES]
    assert quality.score == 0.0


def test_a_window_with_only_degraded_records_is_degraded() -> None:
    quality = window_quality(series([250.0, 260.0], step=HOUR), RANGE_CONFIG)

    assert quality.status is QualityStatus.DEGRADED
    assert quality.flags == [QualityFlag.OUT_OF_SENSOR_RANGE]
    assert quality.score == 0.0


def test_the_window_selects_one_crew_member_one_metric_and_a_half_open_period() -> None:
    batch = [
        measurement(58.0, T0),  # the start is included
        measurement(58.0, T0 + 6 * HOUR),  # the end is excluded
        measurement(58.0, T0 - HOUR),
        measurement(58.0, T0 + HOUR, crew_member_id="crew-test-002"),
        measurement(14.0, T0 + HOUR, metric=MetricType.RESPIRATORY_RATE),
    ]

    quality = window_quality(batch, config=None)

    assert quality.notes.startswith("1 record in the window")


def test_records_outside_the_window_still_reveal_inconsistencies_inside_it() -> None:
    # The diastolic value belongs to another series, yet it exposes the systolic value.
    batch = [measurement(80.0, metric=SYSTOLIC), measurement(120.0, metric=DIASTOLIC)]

    quality = assess_window(
        batch,
        crew_member_id=CREW,
        metric=SYSTOLIC,
        window_start=T0,
        window_end=T0 + HOUR,
        assessed_at=NOW,
    )

    assert quality.status is QualityStatus.UNUSABLE
    assert QualityFlag.SIGNAL_ARTIFACT in quality.flags


def test_samples_are_not_expected_after_the_assessment_time() -> None:
    batch = series([58.0] * 3, step=HOUR)

    quality = window_quality(batch, assessed_at=T0 + 3 * HOUR)

    assert quality.completeness == 1.0
    assert "3 distinct observation times for 3 expected" in quality.notes
    assert quality.status is QualityStatus.ACCEPTABLE


def test_relaxed_limits_accept_a_window_and_still_report_its_flags() -> None:
    batch = [*series([58.0] * 5, step=HOUR), measurement(58.0, T0)]
    relaxed = DataQualityConfig(
        expected_intervals={MetricType.HEART_RATE: HOUR},
        acceptable_min_completeness=0.8,
        acceptable_max_flagged_fraction=0.2,
    )

    assert window_quality(batch).status is QualityStatus.DEGRADED

    quality = window_quality(batch, relaxed)
    assert quality.status is QualityStatus.ACCEPTABLE
    assert quality.flags == [QualityFlag.MISSING_DATA, QualityFlag.DUPLICATE]


def test_the_minimum_number_of_usable_samples_is_configurable() -> None:
    strict = DataQualityConfig(minimum_usable_samples=3)

    quality = window_quality(series([58.0, 59.0], step=HOUR), strict)

    assert quality.status is QualityStatus.UNUSABLE
    assert quality.flags == [QualityFlag.INSUFFICIENT_SAMPLES]
    assert "2 usable values, fewer than the 3 required" in quality.notes


def test_the_window_labels_simulated_data_and_unchecked_sensor_ranges() -> None:
    simulated = window_quality(series([58.0, 59.0], step=HOUR), config=None)
    recorded = window_quality(
        series([58.0, 59.0], step=HOUR, source=MeasurementSource.WEARABLE), RANGE_CONFIG
    )

    assert "Simulated (synthetic) records: 2 of 2." in simulated.notes
    assert "Records not checked against a sensor range: 2 of 2" in simulated.notes
    assert "Simulated" not in recorded.notes
    assert "sensor range" not in recorded.notes


def test_window_output_matches_the_published_schema() -> None:
    validator = Draft202012Validator(load_schema("data_quality"))

    for batch in ([], series([58.0, -1.0, 59.0], step=HOUR)):
        validator.validate(window_quality(batch).model_dump(mode="json"))


def test_a_window_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="window_end must not be earlier"):
        assess_window(
            [],
            crew_member_id=CREW,
            metric=MetricType.HEART_RATE,
            window_start=T0,
            window_end=T0 - HOUR,
            assessed_at=NOW,
        )


def test_window_bounds_must_carry_a_time_zone() -> None:
    with pytest.raises(ValueError, match="window_start must carry a time zone"):
        assess_window(
            [],
            crew_member_id=CREW,
            metric=MetricType.HEART_RATE,
            window_start=datetime(2026, 9, 1),
            window_end=T0,
            assessed_at=NOW,
        )


def test_summarize_series_refuses_measurements_that_were_not_assessed() -> None:
    with pytest.raises(ValueError, match="returned by assess_measurements"):
        summarize_series(
            [measurement(58.0)],
            metric=MetricType.HEART_RATE,
            periods=[(T0, T0 + HOUR)],
            assessed_at=NOW,
        )


def test_summarize_series_covers_several_periods() -> None:
    periods = [(T0, T0 + 2 * HOUR), (T0 + 10 * HOUR, T0 + 12 * HOUR)]
    batch = [measurement(58.0, T0), measurement(58.0, T0 + HOUR), measurement(58.0, T0 + 10 * HOUR)]

    quality = summarize_series(
        assess_measurements(batch, assessed_at=NOW),
        metric=MetricType.HEART_RATE,
        periods=periods,
        assessed_at=NOW,
        config=HOURLY,
    )

    assert quality.completeness == pytest.approx(3 / 4)
    # The time between the two periods is not a gap: only the second period has one.
    assert "Longest interval without an observation: 2 hours" in quality.notes
