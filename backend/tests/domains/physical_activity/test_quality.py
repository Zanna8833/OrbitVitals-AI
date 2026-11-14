"""Upstream assessments constrain comparisons without depending on a quality engine."""

import pytest

from app.domains.physical_activity import TargetOutcome, monitor_activity
from app.models import DataQuality, EvaluationStatus, QualityFlag, QualityStatus
from tests.domains.physical_activity.support import DURATION, replace_request, series


@pytest.mark.parametrize(
    ("status", "value_retained", "eligible"),
    [
        (QualityStatus.ACCEPTABLE, True, True),
        (QualityStatus.NOT_ASSESSED, True, True),
        (QualityStatus.DEGRADED, True, False),
        (QualityStatus.UNUSABLE, False, False),
    ],
)
def test_measurement_quality_status_is_respected(
    status: QualityStatus, value_retained: bool, eligible: bool
) -> None:
    original = series([30])
    record = original.measurements[0].model_copy(
        update={"data_quality": DataQuality(status=status)}
    )
    result = monitor_activity(
        replace_request(original, measurements=[record, original.measurements[1]])
    )
    item = result.days[0].metrics[0]
    assert item.observed_total == (30 if value_retained else None)
    assert item.comparison_eligible == eligible
    assert item.target_outcome == (TargetOutcome.MET if eligible else TargetOutcome.UNKNOWN)
    assert item.data_quality.score is None


@pytest.mark.parametrize("flag", list(QualityFlag))
def test_quality_flags_are_not_overridden_by_an_acceptable_status(flag: QualityFlag) -> None:
    original = series([30])
    record = original.measurements[0].model_copy(
        update={"data_quality": DataQuality(status=QualityStatus.ACCEPTABLE, flags=[flag])}
    )
    result = monitor_activity(
        replace_request(original, measurements=[record, original.measurements[1]])
    )
    item = result.days[0].metrics[0]
    assert item.target_outcome == TargetOutcome.UNKNOWN
    assert flag in item.data_quality.flags
    assert result.evaluation.findings[0].status == EvaluationStatus.INSUFFICIENT_DATA


def test_missing_quality_is_explicitly_unassessed_even_with_complete_recording() -> None:
    result = monitor_activity(series([30]))
    assert result.evaluation.status == EvaluationStatus.NOMINAL
    assert result.evaluation.data_quality.status == QualityStatus.NOT_ASSESSED
    assert result.evaluation.data_quality.score is None
    assert "not fully assessed" in result.evaluation.findings[0].explanation


def test_quality_completeness_does_not_substitute_for_recording_coverage() -> None:
    original = series([30])
    records = [
        item.model_copy(
            update={"data_quality": DataQuality(status=QualityStatus.ACCEPTABLE, completeness=1)}
        )
        for item in original.measurements
    ]
    result = monitor_activity(replace_request(original, measurements=records, coverage=[]))
    assert all(item.target_outcome == TargetOutcome.UNKNOWN for item in result.days[0].metrics)


def test_incomplete_quality_withholds_comparison_even_if_coverage_claims_complete() -> None:
    original = series([30])
    record = original.measurements[0].model_copy(
        update={"data_quality": DataQuality(status=QualityStatus.ACCEPTABLE, completeness=0.8)}
    )
    result = monitor_activity(
        replace_request(original, measurements=[record, original.measurements[1]])
    )
    assert result.days[0].metrics[0].observed_total == 30
    assert not result.days[0].metrics[0].recording_complete
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN


def test_window_quality_adapter_can_suspend_comparison_without_editing_measurements() -> None:
    original = series([30])
    coverage = [
        item.model_copy(update={"quality": DataQuality(status=QualityStatus.DEGRADED)})
        if item.metric == DURATION
        else item
        for item in original.coverage
    ]
    result = monitor_activity(replace_request(original, coverage=coverage))
    assert result.days[0].metrics[0].observed_total == 30
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert result.days[0].metrics[1].target_outcome == TargetOutcome.MET


def test_acceptable_quality_notes_do_not_reduce_quality_and_scores_are_not_averaged() -> None:
    original = series([30] * 7)
    records = [
        item.model_copy(
            update={
                "data_quality": DataQuality(
                    status=QualityStatus.ACCEPTABLE, score=0.9, notes="Device assessment supplied."
                )
            }
        )
        for item in original.measurements
    ]
    result = monitor_activity(replace_request(original, measurements=records))
    assert result.evaluation.data_quality.status == QualityStatus.ACCEPTABLE
    assert result.weeks[0].metrics[0].data_quality.status == QualityStatus.ACCEPTABLE
    assert result.evaluation.data_quality.score is None
    assert "Device assessment supplied" in result.evaluation.data_quality.notes
