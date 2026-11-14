"""Existing-contract adapters and external engine integration boundaries."""

from dataclasses import replace
from datetime import UTC, timedelta, timezone
from json import dumps, loads
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.domains.sleep import analyze_sleep_observation
from app.domains.sleep.demo import demonstration_config
from app.models import (
    AlgorithmInfo,
    BaselineStatistics,
    BaselineStatus,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MetricFinding,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from tests.domains.sleep.helpers import END, START, baseline, evaluate, measurement, series
from tests.support import load_schema


def observe(record: PhysiologicalMeasurement | None = None, **overrides: Any) -> MetricFinding:
    arguments = {"evaluated_at": END, "config": demonstration_config(), **overrides}
    return analyze_sleep_observation(record if record is not None else measurement(), **arguments)


def test_observation_without_baseline_stays_descriptive() -> None:
    finding = observe()
    assert finding.status == EvaluationStatus.INSUFFICIENT_DATA
    assert finding.observed_value == 480
    assert finding.unit == "min"
    assert finding.baseline_id is finding.baseline_value is None
    assert finding.absolute_deviation is finding.relative_deviation is None
    assert finding.data_quality is None
    assert "No personal baseline supplied" in finding.explanation
    assert "Source: simulated" in finding.explanation


@pytest.mark.parametrize(
    ("value", "expected_status", "deviation"),
    [
        (420, EvaluationStatus.ATTENTION, -60),
        (540, EvaluationStatus.ATTENTION, 60),
        (421, EvaluationStatus.NOMINAL, -59),
        (480, EvaluationStatus.NOMINAL, 0),
    ],
)
def test_observation_uses_two_sided_inclusive_baseline_gate(
    value: float, expected_status: EvaluationStatus, deviation: float
) -> None:
    reference = baseline()
    finding = observe(measurement(value=value), baseline=reference)
    assert finding.status == expected_status
    assert finding.baseline_id == reference.baseline_id
    assert finding.baseline_value == 480
    assert finding.absolute_deviation == deviation
    assert finding.relative_deviation == pytest.approx(deviation / 480)
    assert finding.unit == "min"


def test_efficiency_deviation_is_in_percentage_points_and_relative_is_dimensionless() -> None:
    finding = observe(
        measurement(value=87, metric=MetricType.SLEEP_EFFICIENCY),
        baseline=baseline(MetricType.SLEEP_EFFICIENCY),
    )
    assert finding.status == EvaluationStatus.ATTENTION
    assert finding.unit == "%"
    assert finding.absolute_deviation == -5
    assert finding.relative_deviation == pytest.approx(-5 / 92)
    assert "percentage points" in finding.explanation


def test_explicit_baseline_median_is_preferred_to_mean() -> None:
    reference = baseline(statistics=BaselineStatistics(median=450, mean=480))
    finding = observe(baseline=reference)
    assert finding.baseline_value == 450
    assert finding.absolute_deviation == 30
    assert "baseline median" in finding.explanation


def test_baseline_mean_is_used_when_median_is_absent() -> None:
    finding = observe(baseline=baseline(statistics=BaselineStatistics(mean=500)))
    assert finding.baseline_value == 500
    assert finding.absolute_deviation == -20
    assert "baseline mean" in finding.explanation


@pytest.mark.parametrize("value", [0.0, 60.0])
def test_zero_baseline_leaves_relative_deviation_undefined(value: float) -> None:
    finding = observe(
        measurement(value=value), baseline=baseline(statistics=BaselineStatistics(median=0))
    )
    assert finding.baseline_value == 0
    assert finding.absolute_deviation == value
    assert finding.relative_deviation is None
    assert finding.status == (EvaluationStatus.ATTENTION if value else EvaluationStatus.NOMINAL)
    assert "zero reference" in finding.explanation
    dumps(finding.model_dump(mode="json"), allow_nan=False)


def test_relative_ratio_overflow_does_not_break_the_contract() -> None:
    finding = observe(
        measurement(value=1e308, interval_end=None),
        baseline=baseline(statistics=BaselineStatistics(median=1e-320)),
    )
    assert finding.status == EvaluationStatus.ATTENTION
    assert finding.absolute_deviation == 1e308
    assert finding.relative_deviation is None
    dumps(finding.model_dump(mode="json"), allow_nan=False)


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"status": BaselineStatus.PROVISIONAL}, "not established"),
        ({"status": BaselineStatus.INSUFFICIENT_DATA}, "not established"),
        ({"sample_count": 0}, "not established"),
        ({"statistics": BaselineStatistics()}, "no usable median or mean"),
        ({"statistics": BaselineStatistics(median=-1)}, "no usable median or mean"),
        ({"data_quality": DataQuality(status=QualityStatus.UNUSABLE)}, "unusable"),
        ({"window_end": START + timedelta(hours=11)}, "overlaps or follows"),
        ({"computed_at": END + timedelta(seconds=1)}, "after evaluated_at"),
    ],
)
def test_unusable_reference_is_not_synthesized_or_reclassified(
    overrides: dict[str, Any], reason: str
) -> None:
    reference = baseline(**overrides)
    before = reference.model_dump(mode="json")
    finding = observe(baseline=reference)
    assert finding.status == EvaluationStatus.INSUFFICIENT_DATA
    assert finding.observed_value == 480
    assert finding.baseline_id is finding.baseline_value is None
    assert finding.absolute_deviation is finding.relative_deviation is None
    assert reason in finding.explanation
    assert reference.model_dump(mode="json") == before


def test_out_of_definition_efficiency_baseline_is_not_used() -> None:
    finding = observe(
        measurement(value=92, metric=MetricType.SLEEP_EFFICIENCY),
        baseline=baseline(MetricType.SLEEP_EFFICIENCY, statistics=BaselineStatistics(median=101)),
    )
    assert finding.status == EvaluationStatus.INSUFFICIENT_DATA
    assert finding.baseline_id is None


def test_baseline_may_end_exactly_at_observation_start() -> None:
    record = measurement()
    reference = baseline(window_end=record.measured_at, computed_at=record.measured_at)
    finding = observe(record, baseline=reference, evaluated_at=record.interval_end)
    assert finding.status == EvaluationStatus.NOMINAL
    assert finding.baseline_id == reference.baseline_id


@pytest.mark.parametrize(
    "reference",
    [baseline(crew_member_id="different-opaque-crew"), baseline(MetricType.SLEEP_EFFICIENCY)],
)
def test_baseline_identity_mismatch_is_an_integration_error(reference: PersonalBaseline) -> None:
    with pytest.raises(ValueError, match="match the requested crew member and metric"):
        observe(baseline=reference)


@pytest.mark.parametrize(
    ("record", "reason"),
    [
        (measurement(value=-1), "invalid_metric_value"),
        (measurement(value=541), "duration_exceeds_observation_interval"),
        (measurement(value=101, metric=MetricType.SLEEP_EFFICIENCY), "invalid_metric_value"),
        (measurement(8), "observation_not_complete"),
        (measurement(interval_end=END + timedelta(seconds=1)), "observation_not_complete"),
        (measurement(data_quality=DataQuality(status=QualityStatus.UNUSABLE)), "quality_unusable"),
    ],
)
def test_invalid_incomplete_and_unusable_observations_cannot_be_classified(
    record: PhysiologicalMeasurement, reason: str
) -> None:
    finding = observe(record, baseline=baseline(record.metric))
    assert finding.status == EvaluationStatus.INSUFFICIENT_DATA
    assert finding.observed_value is finding.baseline_id is None
    assert reason in finding.explanation


def test_single_point_summary_and_completion_at_horizon_are_supported() -> None:
    reference = baseline()
    assert (
        observe(measurement(interval_end=None), baseline=reference).status
        == EvaluationStatus.NOMINAL
    )
    record = measurement()
    assert (
        observe(record, baseline=reference, evaluated_at=record.interval_end).status
        == EvaluationStatus.NOMINAL
    )


def test_single_observation_preserves_quality_without_mutating_it() -> None:
    quality = DataQuality(status=QualityStatus.DEGRADED, flags=[QualityFlag.SIGNAL_ARTIFACT])
    record = measurement(data_quality=quality)
    finding = observe(record, baseline=baseline())
    assert finding.status == EvaluationStatus.NOMINAL
    assert finding.data_quality == quality
    assert finding.data_quality is not quality
    assert "degraded" in finding.explanation
    finding.data_quality.flags.clear()
    assert record.data_quality.flags == [QualityFlag.SIGNAL_ARTIFACT]


def test_single_observation_requires_an_aware_evaluation_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        observe(evaluated_at=END.replace(tzinfo=None))


def test_single_observation_rejects_non_sleep_metrics() -> None:
    with pytest.raises(ValueError, match="Unsupported sleep metric"):
        observe(measurement(metric=MetricType.HEART_RATE, unit="bpm"))


def test_trend_evaluation_without_baseline_has_no_fabricated_reference() -> None:
    records = series([480, 460, 440, 420, 400, 380, 360])
    result = evaluate(records, mission_phase=MissionPhaseType.IN_FLIGHT)
    assert result.domain == HealthDomain.SLEEP
    assert result.mission_phase == MissionPhaseType.IN_FLIGHT
    assert result.status == EvaluationStatus.ATTENTION
    duration, efficiency = result.findings
    assert duration.status == EvaluationStatus.ATTENTION
    assert duration.observed_value == 420
    assert "progressive_duration_reduction" in duration.explanation
    assert "slope=-20 min/day" in duration.explanation
    assert efficiency.status == EvaluationStatus.INSUFFICIENT_DATA
    assert efficiency.observed_value is None
    for finding in result.findings:
        assert finding.baseline_id is finding.baseline_value is None
        assert finding.absolute_deviation is finding.relative_deviation is None
        assert "No personal baseline supplied" in finding.explanation
    assert result.data_quality.status == QualityStatus.NOT_ASSESSED
    assert result.data_quality.score is result.data_quality.completeness is None
    assert result.data_quality.algorithm is result.data_quality.assessed_at is None
    assert result.data_quality.flags == []


def test_stable_window_is_nominal_with_an_explicit_non_clinical_explanation() -> None:
    result = evaluate()
    assert result.status == EvaluationStatus.NOMINAL
    assert all(item.status == EvaluationStatus.NOMINAL for item in result.findings)
    assert all(
        "does not establish adequate sleep or health" in item.explanation
        for item in result.findings
    )
    assert result.algorithm.name == "sleep_monitoring_trends"
    assert result.algorithm.version == "0.1.0"
    assert '"policy_id": "synthetic_demonstration_only_v1"' in result.summary
    assert '"minimum_coverage": 0.6' in result.summary
    assert '"night_start_hour_utc": 12' in result.summary


def test_a_missing_metric_prevents_an_overall_nominal_status() -> None:
    result = evaluate(series([480] * 7))
    assert result.status == EvaluationStatus.INSUFFICIENT_DATA
    assert result.findings[0].status == EvaluationStatus.NOMINAL
    assert result.findings[1].status == EvaluationStatus.INSUFFICIENT_DATA


def test_empty_window_is_insufficient_with_two_findings() -> None:
    result = evaluate([])
    assert result.status == EvaluationStatus.INSUFFICIENT_DATA
    assert len(result.findings) == 2
    assert all(item.status == EvaluationStatus.INSUFFICIENT_DATA for item in result.findings)
    assert all(item.observed_value is None for item in result.findings)


def test_window_reference_compares_median_not_slope_or_last_observation() -> None:
    result = evaluate(
        series([480, 460, 440, 420, 400, 380, 360]),
        baselines={MetricType.SLEEP_DURATION: baseline()},
    )
    finding = result.findings[0]
    assert finding.observed_value == 420
    assert finding.baseline_value == 480
    assert finding.absolute_deviation == -60
    assert finding.relative_deviation == -0.125


def test_window_median_deviation_can_signal_without_a_trend() -> None:
    result = evaluate(series([400] * 7), baselines={MetricType.SLEEP_DURATION: baseline()})
    finding = result.findings[0]
    assert finding.status == EvaluationStatus.ATTENTION
    assert finding.absolute_deviation == -80
    assert "No configured trend pattern" in finding.explanation


def test_window_baseline_must_precede_entire_window_not_first_observed_record() -> None:
    reference = baseline(window_end=START + timedelta(hours=1))
    result = evaluate(series([480] * 7), baselines={MetricType.SLEEP_DURATION: reference})
    assert result.findings[0].status == EvaluationStatus.NOMINAL
    assert result.findings[0].baseline_id is None
    assert "overlaps or follows" in result.findings[0].explanation


def test_insufficient_window_cannot_signal_from_baseline_deviation_alone() -> None:
    result = evaluate(series([300, 300]), baselines={MetricType.SLEEP_DURATION: baseline()})
    finding = result.findings[0]
    assert finding.status == EvaluationStatus.INSUFFICIENT_DATA
    assert finding.absolute_deviation == -180
    assert "descriptive only" in finding.explanation


def test_measurement_quality_statuses_do_not_become_an_invented_window_quality_score() -> None:
    records = series([480] * 7)
    records[0] = measurement(0, data_quality=DataQuality(status=QualityStatus.DEGRADED, score=0.4))
    records[1] = measurement(
        1, data_quality=DataQuality(status=QualityStatus.ACCEPTABLE, score=0.9)
    )
    result = evaluate(records)
    quality = result.findings[0].data_quality
    assert quality.status == QualityStatus.NOT_ASSESSED
    assert quality.score is quality.completeness is None
    assert quality.flags == []
    assert '"degraded": 1' in quality.notes
    assert '"acceptable": 1' in quality.notes
    assert '"not_assessed": 5' in quality.notes


def test_supplied_quality_is_preserved_and_copied_at_its_original_scope() -> None:
    window_quality = DataQuality(
        status=QualityStatus.DEGRADED,
        score=0.7,
        completeness=0.8,
        flags=[QualityFlag.MISSING_DATA],
        notes="Synthetic assessment fixture for this exact window.",
        algorithm=AlgorithmInfo(name="synthetic_quality_fixture", version="0.0.0"),
        assessed_at=END,
    )
    metric_quality = DataQuality(status=QualityStatus.ACCEPTABLE, score=0.95)
    result = evaluate(
        data_quality=window_quality,
        metric_data_quality={MetricType.SLEEP_DURATION: metric_quality},
    )
    assert result.status == EvaluationStatus.NOMINAL
    assert result.data_quality == window_quality
    assert result.data_quality is not window_quality
    assert result.findings[0].data_quality == metric_quality
    assert result.findings[0].data_quality is not metric_quality
    assert result.findings[1].data_quality.status == QualityStatus.NOT_ASSESSED
    result.data_quality.flags.clear()
    assert window_quality.flags == [QualityFlag.MISSING_DATA]


def test_unusable_window_quality_suppresses_both_classifications() -> None:
    result = evaluate(
        series([480, 460, 440, 420, 400, 380, 360])
        + series([92, 90, 88, 86, 84, 82, 80], MetricType.SLEEP_EFFICIENCY),
        data_quality=DataQuality(status=QualityStatus.UNUSABLE),
    )
    assert result.status == EvaluationStatus.INSUFFICIENT_DATA
    assert all(item.status == EvaluationStatus.INSUFFICIENT_DATA for item in result.findings)
    assert all("quality is unusable" in item.explanation for item in result.findings)


def test_unusable_metric_quality_suppresses_only_that_metric() -> None:
    result = evaluate(
        series([480, 460, 440, 420, 400, 380, 360])
        + series([92, 90, 88, 86, 84, 82, 80], MetricType.SLEEP_EFFICIENCY),
        metric_data_quality={
            MetricType.SLEEP_EFFICIENCY: DataQuality(status=QualityStatus.UNUSABLE)
        },
    )
    assert result.status == EvaluationStatus.ATTENTION
    assert result.findings[0].status == EvaluationStatus.ATTENTION
    assert result.findings[1].status == EvaluationStatus.INSUFFICIENT_DATA


def test_acceptable_upstream_quality_does_not_override_statistical_sufficiency_gates() -> None:
    result = evaluate(
        series([480, 460]), data_quality=DataQuality(status=QualityStatus.ACCEPTABLE, score=1)
    )
    assert result.status == EvaluationStatus.INSUFFICIENT_DATA


@pytest.mark.parametrize(
    "arguments",
    [
        {"baselines": {MetricType.SLEEP_DURATION: baseline(crew_member_id="another-crew")}},
        {"baselines": {MetricType.SLEEP_DURATION: baseline(MetricType.SLEEP_EFFICIENCY)}},
        {"baselines": {MetricType.HEART_RATE: baseline()}},
        {
            "metric_data_quality": {
                MetricType.HEART_RATE: DataQuality(status=QualityStatus.NOT_ASSESSED)
            }
        },
    ],
)
def test_integration_mappings_must_match_supported_metrics(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="match the requested|Unsupported sleep metric"):
        evaluate(**arguments)


@pytest.mark.parametrize(
    "arguments",
    [
        {"evaluated_at": END - timedelta(seconds=1)},
        {"evaluated_at": END.replace(tzinfo=None)},
        {"window_start": START.replace(tzinfo=None)},
        {"window_end": END.replace(tzinfo=None)},
        {"window_end": START},
    ],
)
def test_invalid_evaluation_horizons_are_rejected(arguments: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="timezone-aware|later than"):
        evaluate(**arguments)


def test_evaluation_metadata_is_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=2))
    result = evaluate(
        window_start=START.astimezone(offset),
        window_end=END.astimezone(offset),
        evaluated_at=END.astimezone(offset),
    )
    assert result.window_start == START
    assert result.window_end == result.evaluated_at == END
    assert (
        result.window_start.tzinfo == result.window_end.tzinfo == result.evaluated_at.tzinfo == UTC
    )


def test_evaluation_serializes_against_the_unchanged_model_and_schema() -> None:
    result = evaluate(baselines={MetricType.SLEEP_DURATION: baseline()})
    payload = loads(dumps(result.model_dump(mode="json"), allow_nan=False))
    assert EvaluationResult.model_validate(payload) == result
    Draft202012Validator(load_schema("evaluation_result")).validate(payload)


def test_complete_policy_is_recorded_for_reproducibility() -> None:
    config = replace(demonstration_config(), policy_id="test-policy-v2", minimum_coverage=0.9)
    result = evaluate(config=config)
    policy = loads(result.summary.split("Policy: ", maxsplit=1)[1])
    assert policy["policy_id"] == "test-policy-v2"
    assert policy["minimum_coverage"] == 0.9
    assert policy["duration"]["minimum_slope_per_day"] == 5
