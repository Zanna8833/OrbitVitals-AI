"""Scenario orchestration: generate inputs, call real engines, compare expectations.

No statistical estimator, quality classifier or physiological evaluator is implemented
here. Expected values are regression oracles for the documented synthetic protocol;
they never replace, patch or populate an engine result.
"""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

from pydantic import ValidationError

from app.algorithms.data_quality import DataQualityConfig, assess_measurements, assess_window
from app.algorithms.personal_baseline import build_baseline, build_baselines
from app.domains.physical_activity import ActivityMetricPolicy, ActivityRequest, monitor_activity
from app.domains.sleep import (
    analyze_sleep_observation,
    analyze_sleep_trends,
    evaluate_sleep_window,
)
from app.models import (
    BaselineStatus,
    EvaluationStatus,
    MetricType,
    MissionPhaseType,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from app.scenarios import fixtures
from app.scenarios.codec import json_value
from app.scenarios.models import (
    BaselineQuery,
    BehaviorCheck,
    QualityWindow,
    RejectedInput,
    ReplayInputs,
    ReplayOutputs,
    ReplayResult,
    ReplayStep,
    ScenarioInfo,
)

_COMMON_LIMITATIONS = (
    "All inputs and operational policies are simulated; tests are not clinical validation.",
    "An attention label requests human review; nominal does not establish health or safety.",
    "No clinical emergency, diagnosis, medical risk or treatment is inferred.",
)

_CATALOG = (
    ScenarioInfo(
        scenario_id="sensor_quality_failure",
        title="SIMULATED sensor quality failure",
        scientific_purpose="Separate measurement trustworthiness from physiological conclusions.",
        assumptions=(
            "One primary sleep summary per metric per UTC night is expected.",
            "Invalid percentages, negative durations and a redundant copy are deliberate faults.",
        ),
        limitations=(
            *_COMMON_LIMITATIONS,
            "No device range is configured; acceptable means the available checks passed.",
        ),
    ),
    ScenarioInfo(
        scenario_id="personalized_baseline",
        title="SIMULATED personalized physiological baseline",
        scientific_purpose="Show individual, phase-specific references and unavailable history.",
        assumptions=(
            "The fictional mission timeline and daily acquisition cadence are caller inputs.",
            "Ten samples over nine elapsed days is a demonstration establishment rule only.",
        ),
        limitations=(
            *_COMMON_LIMITATIONS,
            "The reference statistics are not population ranges or validated norms.",
        ),
    ),
    ScenarioInfo(
        scenario_id="progressive_sleep_restriction",
        title="SIMULATED progressive sleep restriction",
        scientific_purpose="Show actual time-aware sleep trends while retaining missing nights.",
        assumptions=(
            "Primary sleep periods start at 22:00 UTC in complete noon-to-noon buckets.",
            "Two nights are absent; no interpolation or zero filling is permitted.",
        ),
        limitations=(
            *_COMMON_LIMITATIONS,
            "Missingness may bias trends; no confidence interval or sleep-debt model exists.",
        ),
    ),
    ScenarioInfo(
        scenario_id="exercise_adherence_change",
        title="SIMULATED exercise adherence change",
        scientific_purpose="Review actual activity reductions and target adherence with coverage.",
        assumptions=(
            "Personal targets, planned rest and recording confirmations are explicit inputs.",
            "Minutes and energy are independently authored additive session measurements.",
        ),
        limitations=(
            *_COMMON_LIMITATIONS,
            "A known subtotal is not a complete day or proof of non-adherence.",
        ),
    ),
    ScenarioInfo(
        scenario_id="insufficient_data",
        title="SIMULATED insufficient or unusable data",
        scientific_purpose="Preserve unknown outcomes with inadequate observations or references.",
        assumptions=(
            "Schema-invalid payloads stop at Pydantic validation, before scientific engines.",
            "Missing records and unconfirmed recording coverage are not zero measurements.",
            "Steps are independent cases rather than one astronaut's physiological progression.",
        ),
        limitations=(
            *_COMMON_LIMITATIONS,
            "Unavailable baselines remain null; no reference is fabricated.",
        ),
    ),
)


def list_scenarios() -> tuple[ScenarioInfo, ...]:
    """Return fresh catalog entries in a stable presentation order, without engine calls."""
    return tuple(info.model_copy(deep=True) for info in _CATALOG)


def _check(check_id: str, description: str, expected: Any, actual: Any) -> BehaviorCheck:
    expected_json, actual_json = json_value(expected), json_value(actual)
    return BehaviorCheck(
        check_id=check_id,
        description=description,
        expected=expected_json,
        actual=actual_json,
        passed=expected_json == actual_json,
    )


def _display(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6g}"


def _sleep_step(
    step_id: str,
    measurements: tuple[PhysiologicalMeasurement, ...],
    nights_elapsed: int,
    expected_status: EvaluationStatus,
    purpose: str,
) -> ReplayStep:
    at = fixtures.SLEEP_START + nights_elapsed * fixtures.DAY
    quality_config = fixtures.daily_quality_policy(fixtures.SLEEP_METRICS)
    config = fixtures.sleep_policy()
    assessed = assess_measurements(measurements, assessed_at=at, config=quality_config)
    quality_windows = tuple(
        QualityWindow(
            metric=metric,
            window_start=fixtures.SLEEP_START,
            window_end=at,
            assessment=assess_window(
                measurements,
                crew_member_id=fixtures.CREW,
                metric=metric,
                window_start=fixtures.SLEEP_START,
                window_end=at,
                assessed_at=at,
                config=quality_config,
            ),
        )
        for metric in fixtures.SLEEP_METRICS
    )
    arguments = {
        "crew_member_id": fixtures.CREW,
        "window_start": fixtures.SLEEP_START,
        "window_end": at,
        "config": config,
    }
    trends = analyze_sleep_trends(assessed, **arguments)
    evaluation = evaluate_sleep_window(
        assessed,
        **arguments,
        evaluation_id=f"simulated-{step_id}",
        evaluated_at=at,
        mission_phase=MissionPhaseType.IN_FLIGHT,
        metric_data_quality={item.metric: item.assessment for item in quality_windows},
    )
    invalid_findings = tuple(
        analyze_sleep_observation(record, evaluated_at=at, config=config)
        for record in assessed
        if record.data_quality.status == QualityStatus.UNUSABLE
    )
    duration = trends[0]
    return ReplayStep(
        step_id=step_id,
        as_of=at,
        explanation=(
            f"SIMULATED checkpoint. {purpose} Actual sleep evaluation: {evaluation.status.value}. "
            f"Duration observations: {len(duration.observations)}/{len(duration.expected_nights)}; "
            f"slope: {_display(duration.slope_per_day)} min/day; "
            f"fitted change: {_display(duration.fitted_change)} min. "
            f"Missing duration nights: {', '.join(map(str, duration.missing_nights)) or 'none'}. "
            "Quality status describes observations. Evaluation labels are non-clinical review "
            "signals; no health or emergency conclusion follows from a corrupted sensor. "
            "Per-metric quality was assessed by the real engine; cross-metric window quality "
            "has no shared aggregation interface and remains not_assessed in this adapter."
        ),
        inputs=ReplayInputs(
            measurements=measurements,
            parameters=json_value(
                {
                    **arguments,
                    "config": config,
                    "evaluated_at": at,
                    "data_quality_config": quality_config,
                }
            ),
        ),
        outputs=ReplayOutputs(
            assessed_measurements=tuple(assessed),
            quality_windows=quality_windows,
            evaluations=(evaluation,),
            observation_findings=invalid_findings,
            sleep_trends=trends,
        ),
        checks=(
            _check(
                "evaluation_status",
                "Actual sleep status matches this checkpoint's expectation.",
                expected_status,
                evaluation.status,
            ),
            _check(
                "sleep_engine",
                "The result identifies the existing sleep algorithm.",
                "sleep_monitoring_trends",
                evaluation.algorithm.name,
            ),
            _check(
                "quality_engine",
                "Window assessments identify the existing quality engine.",
                ["data_quality", "data_quality"],
                [item.assessment.algorithm.name for item in quality_windows],
            ),
            _check(
                "no_emergency_label",
                "Quality failure does not create a physiological alert.",
                False,
                evaluation.status == EvaluationStatus.ALERT,
            ),
        ),
    )


def _sensor_quality_failure() -> tuple[ReplayStep, ...]:
    step = _sleep_step(
        "sensor-failure-assessment",
        fixtures.sensor_failure_records(),
        7,
        EvaluationStatus.NOMINAL,
        "The remaining constant values have no configured trend; nominal does not prove health.",
    )
    assessed = step.outputs.assessed_measurements
    step.checks += (
        _check(
            "unusable_observations",
            "Two corrupt observations and one redundant copy are unusable.",
            3,
            sum(item.data_quality.status == QualityStatus.UNUSABLE for item in assessed),
        ),
        _check(
            "duplicate_detected",
            "The real quality engine identifies the redundant copy.",
            1,
            sum(QualityFlag.DUPLICATE in item.data_quality.flags for item in assessed),
        ),
        _check(
            "artifacts_detected",
            "Definition violations are data artifacts, not diagnoses.",
            2,
            sum(QualityFlag.SIGNAL_ARTIFACT in item.data_quality.flags for item in assessed),
        ),
        _check(
            "quality_statuses",
            "The quality windows retain issues even with a nominal trend screen.",
            ["degraded", "degraded"],
            [item.assessment.status for item in step.outputs.quality_windows],
        ),
        _check(
            "retained_nights",
            "Only six eligible nights per metric enter trend analysis.",
            [6, 6],
            [len(item.observations) for item in step.outputs.sleep_trends],
        ),
        _check(
            "invalid_findings",
            "Unusable individual observations remain insufficient_data.",
            ["insufficient_data"] * 3,
            [item.status for item in step.outputs.observation_findings],
        ),
    )
    return (step,)


def _personalized_baseline() -> tuple[ReplayStep, ...]:
    measurements, phases = fixtures.baseline_inputs()
    steps = []
    # Source: docs/scientific-scenarios.md, fixture protocol: fixed checkpoints
    # exercise early history, phase transition, acquired history and policy absence.
    for step_id, elapsed, configured in (
        ("baseline-early-history", 3, True),
        ("baseline-after-launch", 16, True),
        ("baseline-in-flight-history", 30, True),
        ("baseline-no-establishment-policy", 30, False),
    ):
        at = fixtures.BASELINE_START + elapsed * fixtures.DAY
        available = tuple(record for record in measurements if record.measured_at < at)
        config = fixtures.baseline_policy(establishment_configured=configured)
        assessed = assess_measurements(available, assessed_at=at, config=config.quality)
        baselines = build_baselines(
            available,
            phases,
            computed_at=at,
            config=config,
            crew_member_ids=(fixtures.CREW,),
            metrics=(MetricType.HEART_RATE,),
        )
        requested_phase = (
            MissionPhaseType.IN_FLIGHT if elapsed < 30 else MissionPhaseType.POST_FLIGHT
        )
        queried = build_baseline(
            available,
            phases,
            crew_member_id=fixtures.CREW,
            metric=MetricType.HEART_RATE,
            mission_phase=requested_phase,
            computed_at=at,
            config=config,
        )
        pre_flight = next(
            item for item in baselines if item.mission_phase == MissionPhaseType.PRE_FLIGHT
        )
        checks = [
            _check(
                "baseline_engine",
                "Every reference is produced by the existing baseline engine.",
                ["personal_baseline"] * len(baselines),
                [item.algorithm.name for item in baselines],
            ),
            _check(
                "unavailable_phase",
                "A future phase has no reference window or invented baseline.",
                None,
                queried,
            ),
            _check(
                "pre_flight_count",
                "Only quality-admitted history in pre-flight is used.",
                3 if elapsed == 3 else 14,
                pre_flight.sample_count,
            ),
            _check(
                "pre_flight_status",
                "Status follows available history and the explicit policy.",
                BaselineStatus.ESTABLISHED
                if configured and elapsed >= 16
                else BaselineStatus.PROVISIONAL,
                pre_flight.status,
            ),
        ]
        if elapsed >= 16:
            launch = next(
                item for item in baselines if item.mission_phase == MissionPhaseType.LAUNCH
            )
            checks.extend(
                (
                    _check(
                        "launch_status",
                        "One launch observation cannot support reference statistics.",
                        BaselineStatus.INSUFFICIENT_DATA,
                        launch.status,
                    ),
                    _check(
                        "launch_statistics",
                        "Insufficient launch statistics remain absent.",
                        None,
                        launch.statistics.mean,
                    ),
                )
            )
        if elapsed == 30:
            flight = next(
                item for item in baselines if item.mission_phase == MissionPhaseType.IN_FLIGHT
            )
            checks.extend(
                (
                    _check(
                        "phase_medians",
                        "References stay phase-specific rather than pooling a population.",
                        [58.0, 64.0],
                        [pre_flight.statistics.median, flight.statistics.median],
                    ),
                    _check(
                        "flight_usable_count",
                        "The two definition-invalid readings are not admitted.",
                        12,
                        flight.sample_count,
                    ),
                    _check(
                        "flight_quality",
                        "Reference availability and data quality remain separate.",
                        QualityStatus.DEGRADED,
                        flight.data_quality.status,
                    ),
                    _check(
                        "flight_status",
                        "Reference status follows the configured establishment criteria.",
                        BaselineStatus.ESTABLISHED if configured else BaselineStatus.PROVISIONAL,
                        flight.status,
                    ),
                )
            )
        descriptions = "; ".join(
            f"{item.mission_phase.value}: {item.status.value}, n={item.sample_count}, "
            f"median={_display(item.statistics.median)} {item.unit}, "
            f"quality={item.data_quality.status.value}"
            for item in baselines
        )
        steps.append(
            ReplayStep(
                step_id=step_id,
                as_of=at,
                explanation=(
                    f"SIMULATED references from the baseline engine: {descriptions}. "
                    f"Requested {requested_phase.value} reference: "
                    f"{'available' if queried else 'unavailable'}. "
                    "Establishment criteria are demonstration policy, not validation evidence. "
                    "The final step compares policy choices at the same observation horizon. "
                    "These statistics do not classify the astronaut as healthy or ill."
                ),
                inputs=ReplayInputs(
                    measurements=available,
                    mission_phases=phases,
                    parameters=json_value(
                        {
                            "crew_member_id": fixtures.CREW,
                            "metrics": [MetricType.HEART_RATE],
                            "computed_at": at,
                            "baseline_config": config,
                            "queried_phase": requested_phase,
                        }
                    ),
                ),
                outputs=ReplayOutputs(
                    assessed_measurements=tuple(assessed),
                    baselines=tuple(baselines),
                    baseline_queries=(
                        BaselineQuery(
                            metric=MetricType.HEART_RATE,
                            mission_phase=requested_phase,
                            baseline=queried,
                        ),
                    ),
                ),
                checks=tuple(checks),
            )
        )
    return tuple(steps)


def _progressive_sleep_restriction() -> tuple[ReplayStep, ...]:
    records = fixtures.restriction_records()
    steps = []
    for elapsed in (2, 5, 9):
        at = fixtures.SLEEP_START + elapsed * fixtures.DAY
        available = tuple(record for record in records if record.interval_end <= at)
        step = _sleep_step(
            f"sleep-restriction-night-{elapsed}",
            available,
            elapsed,
            EvaluationStatus.INSUFFICIENT_DATA if elapsed == 2 else EvaluationStatus.ATTENTION,
            "Only completed observations known at this checkpoint are replayed; gaps stay unknown.",
        )
        duration = step.outputs.sleep_trends[0]
        step.checks += (
            _check(
                "actual_slope",
                "Elapsed-time slope preserves the constructed daily reduction.",
                -15.0,
                duration.slope_per_day,
            ),
            _check(
                "eligible_nights",
                "Missing nights are excluded instead of filled with zeros.",
                {2: 2, 5: 4, 9: 7}[elapsed],
                len(duration.observations),
            ),
            _check(
                "duration_signal",
                "Only sufficient history can produce a progressive reduction signal.",
                None if elapsed == 2 else "progressive_duration_reduction",
                duration.signal,
            ),
        )
        if elapsed == 9:
            step.checks += (
                _check(
                    "fitted_change",
                    "Report the real fitted change over eight elapsed days.",
                    -120.0,
                    duration.fitted_change,
                ),
                _check(
                    "missing_nights",
                    "Two absent nights remain explicit in the trend output.",
                    ["2026-11-03", "2026-11-07"],
                    duration.missing_nights,
                ),
                _check(
                    "baseline_not_invented",
                    "A trend does not synthesize a personal baseline.",
                    None,
                    step.outputs.evaluations[0].findings[0].baseline_value,
                ),
            )
        steps.append(step)
    return tuple(steps)


def _activity_step(
    step_id: str,
    request: ActivityRequest,
    raw_measurements: tuple[PhysiologicalMeasurement, ...],
    expected_status: EvaluationStatus,
) -> ReplayStep:
    report = monitor_activity(request)
    return ReplayStep(
        step_id=step_id,
        as_of=request.evaluated_at,
        explanation=(
            f"SIMULATED activity checkpoint: {report.evaluation.status.value}; "
            f"{len(report.trends)} real reduction runs across {len(report.days)} UTC days. "
            "The report preserves known subtotals, planned rest and unknown target outcomes. "
            "Targets describe the supplied fictional mission plan, not an exercise prescription. "
            "No personal daily-total baseline is supplied or inferred."
        ),
        inputs=ReplayInputs(
            measurements=raw_measurements,
            activity_request=request,
            parameters=json_value({"data_quality_config": DataQualityConfig()}),
        ),
        outputs=ReplayOutputs(
            assessed_measurements=request.measurements,
            evaluations=(report.evaluation,),
            activity_report=report,
        ),
        checks=(
            _check(
                "evaluation_status",
                "Activity status comes from the actual monitor.",
                expected_status,
                report.evaluation.status,
            ),
            _check(
                "activity_engine",
                "The evaluation identifies the existing activity module.",
                "physical_activity_monitor",
                report.evaluation.algorithm.name,
            ),
            _check(
                "no_emergency_label",
                "Target adherence does not assign a clinical emergency.",
                False,
                report.evaluation.status == EvaluationStatus.ALERT,
            ),
        ),
    )


def _exercise_adherence_change() -> tuple[ReplayStep, ...]:
    measurements, sessions, coverage, plans, policies = fixtures.activity_inputs()
    steps = []
    for elapsed in (7, 14):
        at = fixtures.ACTIVITY_START + elapsed * fixtures.DAY
        available = tuple(record for record in measurements if record.interval_end <= at)
        assessed = assess_measurements(available, assessed_at=at, config=DataQualityConfig())
        request = ActivityRequest(
            crew_member_id=fixtures.CREW,
            window_start=fixtures.ACTIVITY_START,
            window_end=at,
            evaluated_at=at,
            evaluation_id=f"simulated-activity-day-{elapsed}",
            measurements=tuple(assessed),
            sessions=tuple(item for item in sessions if item.end_time <= at),
            coverage=tuple(item for item in coverage if item.day < at.date()),
            day_plans=tuple(item for item in plans if item.day < at.date()),
            policies=policies,
            mission_phase=MissionPhaseType.IN_FLIGHT,
            reduction_run_length=3,
            context_notes="SIMULATED targets, rest schedule and recording confirmations.",
        )
        step = _activity_step(
            f"activity-day-{elapsed}", request, available, EvaluationStatus.ATTENTION
        )
        report = step.outputs.activity_report
        rest = report.days[5]
        step.checks += (
            _check(
                "duration_reduction",
                "The first actual duration run contains five decreasing totals.",
                [60, 55, 50, 45, 40],
                next(
                    trend.values
                    for trend in report.trends
                    if trend.metric == MetricType.EXERCISE_DURATION
                ),
            ),
            _check(
                "rest_day",
                "Scheduled rest suspends daily target comparison for both metrics.",
                ["not_applicable", "not_applicable"],
                [item.target_outcome for item in rest.metrics],
            ),
            _check(
                "complete_week",
                "The fully recorded first week meets the configured targets.",
                ["met", "met"],
                [item.target_outcome for item in report.weeks[0].metrics],
            ),
        )
        if elapsed == 14:
            partial, missing = report.days[10], report.days[11]
            step.checks += (
                _check(
                    "partial_day",
                    "A known duration subtotal and absent energy stay unknown.",
                    ["unknown", "unknown"],
                    [item.target_outcome for item in partial.metrics],
                ),
                _check(
                    "known_subtotals",
                    "Incomplete observations are not promoted to complete totals.",
                    [15.0, None],
                    [item.observed_total for item in partial.metrics],
                ),
                _check(
                    "missing_records",
                    "Absent observations and coverage remain null, never zero.",
                    [None, None],
                    [item.observed_total for item in missing.metrics],
                ),
                _check(
                    "incomplete_week",
                    "An incomplete week is not a proven missed weekly target.",
                    ["unknown", "unknown"],
                    [item.target_outcome for item in report.weeks[1].metrics],
                ),
                _check(
                    "run_count",
                    "Rest and missing/incomplete days break reduction runs.",
                    4,
                    len(report.trends),
                ),
            )
        steps.append(step)
    return tuple(steps)


def _insufficient_data() -> tuple[ReplayStep, ...]:
    missing = _sleep_step(
        "insufficient-missing-observations",
        (),
        5,
        EvaluationStatus.INSUFFICIENT_DATA,
        "No sleep observations exist; the engines cannot invent sleep or a personal reference.",
    )
    # This deliberately invalid unit cannot enter the shared measurement contract.
    # The real Pydantic validator, rather than a quality/status fixture, rejects it.
    candidate = json_value(
        fixtures.simulated_measurement(
            "sim-invalid-unit",
            MetricType.SLEEP_DURATION,
            8,
            fixtures.SLEEP_START,
        )
    )
    candidate["unit"] = "hours"
    rejected = ()
    try:
        PhysiologicalMeasurement.model_validate(candidate)
    except ValidationError as error:
        rejected = (
            RejectedInput(
                payload=candidate,
                validation_errors=tuple(item["msg"] for item in error.errors(include_url=False)),
            ),
        )
    missing.inputs.rejected_candidates = (candidate,)
    missing.outputs.rejected_inputs = rejected
    missing.checks += (
        _check(
            "invalid_contract_rejected",
            "Noncanonical input stops at the real contract validator.",
            1,
            len(rejected),
        ),
        _check(
            "no_observed_values",
            "An empty window has no invented observed metric values.",
            [None, None],
            [item.observed_value for item in missing.outputs.evaluations[0].findings],
        ),
    )
    invalid_records = fixtures.sleep_records(
        "unusable-only",
        (-30,) * 5,
        (125,) * 5,
    )
    unusable = _sleep_step(
        "insufficient-unusable-observations",
        invalid_records,
        5,
        EvaluationStatus.INSUFFICIENT_DATA,
        "Records exist but definition violations make all of them unusable.",
    )
    unusable.checks += (
        _check(
            "unusable_quality",
            "Both real quality windows are unusable.",
            ["unusable", "unusable"],
            [item.assessment.status for item in unusable.outputs.quality_windows],
        ),
        _check(
            "no_invented_values",
            "Unusable measurements do not produce observed sleep statistics.",
            [None, None],
            [item.observed_value for item in unusable.outputs.evaluations[0].findings],
        ),
    )

    _, phases = fixtures.baseline_inputs()
    single = (
        fixtures.simulated_measurement(
            "sim-insufficient-reference",
            MetricType.HEART_RATE,
            64,
            fixtures.BASELINE_START + 16 * fixtures.DAY + timedelta(hours=9),
        ),
    )
    at = fixtures.BASELINE_START + 30 * fixtures.DAY
    config = fixtures.baseline_policy()
    reference = build_baseline(
        single,
        phases,
        crew_member_id=fixtures.CREW,
        metric=MetricType.HEART_RATE,
        mission_phase=MissionPhaseType.IN_FLIGHT,
        computed_at=at,
        config=config,
    )
    absent_reference = build_baseline(
        single,
        phases,
        crew_member_id=fixtures.CREW,
        metric=MetricType.HEART_RATE,
        mission_phase=MissionPhaseType.POST_FLIGHT,
        computed_at=at,
        config=config,
    )
    reference_step = ReplayStep(
        step_id="insufficient-baseline-information",
        as_of=at,
        explanation=(
            f"SIMULATED reference: {reference.status.value}, n={reference.sample_count}, "
            f"mean={_display(reference.statistics.mean)}. The future post-flight query returns "
            f"{'null' if absent_reference is None else 'a reference'}. "
            "Lack of reference information is not a conclusion about the astronaut."
        ),
        inputs=ReplayInputs(
            measurements=single,
            mission_phases=phases,
            parameters=json_value({"baseline_config": config, "computed_at": at}),
        ),
        outputs=ReplayOutputs(
            assessed_measurements=tuple(
                assess_measurements(single, assessed_at=at, config=config.quality)
            ),
            baselines=(reference,),
            baseline_queries=(
                BaselineQuery(
                    metric=MetricType.HEART_RATE,
                    mission_phase=MissionPhaseType.POST_FLIGHT,
                    baseline=absent_reference,
                ),
            ),
        ),
        checks=(
            _check(
                "reference_status",
                "One sample is insufficient for this baseline engine.",
                BaselineStatus.INSUFFICIENT_DATA,
                reference.status,
            ),
            _check(
                "reference_statistics",
                "No reference statistic is fabricated.",
                None,
                reference.statistics.mean,
            ),
            _check(
                "unavailable_reference",
                "A future reference remains unavailable.",
                None,
                absent_reference,
            ),
        ),
    )
    activity_at = fixtures.ACTIVITY_START + 3 * fixtures.DAY
    raw_activity = (
        fixtures.simulated_measurement(
            "sim-unconfirmed-exercise",
            MetricType.EXERCISE_DURATION,
            30,
            fixtures.ACTIVITY_START + timedelta(hours=9),
            interval_end=fixtures.ACTIVITY_START + timedelta(hours=10),
        ),
    )
    assessed_activity = assess_measurements(raw_activity, assessed_at=activity_at)
    request = ActivityRequest(
        crew_member_id=fixtures.CREW,
        window_start=fixtures.ACTIVITY_START,
        window_end=activity_at,
        evaluated_at=activity_at,
        evaluation_id="simulated-unconfirmed-activity",
        measurements=tuple(assessed_activity),
        mission_phase=MissionPhaseType.IN_FLIGHT,
        policies=(ActivityMetricPolicy(metric=MetricType.EXERCISE_DURATION, daily_target=40),),
        context_notes="SIMULATED subtotal without complete coverage or an established baseline.",
        reduction_run_length=3,
    )
    activity = _activity_step(
        "insufficient-unconfirmed-activity",
        request,
        raw_activity,
        EvaluationStatus.INSUFFICIENT_DATA,
    )
    activity.checks += (
        _check(
            "unknown_target",
            "A partial record is not a proven missed daily target.",
            "unknown",
            activity.outputs.activity_report.days[0].metrics[0].target_outcome,
        ),
        _check(
            "no_baseline",
            "No personal activity baseline is invented.",
            None,
            activity.outputs.evaluations[0].findings[0].baseline_value,
        ),
    )
    return reference_step, activity, missing, unusable


_RUNNERS: dict[str, Callable[[], tuple[ReplayStep, ...]]] = {
    "sensor_quality_failure": _sensor_quality_failure,
    "personalized_baseline": _personalized_baseline,
    "progressive_sleep_restriction": _progressive_sleep_restriction,
    "exercise_adherence_change": _exercise_adherence_change,
    "insufficient_data": _insufficient_data,
}


def replay_scenario(scenario_id: str) -> ReplayResult:
    """Generate a fresh deterministic replay using only existing scientific interfaces."""
    if scenario_id not in _RUNNERS:
        raise ValueError(f"Unknown scenario: {scenario_id}")
    info = next(info for info in list_scenarios() if info.scenario_id == scenario_id)
    steps = _RUNNERS[scenario_id]()
    result = ReplayResult(
        scenario=info,
        steps=steps,
        all_checks_passed=all(
            step.checks and not step.blockers and all(check.passed for check in step.checks)
            for step in steps
        ),
    )
    # Detach the snapshot from mutable algorithm-info constants owned by the engines.
    # Copying preserves values and provenance; it never rewrites an algorithm result.
    return result.model_copy(deep=True)
