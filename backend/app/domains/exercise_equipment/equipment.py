"""Checks the exercise sessions logged by a crew member against their personal exercise plan.

On the International Space Station the crew trains on three devices: a resistance device (ARED:
squat, deadlift, heel raise...), a treadmill with a harness that pulls them onto the belt (T2) and
a cycle ergometer (CEVIS). NASA reports these sessions as volume load (sets x repetitions x kg),
harness load as a percentage of body weight, work rate in watts and heart rate (English et al.
2020, NASA Sprint Study, npj Microgravity 6:21). Every target comes from the plan written by the
crew's trainers: nothing here is a clinical threshold, and the result is not a diagnosis.
"""

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from app.models import (
    AlgorithmInfo,
    ContractModel,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MetricFinding,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    QualityStatus,
)
from app.models.common import Identifier

ALGORITHM = AlgorithmInfo(name="exercise_equipment", version="0.1.0")

# Peak load of the station's resistance device (English et al. 2020): a heavier logged load
# cannot be real.
RESISTANCE_DEVICE_MAX_LOAD_KG = 272


class Device(StrEnum):
    RESISTANCE = "resistance"  # ARED on the station
    TREADMILL = "treadmill"  # T2
    CYCLE = "cycle"  # CEVIS


class ResistanceExercise(ContractModel):
    """One exercise of a resistance session, e.g. 4 sets of 8 squats at 100 kg."""

    exercise: Identifier
    sets: int = Field(ge=1)
    repetitions: int = Field(ge=1, description="Repetitions in each set.")
    load_kg: float = Field(gt=0, le=RESISTANCE_DEVICE_MAX_LOAD_KG)


class FitnessTestStage(ContractModel):
    """One stage of a submaximal cycle fitness test: steady heart rate at a fixed work rate."""

    work_rate_w: float = Field(gt=0)
    heart_rate_bpm: float = Field(gt=0)


class ExerciseLog(ContractModel):
    """One exercise session as logged by the crew member.

    A cycle session with `fitness_test_stages` is a periodic fitness test; NASA runs one about
    every 30 days in flight (Moore et al. 2014).
    """

    session_id: Identifier
    crew_member_id: Identifier
    device: Device
    started_at: AwareDatetime
    resistance_exercises: list[ResistanceExercise] = []
    subject_load_percent: float | None = Field(
        default=None, gt=0, description="Treadmill harness load, as a percentage of body weight."
    )
    work_rate_w: float | None = Field(default=None, gt=0, description="Cycle training work rate.")
    heart_rate_bpm: float | None = Field(default=None, gt=0, description="Mean heart rate.")
    fitness_test_stages: list[FitnessTestStage] = []

    @model_validator(mode="after")
    def _check_device_fields(self) -> Self:
        is_resistance = self.device == Device.RESISTANCE
        if is_resistance != (len(self.resistance_exercises) > 0):
            raise ValueError("A resistance session, and only one, must list its exercises")
        if self.subject_load_percent is not None and self.device != Device.TREADMILL:
            raise ValueError("Harness load is logged only for treadmill sessions")
        has_cycle_values = self.work_rate_w is not None or len(self.fitness_test_stages) > 0
        if has_cycle_values and self.device != Device.CYCLE:
            raise ValueError("Work rate and fitness test stages are logged only for cycle sessions")
        return self


class PrescribedExercise(ContractModel):
    """One resistance exercise of the plan, to be done in every resistance session."""

    exercise: Identifier
    sets: int = Field(ge=1)
    repetitions: int = Field(ge=1)
    load_kg: float = Field(gt=0, le=RESISTANCE_DEVICE_MAX_LOAD_KG)


class ExercisePlan(ContractModel):
    """Personal targets set by the trainers for the evaluated window. A missing target leaves
    its check without a status. Treadmill and cycle targets are minimums."""

    resistance_exercises: list[PrescribedExercise] = []
    treadmill_subject_load_percent: float | None = Field(default=None, gt=0)
    treadmill_heart_rate_bpm: float | None = Field(default=None, gt=0)
    cycle_work_rate_w: float | None = Field(default=None, gt=0)
    fitness_heart_rate_tolerance_bpm: float | None = Field(
        default=None,
        ge=0,
        description="Largest accepted rise of fitness-test heart rate over the pre-flight test.",
    )


def volume_load(sets: int, repetitions: int, load_kg: float) -> float:
    return sets * repetitions * load_kg


def launch_time(mission_phases: list[MissionPhase]) -> datetime | None:
    """Start of the in-flight phase. None when it is not known."""
    for phase in mission_phases:
        if phase.phase == MissionPhaseType.IN_FLIGHT:
            return phase.start_time
    return None


def phase_at(moment: datetime, mission_phases: list[MissionPhase]) -> MissionPhaseType | None:
    for phase in mission_phases:
        if phase.start_time <= moment and (phase.end_time is None or moment < phase.end_time):
            return phase.phase
    return None


def day_text(log: ExerciseLog) -> str:
    return log.started_at.date().isoformat()


def finding_with_deviation(
    metric: MetricType,
    unit: str,
    status: EvaluationStatus,
    observed: float,
    reference: float,
    explanation: str,
) -> MetricFinding:
    absolute_deviation = observed - reference
    relative_deviation = None
    if reference != 0:
        relative_deviation = round(absolute_deviation / reference, 4)
    return MetricFinding(
        metric=metric,
        unit=unit,
        status=status,
        observed_value=round(observed, 2),
        baseline_value=round(reference, 2),
        absolute_deviation=round(absolute_deviation, 2),
        relative_deviation=relative_deviation,
        explanation=explanation,
    )


def insufficient_finding(metric: MetricType, unit: str, explanation: str) -> MetricFinding:
    return MetricFinding(
        metric=metric,
        unit=unit,
        status=EvaluationStatus.INSUFFICIENT_DATA,
        explanation=explanation,
    )


def check_resistance(logs: list[ExerciseLog], plan: ExercisePlan) -> MetricFinding:
    """Volume load of every prescribed exercise in every resistance session, against the plan.
    Exercises that are not in the plan are extra work and are not counted."""
    metric = MetricType.RESISTANCE_VOLUME_LOAD
    if len(plan.resistance_exercises) == 0:
        return insufficient_finding(metric, "kg", "The plan has no resistance exercise.")
    sessions = []
    for log in logs:
        if log.device == Device.RESISTANCE:
            sessions.append(log)
    if len(sessions) == 0:
        return insufficient_finding(metric, "kg", "No resistance session logged in the window.")

    done_total = 0.0
    prescribed_total = 0.0
    below_plan = []
    for session in sessions:
        for prescribed in plan.resistance_exercises:
            prescribed_volume = volume_load(
                prescribed.sets, prescribed.repetitions, prescribed.load_kg
            )
            done_volume = 0.0
            for exercise in session.resistance_exercises:
                if exercise.exercise != prescribed.exercise:
                    continue
                done_volume += volume_load(exercise.sets, exercise.repetitions, exercise.load_kg)
            done_total += done_volume
            prescribed_total += prescribed_volume
            if done_volume < prescribed_volume:
                below_plan.append(
                    f"{prescribed.exercise} on {day_text(session)} "
                    f"({done_volume:g} of {prescribed_volume:g} kg)"
                )

    explanation = (
        f"Resistance sessions in the window: {len(sessions)}. {done_total:g} kg lifted against "
        f"{prescribed_total:g} kg prescribed (sets x repetitions x load)."
    )
    status = EvaluationStatus.NOMINAL
    if len(below_plan) > 0:
        status = EvaluationStatus.ATTENTION
        explanation = f"{explanation} Below the plan: {', '.join(below_plan)}."
    return finding_with_deviation(metric, "kg", status, done_total, prescribed_total, explanation)


def check_minimum(
    metric: MetricType,
    unit: str,
    sessions: list[ExerciseLog],
    values: list[float],
    target: float | None,
    label: str,
) -> MetricFinding:
    """Mean of the logged values against a minimum from the plan; values[i] belongs to
    sessions[i]. Every session below the minimum needs attention."""
    if target is None:
        return insufficient_finding(metric, unit, f"The plan sets no {label}.")
    if len(values) == 0:
        return insufficient_finding(metric, unit, f"No session with a logged {label}.")

    below_plan = []
    for index in range(len(values)):
        if values[index] < target:
            below_plan.append(f"{values[index]:g} {unit} on {day_text(sessions[index])}")
    mean = sum(values) / len(values)
    explanation = (
        f"Sessions in the window: {len(values)}. Mean {label} {mean:.1f} {unit}, "
        f"plan minimum {target:g} {unit}."
    )
    status = EvaluationStatus.NOMINAL
    if len(below_plan) > 0:
        status = EvaluationStatus.ATTENTION
        explanation = f"{explanation} Below the plan: {', '.join(below_plan)}."
    return finding_with_deviation(metric, unit, status, mean, target, explanation)


def latest_fitness_test(
    logs: list[ExerciseLog], start: datetime | None, end: datetime | None
) -> ExerciseLog | None:
    """Latest cycle session with fitness test stages, started in [start, end)."""
    latest = None
    for log in logs:
        if len(log.fitness_test_stages) == 0:
            continue
        if start is not None and log.started_at < start:
            continue
        if end is not None and log.started_at >= end:
            continue
        if latest is None or log.started_at > latest.started_at:
            latest = log
    return latest


def check_fitness_test(
    logs: list[ExerciseLog],
    window_logs: list[ExerciseLog],
    plan: ExercisePlan,
    launch: datetime | None,
) -> MetricFinding:
    """Heart rate of the latest in-flight fitness test against the latest pre-flight test,
    stage by stage at the same work rate (Moore et al. 2014): a higher heart rate at the same
    work rate is a sign of lower aerobic fitness."""
    metric = MetricType.HEART_RATE
    if launch is None:
        return insufficient_finding(
            metric, "bpm", "The launch date is unknown, so no test can be called pre-flight."
        )
    pre_flight = latest_fitness_test(logs, None, launch)
    if pre_flight is None:
        return insufficient_finding(metric, "bpm", "No pre-flight fitness test logged.")
    in_flight = latest_fitness_test(window_logs, launch, None)
    if in_flight is None:
        return insufficient_finding(metric, "bpm", "No in-flight fitness test in the window.")

    in_flight_rates = []
    pre_flight_rates = []
    stage_texts = []
    largest_rise = None
    for stage in in_flight.fitness_test_stages:
        for reference in pre_flight.fitness_test_stages:
            if reference.work_rate_w != stage.work_rate_w:
                continue
            rise = stage.heart_rate_bpm - reference.heart_rate_bpm
            in_flight_rates.append(stage.heart_rate_bpm)
            pre_flight_rates.append(reference.heart_rate_bpm)
            stage_texts.append(
                f"{stage.heart_rate_bpm:g} bpm against {reference.heart_rate_bpm:g} bpm at "
                f"{stage.work_rate_w:g} W"
            )
            if largest_rise is None or rise > largest_rise:
                largest_rise = rise
            break
    if len(in_flight_rates) == 0:
        return insufficient_finding(
            metric, "bpm", "The in-flight and pre-flight fitness tests share no work rate."
        )

    explanation = (
        f"Fitness test of {day_text(in_flight)} against the pre-flight test of "
        f"{day_text(pre_flight)}: {', '.join(stage_texts)}."
    )
    tolerance = plan.fitness_heart_rate_tolerance_bpm
    if tolerance is None:
        status = EvaluationStatus.INSUFFICIENT_DATA
        explanation = f"{explanation} The plan sets no tolerance, so no status is given."
    elif largest_rise > tolerance:
        status = EvaluationStatus.ATTENTION
        explanation = (
            f"{explanation} Heart rate rose by up to {largest_rise:g} bpm at the same work rate,"
            f" more than the {tolerance:g} bpm accepted by the plan: aerobic fitness may be lower."
        )
    else:
        status = EvaluationStatus.NOMINAL
        explanation = f"{explanation} Within the {tolerance:g} bpm accepted by the plan."
    observed = sum(in_flight_rates) / len(in_flight_rates)
    reference = sum(pre_flight_rates) / len(pre_flight_rates)
    return finding_with_deviation(metric, "bpm", status, observed, reference, explanation)


def evaluate_exercise_equipment(
    crew_member_id: str,
    logs: list[ExerciseLog],
    plan: ExercisePlan,
    mission_phases: list[MissionPhase],
    window_start: datetime,
    window_end: datetime,
    evaluated_at: datetime,
    evaluation_id: str,
) -> EvaluationResult:
    """Evaluates the sessions of one crew member started in [window_start, window_end).

    The plan applies to the whole window: when the trainers change it (for example the harness
    load rising from 60% to 80% of body weight), evaluate the two periods separately. Sessions of
    other crew members are ignored. The pre-flight fitness test may come before the window.
    """
    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    if window_end > evaluated_at:
        raise ValueError("window_end cannot be after evaluated_at")

    own_logs = []
    window_logs = []
    for log in logs:
        if log.crew_member_id != crew_member_id or log.started_at >= window_end:
            continue
        own_logs.append(log)
        if log.started_at >= window_start:
            window_logs.append(log)

    treadmill_load_sessions = []
    treadmill_loads = []
    treadmill_heart_sessions = []
    treadmill_heart_rates = []
    cycle_sessions = []
    cycle_work_rates = []
    for log in window_logs:
        if log.subject_load_percent is not None:
            treadmill_load_sessions.append(log)
            treadmill_loads.append(log.subject_load_percent)
        if log.device == Device.TREADMILL and log.heart_rate_bpm is not None:
            treadmill_heart_sessions.append(log)
            treadmill_heart_rates.append(log.heart_rate_bpm)
        if log.work_rate_w is not None:
            cycle_sessions.append(log)
            cycle_work_rates.append(log.work_rate_w)

    labels = [
        "resistance volume load",
        "treadmill harness load",
        "treadmill heart rate",
        "cycle work rate",
        "fitness test heart rate",
    ]
    findings = [
        check_resistance(window_logs, plan),
        check_minimum(
            MetricType.TREADMILL_SUBJECT_LOAD,
            "%",
            treadmill_load_sessions,
            treadmill_loads,
            plan.treadmill_subject_load_percent,
            labels[1],
        ),
        check_minimum(
            MetricType.HEART_RATE,
            "bpm",
            treadmill_heart_sessions,
            treadmill_heart_rates,
            plan.treadmill_heart_rate_bpm,
            labels[2],
        ),
        check_minimum(
            MetricType.CYCLE_WORK_RATE,
            "W",
            cycle_sessions,
            cycle_work_rates,
            plan.cycle_work_rate_w,
            labels[3],
        ),
        check_fitness_test(own_logs, window_logs, plan, launch_time(mission_phases)),
    ]

    attention = []
    evaluated = 0
    for index in range(len(findings)):
        if findings[index].status == EvaluationStatus.ATTENTION:
            attention.append(labels[index])
        if findings[index].status != EvaluationStatus.INSUFFICIENT_DATA:
            evaluated += 1
    if len(attention) > 0:
        status = EvaluationStatus.ATTENTION
        summary = "Below the exercise plan, to review: " + ", ".join(attention) + "."
    elif evaluated > 0:
        status = EvaluationStatus.NOMINAL
        summary = "The logged exercise sessions match the plan."
    else:
        status = EvaluationStatus.INSUFFICIENT_DATA
        summary = "Not enough logged sessions or plan targets to evaluate exercise."

    return EvaluationResult(
        evaluation_id=evaluation_id,
        crew_member_id=crew_member_id,
        domain=HealthDomain.PHYSICAL_ACTIVITY,
        mission_phase=phase_at(window_start, mission_phases),
        window_start=window_start,
        window_end=window_end,
        status=status,
        summary=summary,
        findings=findings,
        # Logged by hand: no quality algorithm has assessed these values
        data_quality=DataQuality(status=QualityStatus.NOT_ASSESSED),
        algorithm=ALGORITHM,
        evaluated_at=evaluated_at,
    )
