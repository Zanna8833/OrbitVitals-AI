"""Checks whether an astronaut's blood pressure and body temperature are normal for spaceflight.

There is no official NASA table of normal in-flight vital signs: each reading is compared with the
same astronaut's pre-flight baseline, shifted by the changes published for long-duration ISS flight.

Input and output use the shared contracts in app.models: measurements (PhysiologicalMeasurement),
personal baselines (PersonalBaseline, computed elsewhere), the mission timeline (MissionPhase) and
the result (EvaluationResult with one MetricFinding per metric).
"""

from datetime import datetime

from app.models import (
    AlgorithmInfo,
    BaselineStatus,
    DataQuality,
    EvaluationResult,
    EvaluationStatus,
    HealthDomain,
    MetricFinding,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
    QualityStatus,
)

ALGORITHM = AlgorithmInfo(name="vital_signs_expected_range", version="0.1.0")

# Blood pressure: equal to or up to about 10 mmHg below the pre-flight baseline is expected in
# flight (Norsk et al. 2015, J Physiol: 24-h BP -8/-9 mmHg; Hughson et al. 2012, J Appl Physiol:
# no change at rest).
BP_EXPECTED_DROP = 10  # mmHg
# Measurement error: BP monitors are validated for a mean error up to 5 mmHg
# (ISO 81060-2, Stergiou et al. 2018).
BP_MARGIN = 5  # mmHg

# Resting core temperature rises by about 1 degC, gradually, with a plateau after about 75 days
# (Stahn et al. 2017, Sci Rep). The curve is published only as a figure: the linear rise is our
# assumption.
TEMP_EXPECTED_RISE = 1.0  # degC
TEMP_RISE_DAYS = 75
# Day-to-day variability of body temperature in healthy adults: 0.32 degC (PMC7857558).
TEMP_MARGIN = 0.3  # degC

# Second check against the personal in-flight baseline (computed by the baseline algorithm):
# with one reading per day, 2 standard deviations gave a false alarm about every 20 days for
# healthy crew, so the limit is 3.
IN_FLIGHT_SD_LIMIT = 3

BLOOD_PRESSURE_METRICS = [MetricType.SYSTOLIC_BLOOD_PRESSURE, MetricType.DIASTOLIC_BLOOD_PRESSURE]
EVALUATED_METRICS = [
    MetricType.SYSTOLIC_BLOOD_PRESSURE,
    MetricType.DIASTOLIC_BLOOD_PRESSURE,
    MetricType.BODY_TEMPERATURE,
]

# 'alert' is never assigned: no sourced threshold separates it from 'attention'.


def expected_temperature_rise(day: int) -> float:
    """Expected rise of resting core temperature on a given mission day (0 before launch)."""
    if day <= 0:
        return 0.0
    if day >= TEMP_RISE_DAYS:
        return TEMP_EXPECTED_RISE
    return TEMP_EXPECTED_RISE * day / TEMP_RISE_DAYS


def expected_range(metric: MetricType, baseline_value: float, day: int) -> tuple[float, float]:
    """Lowest and highest normal value on this mission day, measurement margin included."""
    if metric in BLOOD_PRESSURE_METRICS:
        minimum = baseline_value - BP_EXPECTED_DROP - BP_MARGIN
        maximum = baseline_value + BP_MARGIN
    elif metric == MetricType.BODY_TEMPERATURE:
        minimum = baseline_value - TEMP_MARGIN
        maximum = baseline_value + expected_temperature_rise(day) + TEMP_MARGIN
    else:
        raise ValueError("Metric not evaluated by this algorithm: " + metric.value)
    return minimum, maximum


def range_deviation(value: float, minimum: float, maximum: float) -> float:
    """How far the value is outside the range: 0 inside, positive above, negative below."""
    if value > maximum:
        return value - maximum
    if value < minimum:
        return value - minimum
    return 0.0


def launch_time(mission_phases: list[MissionPhase]) -> datetime | None:
    """Start of the in-flight phase, used to count mission days. None when it is not known."""
    for phase in mission_phases:
        if phase.phase == MissionPhaseType.IN_FLIGHT:
            return phase.start_time
    return None


def mission_day(measured_at: datetime, launch: datetime) -> int:
    """Whole days since launch: day 0 is the launch day, negative before it."""
    return (measured_at - launch).days


def phase_at(moment: datetime, mission_phases: list[MissionPhase]) -> MissionPhaseType | None:
    for phase in mission_phases:
        if phase.start_time <= moment and (phase.end_time is None or moment < phase.end_time):
            return phase.phase
    return None


def find_baseline(
    baselines: list[PersonalBaseline],
    metric: MetricType,
    mission_phase: MissionPhaseType,
    evaluated_at: datetime,
) -> PersonalBaseline | None:
    """The usable baseline of this metric built from this mission phase, if any.
    A baseline computed after the evaluation time is not used (same rule as the sleep domain)."""
    for baseline in baselines:
        if baseline.metric != metric or baseline.mission_phase != mission_phase:
            continue
        if baseline.computed_at > evaluated_at:
            continue
        if baseline.status == BaselineStatus.INSUFFICIENT_DATA or baseline.statistics.mean is None:
            continue
        return baseline
    return None


def latest_measurement(
    measurements: list[PhysiologicalMeasurement], metric: MetricType
) -> PhysiologicalMeasurement | None:
    latest = None
    for measurement in measurements:
        if measurement.metric != metric:
            continue
        if latest is None or measurement.measured_at > latest.measured_at:
            latest = measurement
    return latest


def insufficient_finding(
    metric: MetricType,
    unit: str,
    explanation: str,
    measurement: PhysiologicalMeasurement | None = None,
) -> MetricFinding:
    observed_value = None
    data_quality = None
    if measurement is not None:
        observed_value = measurement.value
        data_quality = measurement.data_quality
    return MetricFinding(
        metric=metric,
        unit=unit,
        status=EvaluationStatus.INSUFFICIENT_DATA,
        observed_value=observed_value,
        explanation=explanation,
        data_quality=data_quality,
    )


def evaluate_metric(
    metric: MetricType,
    measurements: list[PhysiologicalMeasurement],
    baselines: list[PersonalBaseline],
    mission_phases: list[MissionPhase],
    evaluated_at: datetime,
) -> MetricFinding:
    """Finding for the most recent measurement of one metric."""
    unit = "mmHg"
    if metric == MetricType.BODY_TEMPERATURE:
        unit = "degC"

    measurement = latest_measurement(measurements, metric)
    if measurement is None:
        return insufficient_finding(metric, unit, "No measurement of this metric in the window.")
    if measurement.data_quality is not None and (
        measurement.data_quality.status == QualityStatus.UNUSABLE
    ):
        return insufficient_finding(
            metric,
            unit,
            "The measurement was marked as unusable by the quality check.",
            measurement,
        )
    pre_flight = find_baseline(baselines, metric, MissionPhaseType.PRE_FLIGHT, evaluated_at)
    if pre_flight is None:
        return insufficient_finding(
            metric, unit, "No usable pre-flight baseline for this metric.", measurement
        )
    launch = launch_time(mission_phases)
    if launch is None:
        return insufficient_finding(
            metric,
            unit,
            "The launch date is unknown, so the mission day cannot be computed.",
            measurement,
        )

    day = mission_day(measurement.measured_at, launch)
    baseline_value = pre_flight.statistics.mean
    minimum, maximum = expected_range(metric, baseline_value, day)
    distance = range_deviation(measurement.value, minimum, maximum)
    value_text = f"{measurement.value:g} {unit}"
    range_text = f"{minimum:.1f}-{maximum:.1f} {unit}"
    reference_text = f"pre-flight baseline {baseline_value:g} {unit}"
    if distance == 0:
        status = EvaluationStatus.NOMINAL
        position = "is within the range expected in flight"
    else:
        status = EvaluationStatus.ATTENTION
        side = "below"
        if distance > 0:
            side = "above"
        position = f"is {abs(distance):.1f} {unit} {side} the range expected in flight"
    explanation = (
        f"Mission day {day}: {value_text} {position} for this crew member "
        f"({range_text}, from the {reference_text})."
    )

    # Second check, when the baseline algorithm provides an in-flight baseline with its spread
    in_flight = find_baseline(baselines, metric, MissionPhaseType.IN_FLIGHT, evaluated_at)
    spread = None
    if in_flight is not None:
        spread = in_flight.statistics.standard_deviation
    if spread is not None and spread > 0:
        in_flight_mean = in_flight.statistics.mean
        if abs(measurement.value - in_flight_mean) > IN_FLIGHT_SD_LIMIT * spread:
            status = EvaluationStatus.ATTENTION
            explanation = (
                f"{explanation} It is also more than {IN_FLIGHT_SD_LIMIT} standard deviations "
                f"from the personal in-flight baseline ({in_flight_mean:.1f} {unit})."
            )

    absolute_deviation = measurement.value - baseline_value
    relative_deviation = None
    if baseline_value != 0:
        relative_deviation = round(absolute_deviation / baseline_value, 4)
    return MetricFinding(
        metric=metric,
        unit=unit,
        status=status,
        observed_value=measurement.value,
        baseline_id=pre_flight.baseline_id,
        baseline_value=baseline_value,
        absolute_deviation=round(absolute_deviation, 2),
        relative_deviation=relative_deviation,
        explanation=explanation,
        data_quality=measurement.data_quality,
    )


def overall_status(findings: list[MetricFinding]) -> EvaluationStatus:
    """Attention if any metric needs it, nominal if at least one was evaluated, else no data."""
    statuses = []
    for finding in findings:
        statuses.append(finding.status)
    if EvaluationStatus.ATTENTION in statuses:
        return EvaluationStatus.ATTENTION
    if EvaluationStatus.NOMINAL in statuses:
        return EvaluationStatus.NOMINAL
    return EvaluationStatus.INSUFFICIENT_DATA


def evaluate_vital_signs(
    crew_member_id: str,
    measurements: list[PhysiologicalMeasurement],
    baselines: list[PersonalBaseline],
    mission_phases: list[MissionPhase],
    evaluated_at: datetime,
    evaluation_id: str,
) -> EvaluationResult:
    """Evaluates blood pressure and body temperature of one crew member.

    Uses the most recent measurement of each metric in `measurements`; the evaluation window goes
    from the first to the last of them. Measurements taken after `evaluated_at`, and measurements
    and baselines of other crew members or other metrics, are ignored. The result supports
    decisions made by people: it is not a diagnosis.
    """
    own_measurements = []
    for measurement in measurements:
        if measurement.crew_member_id != crew_member_id:
            continue
        if measurement.metric in EVALUATED_METRICS and measurement.measured_at <= evaluated_at:
            own_measurements.append(measurement)
    own_baselines = []
    for baseline in baselines:
        if baseline.crew_member_id == crew_member_id:
            own_baselines.append(baseline)

    findings = []
    for metric in EVALUATED_METRICS:
        finding = evaluate_metric(
            metric, own_measurements, own_baselines, mission_phases, evaluated_at
        )
        findings.append(finding)
    status = overall_status(findings)

    if len(own_measurements) == 0:
        window_start = evaluated_at
        window_end = evaluated_at
    else:
        window_start = own_measurements[0].measured_at
        window_end = own_measurements[0].measured_at
        for measurement in own_measurements:
            window_start = min(window_start, measurement.measured_at)
            window_end = max(window_end, measurement.measured_at)

    attention = []
    for finding in findings:
        if finding.status == EvaluationStatus.ATTENTION:
            attention.append(finding.metric.value)
    if status == EvaluationStatus.ATTENTION:
        summary = "Outside the range expected in flight: " + ", ".join(attention) + "."
    elif status == EvaluationStatus.NOMINAL:
        summary = "Blood pressure and body temperature are within the range expected in flight."
    else:
        summary = "Not enough data or baselines to evaluate blood pressure and body temperature."

    return EvaluationResult(
        evaluation_id=evaluation_id,
        crew_member_id=crew_member_id,
        domain=HealthDomain.VITAL_SIGNS,
        mission_phase=phase_at(window_end, mission_phases),
        window_start=window_start,
        window_end=window_end,
        status=status,
        summary=summary,
        findings=findings,
        # Data quality is assessed by its own algorithm: here it is only passed through
        data_quality=DataQuality(status=QualityStatus.NOT_ASSESSED),
        algorithm=ALGORITHM,
        evaluated_at=evaluated_at,
    )
