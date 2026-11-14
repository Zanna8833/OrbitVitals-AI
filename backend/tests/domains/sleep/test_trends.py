"""Time-aware trends and selection behavior on explicitly simulated sleep records."""

from dataclasses import replace
from datetime import UTC, timedelta, timezone
from math import isfinite
from typing import Any

import pytest

from app.domains.sleep import TrendSignal
from app.domains.sleep.demo import demonstration_config, demonstration_scenarios
from app.models import DataQuality, MetricType, PhysiologicalMeasurement, QualityStatus
from tests.domains.sleep.helpers import (
    END,
    START,
    analyze,
    both_metrics,
    measurement,
    series,
)


@pytest.mark.parametrize(
    ("metric", "values", "slope", "signal"),
    [
        (
            MetricType.SLEEP_DURATION,
            [480, 460, 440, 420, 400, 380, 360],
            -20,
            TrendSignal.DURATION_REDUCTION,
        ),
        (
            MetricType.SLEEP_EFFICIENCY,
            [92, 90, 88, 86, 84, 82, 80],
            -2,
            TrendSignal.EFFICIENCY_DECREASE,
        ),
        (
            MetricType.SLEEP_EFFICIENCY,
            [80, 82, 84, 86, 88, 90, 92],
            2,
            TrendSignal.EFFICIENCY_INCREASE,
        ),
    ],
)
def test_known_linear_trends(
    metric: MetricType, values: list[float], slope: float, signal: TrendSignal
) -> None:
    trends = analyze(series(values, metric))
    trend = next(item for item in trends if item.metric == metric)
    assert trend.sufficient_data
    assert trend.slope_per_day == pytest.approx(slope)
    assert trend.fitted_change == pytest.approx(slope * 6)
    assert trend.median_value == values[3]
    assert trend.signal == signal
    assert trend.coverage == 1.0
    assert not trend.missing_nights


@pytest.mark.parametrize(
    "values",
    [
        [480] * 7,
        [360, 380, 400, 420, 440, 460, 480],
        [480, 480, 480, 300, 480, 480, 480],
        [480, 480, 480, 480, 480, 480, 300],
    ],
)
def test_stable_increasing_and_isolated_low_duration_are_not_progressive(
    values: list[float],
) -> None:
    trend, _ = analyze(series(values))
    assert trend.sufficient_data
    assert trend.signal is None


def test_progression_fraction_gate_is_independent_of_effect_size() -> None:
    records = series([480, 450, 460, 420, 400, 410, 360])
    trend, _ = analyze(records)
    assert trend.slope_per_day < -5
    assert trend.fitted_change < -30
    assert trend.decreasing_fraction == pytest.approx(4 / 6)
    assert trend.signal is None
    relaxed = replace(demonstration_config(), minimum_decreasing_fraction=0.6)
    assert analyze(records, relaxed)[0].signal == TrendSignal.DURATION_REDUCTION


def test_ties_do_not_count_as_decreasing_transitions() -> None:
    records = series([480, 480, 440, 440, 400, 400, 360])
    trend, _ = analyze(records)
    assert trend.decreasing_fraction == 0.5
    assert trend.slope_per_day < 0
    assert trend.signal is None


@pytest.mark.parametrize(
    ("field", "threshold"),
    [("minimum_slope_per_day", 21.0), ("minimum_total_change", 121.0)],
)
def test_both_effect_size_gates_are_required(field: str, threshold: float) -> None:
    config = demonstration_config()
    config = replace(config, duration=replace(config.duration, **{field: threshold}))
    trend, _ = analyze(series([480, 460, 440, 420, 400, 380, 360]), config)
    assert trend.sufficient_data
    assert trend.signal is None


def test_equality_passes_all_effect_and_sufficiency_gates() -> None:
    config = demonstration_config()
    config = replace(
        config,
        duration=replace(config.duration, minimum_slope_per_day=10, minimum_total_change=30),
        minimum_nights=4,
        minimum_coverage=1.0,
        minimum_span_days=3.0,
        maximum_consecutive_missing_nights=0,
        minimum_decreasing_fraction=1.0,
    )
    trend, _ = analyze(series([480, 470, 460, 450]), config, window_end=START + timedelta(days=4))
    assert trend.sufficient_data
    assert trend.signal == TrendSignal.DURATION_REDUCTION


def test_subthreshold_efficiency_change_is_not_flagged() -> None:
    _, trend = analyze(
        series([92, 91.9, 91.8, 91.7, 91.6, 91.5, 91.4], MetricType.SLEEP_EFFICIENCY)
    )
    assert trend.sufficient_data
    assert trend.slope_per_day == pytest.approx(-0.1)
    assert trend.signal is None


def test_sustained_midwindow_efficiency_shift_can_cross_the_effect_size_gates() -> None:
    _, trend = analyze(series([92, 92, 92, 84, 84, 84, 84], MetricType.SLEEP_EFFICIENCY))
    assert trend.sufficient_data
    assert trend.signal == TrendSignal.EFFICIENCY_DECREASE
    assert trend.slope_per_day < -0.5
    assert trend.fitted_change < -3


def test_irregular_timestamps_use_actual_elapsed_days() -> None:
    scenario = next(
        item for item in demonstration_scenarios() if item.name == "irregular_timestamps"
    )
    trend, _ = analyze(scenario.measurements)
    assert trend.signal == TrendSignal.DURATION_REDUCTION
    assert trend.slope_per_day == pytest.approx(-20.0)
    assert trend.span_days == pytest.approx(6 + 2 / 24)
    assert trend.fitted_change == pytest.approx(-20 * (6 + 2 / 24))


def test_missing_nights_preserve_elapsed_slope_and_report_dates() -> None:
    records = [
        item
        for item in series([480, 460, 440, 420, 400, 380, 360])
        if item.measured_at.date() not in {(START + timedelta(days=i)).date() for i in (1, 4)}
    ]
    trend, _ = analyze(records)
    assert trend.sufficient_data
    assert trend.slope_per_day == -20
    assert trend.fitted_change == -120
    assert trend.coverage == pytest.approx(5 / 7)
    assert trend.missing_nights == tuple((START + timedelta(days=i)).date() for i in (1, 4))
    assert trend.longest_missing_run == 1
    assert trend.signal == TrendSignal.DURATION_REDUCTION
    strict = replace(demonstration_config(), minimum_coverage=0.8)
    strict_trend, _ = analyze(records, strict)
    assert not strict_trend.sufficient_data
    assert "coverage_below_minimum" in strict_trend.insufficient_reasons
    assert strict_trend.signal is None


@pytest.mark.parametrize("kept", [(0, 1, 2, 3), (3, 4, 5, 6)])
def test_leading_and_trailing_missing_runs_are_not_hidden(kept: tuple[int, ...]) -> None:
    config = replace(demonstration_config(), minimum_coverage=0.5)
    trend, _ = analyze([measurement(i, 480 - 20 * i) for i in kept], config)
    assert trend.coverage == pytest.approx(4 / 7)
    assert trend.longest_missing_run == 3
    assert trend.insufficient_reasons == ("missing_run_exceeds_maximum",)
    assert trend.signal is None


def test_too_few_nights_and_short_elapsed_span_are_explicit() -> None:
    trend, _ = analyze(series([480, 460]))
    assert "too_few_nights" in trend.insufficient_reasons
    assert "time_span_below_minimum" in trend.insufficient_reasons
    assert trend.slope_per_day == -20
    assert trend.signal is None
    assert not trend.sufficient_data


def test_minimum_elapsed_span_is_checked_even_with_enough_nights() -> None:
    config = replace(demonstration_config(), minimum_span_days=7)
    trend, _ = analyze(series([480, 460, 440, 420, 400, 380, 360]), config)
    assert trend.insufficient_reasons == ("time_span_below_minimum",)
    assert trend.signal is None


def test_unpaired_metrics_have_independent_coverage() -> None:
    duration = series([480] * 7)
    efficiency = series([92] * 7, MetricType.SLEEP_EFFICIENCY)[:3]
    duration_trend, efficiency_trend = analyze(duration + efficiency)
    assert duration_trend.sufficient_data
    assert duration_trend.coverage == 1
    assert not efficiency_trend.sufficient_data
    assert efficiency_trend.coverage == pytest.approx(3 / 7)
    assert len(efficiency_trend.missing_nights) == 4


def test_empty_input_produces_two_insufficient_results() -> None:
    trends = analyze([])
    assert [item.metric for item in trends] == [
        MetricType.SLEEP_DURATION,
        MetricType.SLEEP_EFFICIENCY,
    ]
    for trend in trends:
        assert not trend.sufficient_data
        assert trend.coverage == 0
        assert len(trend.missing_nights) == 7
        assert trend.median_value is None
        assert trend.slope_per_day is None
        assert trend.fitted_change is None
        assert trend.decreasing_fraction is None
        assert trend.signal is None


def test_no_complete_buckets_has_undefined_coverage() -> None:
    start = START + timedelta(hours=10)
    trend, _ = analyze([], window_start=start, window_end=start + timedelta(hours=1))
    assert not trend.expected_nights
    assert trend.coverage is None
    assert "no_complete_night_buckets" in trend.insufficient_reasons


def test_partial_edge_buckets_are_excluded_from_numerator_and_denominator() -> None:
    trend, _ = analyze(
        series([480] * 7),
        window_start=START + timedelta(hours=6),
        window_end=END - timedelta(hours=6),
    )
    assert trend.sufficient_data
    assert len(trend.observations) == len(trend.expected_nights) == 5
    assert trend.coverage == 1
    assert not trend.missing_nights
    assert {item.reason for item in trend.exclusions} == {
        "partial_night_bucket",
        "incomplete_interval",
    }


def test_half_open_window_and_exact_completed_interval_boundary() -> None:
    records = series([480] * 7)
    records[0] = measurement(0, measured_at=START, interval_end=START + timedelta(hours=9))
    records[-1] = measurement(6, interval_end=END)
    records += [
        measurement(7, measured_at=END, interval_end=None),
        measurement(-1, measured_at=START - timedelta(seconds=1), interval_end=None),
    ]
    trend, _ = analyze(records)
    assert len(trend.observations) == 7
    assert trend.observations[0].measured_at == START
    assert [item.reason for item in trend.exclusions] == ["outside_window", "outside_window"]


def test_incomplete_interval_is_not_clipped_or_prorated() -> None:
    records = series([480] * 7)
    records[-1] = measurement(6, interval_end=END + timedelta(hours=1))
    trend, _ = analyze(records)
    assert len(trend.observations) == 6
    assert trend.missing_nights == ((START + timedelta(days=6)).date(),)
    assert trend.exclusions[0].reason == "incomplete_interval"


def test_point_summaries_are_supported_without_assuming_interval_length() -> None:
    trend, _ = analyze([measurement(i, interval_end=None) for i in range(7)])
    assert trend.sufficient_data
    assert trend.median_value == 480


def test_offset_timestamps_and_midnight_intervals_group_as_utc() -> None:
    records = both_metrics()
    shifted = [
        item.model_copy(
            update={
                "measured_at": item.measured_at.astimezone(
                    timezone(timedelta(hours=5, minutes=30))
                ),
                "interval_end": item.interval_end.astimezone(timezone(timedelta(hours=-7))),
            }
        )
        for item in records
    ]
    assert analyze(records) == analyze(shifted)
    trend, _ = analyze(shifted)
    assert trend.observations[0].night == START.date()
    assert trend.observations[0].measured_at.tzinfo == UTC


def test_operational_boundary_is_configurable() -> None:
    record = measurement(0, measured_at=START + timedelta(hours=13), interval_end=None)
    noon_trend, _ = analyze([record])
    midnight_trend, _ = analyze([record], replace(demonstration_config(), night_start_hour_utc=0))
    assert noon_trend.observations[0].night == START.date()
    assert midnight_trend.observations[0].night == (START + timedelta(days=1)).date()


def test_identical_repeated_ids_count_once() -> None:
    records = series([480] * 7)
    trend, _ = analyze(records + [records[2].model_copy(deep=True)])
    assert len(trend.observations) == 7
    assert trend.coverage == 1
    assert trend.exclusions[0].reason == "repeated_identical_id"


def test_conflicting_repeated_id_raises_instead_of_choosing_input_order() -> None:
    records = series([480] * 7)
    conflict = measurement(2, value=300)
    with pytest.raises(ValueError, match="Conflicting measurement_id"):
        analyze(records + [conflict])


def test_multiple_distinct_records_exclude_the_ambiguous_night() -> None:
    records = series([480] * 7) + [
        measurement(2, value=300, measurement_id="synthetic-nap-or-revision")
    ]
    trend, _ = analyze(records)
    assert len(trend.observations) == 6
    assert trend.missing_nights == ((START + timedelta(days=2)).date(),)
    assert [item.reason for item in trend.exclusions] == ["ambiguous_night", "ambiguous_night"]
    assert trend.median_value == 480


def test_overlapping_periods_in_different_buckets_exclude_both() -> None:
    records = series([480] * 7)
    records[0] = measurement(0, interval_end=START + timedelta(days=2, hours=8))
    trend, _ = analyze(records)
    assert len(trend.observations) == 5
    assert trend.missing_nights == (START.date(), (START + timedelta(days=1)).date())
    assert [item.reason for item in trend.exclusions] == ["overlapping_intervals"] * 2


@pytest.mark.parametrize(
    ("metric", "value", "reason"),
    [
        (MetricType.SLEEP_DURATION, -1, "invalid_metric_value"),
        (MetricType.SLEEP_DURATION, 541, "duration_exceeds_observation_interval"),
        (MetricType.SLEEP_EFFICIENCY, -0.1, "invalid_metric_value"),
        (MetricType.SLEEP_EFFICIENCY, 100.1, "invalid_metric_value"),
    ],
)
def test_definition_violations_are_excluded_without_clinical_limits(
    metric: MetricType, value: float, reason: str
) -> None:
    trend = next(item for item in analyze([measurement(0, value, metric)]) if item.metric == metric)
    assert not trend.observations
    assert trend.exclusions[0].reason == reason


@pytest.mark.parametrize(
    ("metric", "value"),
    [
        (MetricType.SLEEP_DURATION, 0),
        (MetricType.SLEEP_EFFICIENCY, 0),
        (MetricType.SLEEP_EFFICIENCY, 100),
    ],
)
def test_zero_and_percentage_endpoints_are_values_not_missing_data(
    metric: MetricType, value: float
) -> None:
    trend = next(item for item in analyze(series([value] * 7, metric)) if item.metric == metric)
    assert trend.sufficient_data
    assert trend.median_value == value
    assert trend.coverage == 1
    assert trend.signal is None


def test_zero_length_interval_is_not_a_completed_sleep_period() -> None:
    record = measurement(0, value=0, interval_end=START + timedelta(hours=10))
    trend, _ = analyze([record])
    assert not trend.observations
    assert trend.exclusions[0].reason == "non_positive_interval"


def test_upstream_unusable_is_excluded_and_degraded_is_retained() -> None:
    records = series([480] * 7)
    records[2] = measurement(2, data_quality=DataQuality(status=QualityStatus.UNUSABLE))
    records[3] = measurement(3, data_quality=DataQuality(status=QualityStatus.DEGRADED))
    trend, _ = analyze(records)
    assert len(trend.observations) == 6
    assert trend.missing_nights == ((START + timedelta(days=2)).date(),)
    assert trend.exclusions[0].reason == "upstream_quality_unusable"
    assert QualityStatus.DEGRADED in {item.quality_status for item in trend.observations}


def test_unusable_duplicate_does_not_invalidate_the_eligible_record() -> None:
    records = series([480] * 7)
    records.append(
        measurement(
            2,
            measurement_id="synthetic-unusable-copy",
            data_quality=DataQuality(status=QualityStatus.UNUSABLE),
        )
    )
    trend, _ = analyze(records)
    assert trend.coverage == 1
    assert trend.exclusions[0].reason == "upstream_quality_unusable"


def test_order_invariance_and_no_input_mutation() -> None:
    records = both_metrics() + [measurement(2, measurement_id="synthetic-second-record")]
    before = [item.model_dump(mode="json") for item in records]
    assert analyze(records) == analyze(reversed(records))
    assert [item.model_dump(mode="json") for item in records] == before


def test_generators_are_consumed_once() -> None:
    assert analyze(iter(both_metrics())) == analyze(both_metrics())


@pytest.mark.parametrize(
    "record",
    [
        measurement(crew_member_id="different-opaque-crew"),
        measurement(metric=MetricType.HEART_RATE, unit="bpm"),
    ],
)
def test_mixed_people_and_other_metrics_are_rejected(record: PhysiologicalMeasurement) -> None:
    with pytest.raises(ValueError, match="crew member|Unsupported sleep metric"):
        analyze([record])


@pytest.mark.parametrize(
    "overrides",
    [
        {"window_start": START.replace(tzinfo=None)},
        {"window_end": END.replace(tzinfo=None)},
        {"window_end": START},
        {"window_end": START - timedelta(seconds=1)},
    ],
)
def test_invalid_windows_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="timezone-aware|later than"):
        analyze([], **overrides)


def test_large_finite_values_do_not_overflow_the_even_count_median() -> None:
    records = [measurement(i, value=1e308, interval_end=None) for i in range(4)]
    trend, _ = analyze(records, window_end=START + timedelta(days=4))
    assert trend.sufficient_data
    assert trend.median_value == 1e308
    assert isfinite(trend.median_value)
    assert trend.slope_per_day == 0


def test_unrepresentable_pairwise_slope_withholds_classification() -> None:
    records = [measurement(i, value=1e308, interval_end=None) for i in range(4)]
    records[0] = measurement(
        0, value=0, measured_at=START + timedelta(days=1, microseconds=-1), interval_end=None
    )
    records[1] = measurement(
        1, value=1e308, measured_at=START + timedelta(days=1), interval_end=None
    )
    trend, _ = analyze(
        records,
        replace(demonstration_config(), minimum_span_days=1),
        window_end=START + timedelta(days=4),
    )
    assert not trend.sufficient_data
    assert "non_finite_trend_arithmetic" in trend.insufficient_reasons
    assert trend.slope_per_day is trend.fitted_change is trend.signal is None
