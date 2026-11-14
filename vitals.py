"""Checks whether an astronaut's blood pressure and body temperature are normal for spaceflight.

There is no official NASA table of normal in-flight vital signs: each reading is compared with the same
astronaut's pre-flight baseline, shifted by the changes published for long-duration ISS flight.
"""

# Blood pressure: equal to or up to about 10 mmHg below the pre-flight baseline is expected in flight
# (Norsk et al. 2015, J Physiol: 24-h BP -8/-9 mmHg; Hughson et al. 2012, J Appl Physiol: no change at rest).
BP_EXPECTED_DROP = 10  # mmHg
# Measurement error: BP monitors are validated for a mean error up to 5 mmHg (ISO 81060-2, Stergiou et al. 2018).
BP_MARGIN = 5  # mmHg

# Resting core temperature rises by about 1 degC, gradually, with a plateau after about 75 days
# (Stahn et al. 2017, Sci Rep). The curve is published only as a figure: the linear rise is our assumption.
TEMP_EXPECTED_RISE = 1.0  # degC
TEMP_RISE_DAYS = 75
# Day-to-day variability of body temperature in healthy adults: 0.32 degC (PMC7857558).
TEMP_MARGIN = 0.3  # degC

BLOOD_PRESSURE_PARAMETERS = ["systolic_bp", "diastolic_bp"]
TEMPERATURE_PARAMETER = "core_temperature"


def expected_temperature_rise(day: int) -> float:
    """Expected rise of resting core temperature on a given mission day."""
    if day >= TEMP_RISE_DAYS:
        return TEMP_EXPECTED_RISE
    return TEMP_EXPECTED_RISE * day / TEMP_RISE_DAYS


def expected_range(parameter: str, baseline_value: float, day: int) -> tuple[float, float]:
    """Lowest and highest normal value on this mission day, measurement margin included."""
    if parameter in BLOOD_PRESSURE_PARAMETERS:
        minimum = baseline_value - BP_EXPECTED_DROP - BP_MARGIN
        maximum = baseline_value + BP_MARGIN
    elif parameter == TEMPERATURE_PARAMETER:
        minimum = baseline_value - TEMP_MARGIN
        maximum = baseline_value + expected_temperature_rise(day) + TEMP_MARGIN
    else:
        raise ValueError("Unknown parameter: " + parameter)
    return minimum, maximum


def range_deviation(value: float, minimum: float, maximum: float) -> float:
    """How far the value is outside the range: 0 inside, positive above, negative below."""
    if value > maximum:
        return value - maximum
    if value < minimum:
        return value - minimum
    return 0.0


def check_parameter(parameter: str, value: float, day: int, baseline_value: float) -> dict:
    """Result for one reading, ready to be stored in the registry and saved as JSON."""
    minimum, maximum = expected_range(parameter, baseline_value, day)
    deviation = range_deviation(value, minimum, maximum)
    return {
        "value": value,
        "expected_min": round(minimum, 2),
        "expected_max": round(maximum, 2),
        "deviation": round(deviation, 2),
        "ok": deviation == 0,
    }
