"""Personal targets, historical baselines, planned rest and descriptive reductions."""

from datetime import timedelta

import pytest

from app.domains.physical_activity import (
    ActivityDayPlan,
    ActivityMetricPolicy,
    TargetOutcome,
    monitor_activity,
)
from app.models import (
    BaselineStatistics,
    BaselineStatus,
    DataQuality,
    EvaluationStatus,
    MissionPhaseType,
    QualityStatus,
)
from tests.domains.physical_activity.support import (
    DURATION,
    ENERGY,
    START,
    baseline_reference,
    replace_request,
    series,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(19, TargetOutcome.MISSED), (20, TargetOutcome.MET), (21, TargetOutcome.MET)],
)
def test_daily_minimum_target_boundary(value: float, expected: TargetOutcome) -> None:
    result = monitor_activity(series([value]))
    assert result.days[0].metrics[0].target_outcome == expected


def test_zero_targets_are_valid_and_are_not_missing_configuration() -> None:
    result = monitor_activity(
        series([0], policies=[ActivityMetricPolicy(metric=DURATION, daily_target=0)])
    )
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.MET


def test_no_comparator_does_not_imply_nominal_activity() -> None:
    result = monitor_activity(series([30], policies=[]))
    assert result.evaluation.status == EvaluationStatus.INSUFFICIENT_DATA
    assert result.evaluation.findings[0].observed_value == 30
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.NOT_CONFIGURED


def test_planned_rest_suspends_daily_targets_and_baseline_comparisons() -> None:
    plan = ActivityDayPlan(day=START.date(), planned_rest=True, notes="Scheduled recovery.")
    result = monitor_activity(series([0], day_plans=[plan], baselines=[baseline_reference()]))
    assert all(
        item.target_outcome == TargetOutcome.NOT_APPLICABLE for item in result.days[0].metrics
    )
    assert result.evaluation.findings[0].observed_value is None
    assert result.evaluation.status == EvaluationStatus.INSUFFICIENT_DATA
    assert "Scheduled recovery." in result.days[0].notes


def test_operational_exception_and_day_specific_targets_are_explicit() -> None:
    plans = [
        ActivityDayPlan(day=START.date(), daily_targets={DURATION: 10}),
        ActivityDayPlan(
            day=(START + timedelta(days=1)).date(),
            comparisons_enabled=False,
            notes="Exercise equipment unavailable.",
        ),
    ]
    result = monitor_activity(series([15, 0], day_plans=plans))
    assert result.days[0].metrics[0].target_value == 10
    assert result.days[0].metrics[0].target_outcome == TargetOutcome.MET
    assert result.days[1].metrics[0].target_outcome == TargetOutcome.NOT_APPLICABLE
    assert result.evaluation.findings[0].status == EvaluationStatus.NOMINAL


@pytest.mark.parametrize(
    ("target", "expected"), [(210, TargetOutcome.MET), (211, TargetOutcome.MISSED)]
)
def test_full_iso_week_target(target: float, expected: TargetOutcome) -> None:
    result = monitor_activity(
        series([30] * 7, policies=[ActivityMetricPolicy(metric=DURATION, weekly_target=target)])
    )
    item = result.weeks[0].metrics[0]
    assert item.observed_total == 210
    assert item.target_value == target
    assert item.target_outcome == expected
    assert result.weeks[0].week_start == START.date()


@pytest.mark.parametrize("values", [[30] * 6, [30, 30, None, 30, 30, 30, 30]])
def test_partial_or_missing_week_is_not_prorated(values: list[float | None]) -> None:
    result = monitor_activity(
        series(values, policies=[ActivityMetricPolicy(metric=DURATION, weekly_target=210)])
    )
    assert result.weeks[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN
    assert result.evaluation.findings[0].status == EvaluationStatus.INSUFFICIENT_DATA


def test_rest_activity_is_retained_in_weekly_totals_without_a_daily_target_miss() -> None:
    plans = [ActivityDayPlan(day=(START + timedelta(days=6)).date(), planned_rest=True)]
    result = monitor_activity(
        series(
            [30] * 6 + [5],
            day_plans=plans,
            policies=[ActivityMetricPolicy(metric=DURATION, daily_target=20, weekly_target=185)],
        )
    )
    assert result.weeks[0].metrics[0].observed_total == 185
    assert result.weeks[0].metrics[0].target_outcome == TargetOutcome.MET
    assert result.days[-1].metrics[0].target_outcome == TargetOutcome.NOT_APPLICABLE


def test_rest_does_not_impute_missing_activity_in_weekly_totals() -> None:
    result = monitor_activity(
        series(
            [30] * 6 + [None],
            day_plans=[ActivityDayPlan(day=(START + timedelta(days=6)).date(), planned_rest=True)],
            policies=[ActivityMetricPolicy(metric=DURATION, weekly_target=180)],
        )
    )
    assert result.weeks[0].metrics[0].observed_total == 180
    assert result.weeks[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN


def test_operational_exception_suspends_weekly_comparisons() -> None:
    result = monitor_activity(
        series(
            [30] * 7,
            day_plans=[ActivityDayPlan(day=START.date(), comparisons_enabled=False)],
            policies=[ActivityMetricPolicy(metric=DURATION, weekly_target=300)],
        )
    )
    assert result.weeks[0].metrics[0].target_outcome == TargetOutcome.NOT_APPLICABLE


def test_weekly_overflow_is_not_a_missed_target() -> None:
    result = monitor_activity(
        series([1e308] * 7, policies=[ActivityMetricPolicy(metric=DURATION, weekly_target=200)])
    )
    assert result.weeks[0].metrics[0].observed_total is None
    assert result.weeks[0].metrics[0].target_outcome == TargetOutcome.UNKNOWN


def test_progressive_daily_reduction_is_descriptive_even_without_a_target() -> None:
    result = monitor_activity(series([60, 50, 40, 30], policies=[]))
    assert result.evaluation.findings[0].status == EvaluationStatus.ATTENTION
    assert len(result.trends) == 1
    assert result.trends[0].values == [60, 50, 40, 30]
    assert result.trends[0].absolute_change == -30
    assert result.trends[0].relative_change == -0.5
    assert "no significance or medical risk" in result.trends[0].explanation
    assert result.days[1].metrics[0].absolute_change == -10


@pytest.mark.parametrize("values", [[40, 40, 30], [40, None, 30], [40, 50, 30], [40, 30]])
def test_gaps_plateaus_increases_and_short_runs_do_not_make_a_reduction_signal(
    values: list,
) -> None:
    result = monitor_activity(series(values))
    assert result.trends == []


@pytest.mark.parametrize("exception", ["rest", "operational", "target"])
def test_plan_changes_break_reduction_runs(exception: str) -> None:
    plan = ActivityDayPlan(
        day=(START + timedelta(days=1)).date(),
        planned_rest=exception == "rest",
        comparisons_enabled=exception != "operational",
        daily_targets={DURATION: 5} if exception == "target" else {},
    )
    result = monitor_activity(series([40, 30, 20], day_plans=[plan]))
    assert result.trends == []
    assert result.days[-1].metrics[0].absolute_change is None


def test_reduction_run_length_is_configurable() -> None:
    assert monitor_activity(series([50, 40, 30], reduction_run_length=4)).trends == []
    assert len(monitor_activity(series([50, 40, 30, 20], reduction_run_length=4)).trends) == 1


def test_distinct_maximal_reduction_runs_are_preserved() -> None:
    result = monitor_activity(series([60, 50, 40, 60, 50, 40]))
    assert [trend.values for trend in result.trends] == [[60, 50, 40], [60, 50, 40]]


def test_complete_weekly_reductions_have_explicit_week_over_week_changes() -> None:
    result = monitor_activity(series([40] * 7 + [30] * 7 + [20] * 7))
    assert len(result.trends) == 1
    trend = result.trends[0]
    assert trend.period == "weekly"
    assert trend.values == [280, 210, 140]
    assert result.weeks[1].metrics[0].absolute_change == -70
    assert result.weeks[1].metrics[0].relative_change == -0.25


def test_changed_rest_schedule_breaks_weekly_reduction_runs() -> None:
    result = monitor_activity(
        series(
            [40] * 7 + [30] * 7 + [20] * 7,
            day_plans=[ActivityDayPlan(day=(START + timedelta(days=13)).date(), planned_rest=True)],
        )
    )
    assert all(trend.period != "weekly" for trend in result.trends)
    assert result.weeks[1].metrics[0].absolute_change is None


def test_established_baseline_is_reported_with_signed_deviations() -> None:
    result = monitor_activity(series([30], baselines=[baseline_reference()]))
    finding = result.evaluation.findings[0]
    assert finding.baseline_id == "sim-daily-baseline"
    assert finding.baseline_value == 40
    assert finding.absolute_deviation == -10
    assert finding.relative_deviation == -0.25
    assert finding.status == EvaluationStatus.NOMINAL  # No baseline tolerance was configured.


def test_baseline_standard_deviation_does_not_create_an_unconfigured_threshold() -> None:
    result = monitor_activity(series([1000], baselines=[baseline_reference()]))
    assert result.evaluation.findings[0].status == EvaluationStatus.NOMINAL
    assert "absolute=None" in result.evaluation.findings[0].explanation


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (30, EvaluationStatus.NOMINAL),
        (29, EvaluationStatus.ATTENTION),
        (51, EvaluationStatus.ATTENTION),
    ],
)
def test_configured_relative_baseline_tolerance_is_two_sided_and_strict(
    value: float, expected: EvaluationStatus
) -> None:
    result = monitor_activity(
        series(
            [value],
            baselines=[baseline_reference()],
            policies=[
                ActivityMetricPolicy(
                    metric=DURATION, daily_target=20, baseline_relative_tolerance=0.25
                )
            ],
        )
    )
    assert result.evaluation.findings[0].status == expected


def test_daily_anomalies_are_not_cancelled_by_the_window_mean() -> None:
    result = monitor_activity(
        series(
            [20, 60],
            baselines=[baseline_reference()],
            policies=[ActivityMetricPolicy(metric=DURATION, baseline_absolute_tolerance=10)],
        )
    )
    finding = result.evaluation.findings[0]
    assert finding.observed_value == 40
    assert finding.absolute_deviation == 0
    assert finding.status == EvaluationStatus.ATTENTION
    assert "Unusual daily deviations" in finding.explanation


@pytest.mark.parametrize("absolute_tolerance", [None, 5])
def test_zero_baseline_has_no_relative_division(absolute_tolerance: float | None) -> None:
    result = monitor_activity(
        series(
            [30],
            baselines=[baseline_reference(statistics={"mean": 0})],
            policies=[
                ActivityMetricPolicy(
                    metric=DURATION,
                    daily_target=20,
                    baseline_relative_tolerance=0.1,
                    baseline_absolute_tolerance=absolute_tolerance,
                )
            ],
        )
    )
    finding = result.evaluation.findings[0]
    assert finding.relative_deviation is None
    assert finding.absolute_deviation == 30
    assert finding.status == (
        EvaluationStatus.ATTENTION if absolute_tolerance else EvaluationStatus.NOMINAL
    )


def test_unrepresentable_relative_deviation_is_null_but_exceedance_is_reported() -> None:
    result = monitor_activity(
        series(
            [1e308],
            baselines=[baseline_reference(statistics={"mean": 1e-308})],
            policies=[ActivityMetricPolicy(metric=DURATION, baseline_relative_tolerance=0.5)],
        )
    )
    finding = result.evaluation.findings[0]
    assert finding.relative_deviation is None
    assert finding.status == EvaluationStatus.ATTENTION
    assert "not representable" in finding.explanation


@pytest.mark.parametrize(
    "overrides",
    [
        {"crew_member_id": "other-crew"},
        {"status": BaselineStatus.PROVISIONAL},
        {"status": BaselineStatus.INSUFFICIENT_DATA},
        {"mission_phase": MissionPhaseType.PRE_FLIGHT},
        {"window_end": START + timedelta(hours=1)},
        {"window_start": START - timedelta(days=7)},
        {"computed_at": START + timedelta(days=31)},
        {"computed_at": START - timedelta(days=25)},
        {"sample_count": 0},
        {"statistics": BaselineStatistics(median=40)},
        {"statistics": BaselineStatistics(mean=-10)},
        {"data_quality": DataQuality(status=QualityStatus.DEGRADED)},
        {"data_quality": DataQuality(status=QualityStatus.UNUSABLE)},
        {"data_quality": DataQuality(status=QualityStatus.ACCEPTABLE, completeness=0.5)},
    ],
)
def test_incompatible_baselines_are_ignored_with_an_explanation(overrides: dict) -> None:
    result = monitor_activity(series([30], baselines=[baseline_reference(**overrides)]))
    assert result.evaluation.findings[0].baseline_id is None
    assert any("Ignored baseline" in notice for notice in result.notices)
    assert "Ignored baseline" in result.evaluation.findings[0].explanation


def test_unknown_phase_and_unconfirmed_comparability_prevent_baseline_use() -> None:
    reference = baseline_reference()
    unknown_phase = monitor_activity(series([30], baselines=[reference], mission_phase=None))
    assert unknown_phase.evaluation.findings[0].baseline_value is None
    unconfirmed = monitor_activity(
        series([30], baselines=[reference.model_copy(update={"comparable": False})])
    )
    assert unconfirmed.evaluation.findings[0].baseline_value is None


def test_latest_eligible_baseline_is_selected_without_using_future_or_provisional_data() -> None:
    references = [
        baseline_reference(
            baseline_id="old", window_end=START - timedelta(days=10), statistics={"mean": 35}
        ),
        baseline_reference(baseline_id="latest", statistics={"mean": 40}),
        baseline_reference(
            baseline_id="provisional",
            window_end=START - timedelta(days=2),
            computed_at=START - timedelta(days=1),
            status=BaselineStatus.PROVISIONAL,
        ),
    ]
    original = series([30], baselines=references)
    result = monitor_activity(original)
    reverse = monitor_activity(replace_request(original, baselines=references[::-1]))
    assert result.evaluation.findings[0].baseline_id == "latest"
    assert result.evaluation.findings[0].baseline_value == 40
    assert result.evaluation.findings == reverse.evaluation.findings


def test_energy_baseline_uses_kcal_and_its_own_policy() -> None:
    reference = baseline_reference(metric=ENERGY, unit="kcal", statistics={"mean": 300})
    result = monitor_activity(
        series(
            [30],
            [100],
            baselines=[reference],
            policies=[ActivityMetricPolicy(metric=ENERGY, baseline_absolute_tolerance=50)],
        )
    )
    finding = result.evaluation.findings[1]
    assert finding.unit == "kcal"
    assert finding.absolute_deviation == -200
    assert finding.status == EvaluationStatus.ATTENTION


def test_shared_finding_explains_actual_daily_override_and_weekly_miss_values() -> None:
    result = monitor_activity(
        series(
            [30] * 7,
            policies=[ActivityMetricPolicy(metric=DURATION, daily_target=20, weekly_target=220)],
            day_plans=[ActivityDayPlan(day=START.date(), daily_targets={DURATION: 35})],
        )
    )
    explanation = result.evaluation.findings[0].explanation
    assert "observed 30 < target 35 min" in explanation
    assert "observed 210 < target 220 min" in explanation
    assert "Day-specific target on 2026-11-02: 35 min" in explanation


def test_either_absolute_or_relative_tolerance_can_trigger_review() -> None:
    result = monitor_activity(
        series(
            [30],
            baselines=[baseline_reference()],
            policies=[
                ActivityMetricPolicy(
                    metric=DURATION, baseline_absolute_tolerance=5, baseline_relative_tolerance=0.9
                )
            ],
        )
    )
    finding = result.evaluation.findings[0]
    assert finding.status == EvaluationStatus.ATTENTION
    assert "observed 30 min; signed deviation -10 min" in finding.explanation


def test_missing_days_do_not_hide_a_confirmed_baseline_deviation() -> None:
    result = monitor_activity(
        series(
            [20, None],
            baselines=[baseline_reference()],
            policies=[ActivityMetricPolicy(metric=DURATION, baseline_absolute_tolerance=5)],
        )
    )
    assert result.evaluation.findings[0].status == EvaluationStatus.ATTENTION
    assert "remain unknown" in result.evaluation.findings[0].explanation
