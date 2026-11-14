"""Checks whether an astronaut's blood pressure and body temperature are normal for spaceflight.

There is no official NASA table of normal in-flight vital signs: each reading is compared with the same
astronaut's pre-flight baseline, shifted by the changes published for long-duration ISS flight.
"""

import json
import statistics

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

# Personal in-flight reference: mean of the 30 days before the last week, so that a drift of the last
# few days does not hide inside the reference.
PLATEAU_DAYS = 30
RECENT_DAYS = 7
# With one reading per day, 2 standard deviations gave a false alarm about every 20 days for healthy crew.
PLATEAU_SD_LIMIT = 3

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


def plateau_values(registry: dict, astronaut_id: str, parameter: str, day: int) -> list[float]:
    """Values of the parameter on days day-37 ... day-8 already stored in the registry."""
    values = []
    if astronaut_id not in registry:
        return values
    days = registry[astronaut_id]
    first_day = day - RECENT_DAYS - PLATEAU_DAYS
    for past_day in range(first_day, day - RECENT_DAYS):
        if past_day in days and parameter in days[past_day]:
            values.append(days[past_day][parameter]["value"])
    return values


def check_parameter(registry: dict, astronaut_id: str, parameter: str, value: float, day: int,
                    baseline_value: float) -> dict:
    """Result for one reading, ready to be stored in the registry and saved as JSON."""
    minimum, maximum = expected_range(parameter, baseline_value, day)
    deviation = range_deviation(value, minimum, maximum)
    ok = deviation == 0

    # Second check, only when there is enough history: distance from the personal in-flight reference
    plateau = plateau_values(registry, astronaut_id, parameter, day)
    plateau_mean = None
    if len(plateau) >= 2:
        plateau_mean = statistics.mean(plateau)
        standard_deviation = statistics.stdev(plateau)
        if standard_deviation > 0 and abs(value - plateau_mean) > PLATEAU_SD_LIMIT * standard_deviation:
            ok = False
        plateau_mean = round(plateau_mean, 2)

    return {
        "value": value,
        "expected_min": round(minimum, 2),
        "expected_max": round(maximum, 2),
        "deviation": round(deviation, 2),
        "plateau_mean": plateau_mean,
        "ok": ok,
    }


def record_day(registry: dict, astronaut_id: str, day: int, systolic: float, diastolic: float,
               temperature: float, baseline: dict) -> dict:
    """Checks one day of readings and stores it in registry[astronaut_id][day].
    baseline = pre-flight values with the keys systolic_bp, diastolic_bp, core_temperature."""
    systolic_result = check_parameter(registry, astronaut_id, "systolic_bp", systolic, day,
                                      baseline["systolic_bp"])
    diastolic_result = check_parameter(registry, astronaut_id, "diastolic_bp", diastolic, day,
                                       baseline["diastolic_bp"])
    temperature_result = check_parameter(registry, astronaut_id, TEMPERATURE_PARAMETER, temperature, day,
                                         baseline[TEMPERATURE_PARAMETER])
    day_record = {
        "systolic_bp": systolic_result,
        "diastolic_bp": diastolic_result,
        "core_temperature": temperature_result,
        "blood_pressure_ok": systolic_result["ok"] and diastolic_result["ok"],
        "temperature_ok": temperature_result["ok"],
    }
    if astronaut_id not in registry:
        registry[astronaut_id] = {}
    registry[astronaut_id][day] = day_record
    return day_record


def save_registry(registry: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(registry, file, indent=2)


def load_registry(path: str) -> dict:
    with open(path, encoding="utf-8") as file:
        loaded = json.load(file)
    # JSON keys are always strings: mission days go back to int
    registry = {}
    for astronaut_id in loaded:
        registry[astronaut_id] = {}
        for day in loaded[astronaut_id]:
            registry[astronaut_id][int(day)] = loaded[astronaut_id][day]
    return registry
