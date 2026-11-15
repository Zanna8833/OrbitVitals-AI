"""Access to crew data. This is the only module to rewrite when the real data arrive:
just keep the same four public functions (crew_list, profile, series, long_term_summary).

Placeholder format:
- crew_data/profiles.json: {"A1": {"name", "role", "age", "sex", "notes", "preflight_baseline": {parameter: value}}}
- crew_data/measurements.csv: astronaut,mission_day,parameter,value,unit (one row per measurement)
"""

import csv
import json
import statistics
from pathlib import Path

DATA_FOLDER = Path(__file__).resolve().parents[2] / "crew_data"
WINDOW_DAYS = 7  # mean of the first and last 7 days to show the trend
PLATEAU_DAYS = 30  # the 30 days before the last week: the crew member's own in-flight reference
OUT_OF_RANGE_DEVIATIONS = 2  # latest value more than 2 standard deviations from the plateau → flagged to the model


def read_profiles(folder: Path = DATA_FOLDER) -> dict:
    with open(folder / "profiles.json", encoding="utf-8") as file:
        return json.load(file)


def read_measurements(folder: Path = DATA_FOLDER) -> list[dict]:
    measurements = []
    with open(folder / "measurements.csv", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            measurements.append({
                "astronaut": row["astronaut"],
                "day": int(row["mission_day"]),
                "parameter": row["parameter"],
                "value": float(row["value"]),
                "unit": row["unit"],
            })
    return measurements


def crew_list(folder: Path = DATA_FOLDER) -> list[str]:
    return list(read_profiles(folder).keys())


def profile(astronaut_id: str, folder: Path = DATA_FOLDER) -> dict:
    profiles = read_profiles(folder)
    if astronaut_id not in profiles:
        raise KeyError("Unknown astronaut: " + astronaut_id)
    return profiles[astronaut_id]


def series(astronaut_id: str, parameter: str, folder: Path = DATA_FOLDER) -> list[tuple[int, float]]:
    """The (day, value) measurements of one parameter, ordered by day."""
    points = []
    for measurement in read_measurements(folder):
        if measurement["astronaut"] == astronaut_id and measurement["parameter"] == parameter:
            points.append((measurement["day"], measurement["value"]))
    points.sort()
    return points


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


def long_term_summary(astronaut_id: str, folder: Path = DATA_FOLDER) -> str:
    """Compact text (goes to the model) with the trend of every parameter against the pre-flight baseline.
    No clinical judgement here: the model compares with the expected in-flight values using the documents."""
    profile_data = profile(astronaut_id, folder)
    baseline = profile_data.get("preflight_baseline", {})

    # Parameters in the order they appear, with their unit
    parameters = []
    units = {}
    current_day = 0
    for measurement in read_measurements(folder):
        if measurement["astronaut"] != astronaut_id:
            continue
        if measurement["parameter"] not in units:
            parameters.append(measurement["parameter"])
            units[measurement["parameter"]] = measurement["unit"]
        current_day = max(current_day, measurement["day"])

    lines = []
    lines.append("Crew member " + astronaut_id + ": " + profile_data.get("name", "") + ", "
                 + profile_data.get("role", "") + ", age " + str(profile_data.get("age", "?")) + ", sex "
                 + profile_data.get("sex", "?") + ". Current mission day: " + str(current_day) + ".")
    if profile_data.get("notes", "") != "":
        lines.append("Medical notes: " + profile_data["notes"])
    parameter_lines = []
    alerts = []
    for parameter in parameters:
        points = series(astronaut_id, parameter, folder)
        values = []
        for _day, value in points:
            values.append(value)
        first = values[:WINDOW_DAYS]
        last = values[-WINDOW_DAYS:]
        # The personal in-flight reference (guidance says to compare with this, not with terrestrial ranges)
        plateau = values[-(PLATEAU_DAYS + WINDOW_DAYS):-WINDOW_DAYS]
        plateau_text = "n/a"
        deviation_text = ""
        if len(plateau) > 0:
            plateau_text = format(mean(plateau), ".1f")
        # The 4B model does not compare dozens of numbers well; the code says what moved away from the personal
        # plateau. This is statistics on the person's own data, not a diagnosis.
        if len(plateau) >= 2:
            deviation = values[-1] - mean(plateau)
            deviation_text = "; latest vs plateau " + format(deviation, "+.2g")
            standard_deviation = statistics.stdev(plateau)
            if standard_deviation > 0 and abs(deviation) > OUT_OF_RANGE_DEVIATIONS * standard_deviation:
                deviation_text = deviation_text + " -> OUTSIDE personal in-flight range"
                alerts.append(parameter + " latest " + format(values[-1], "g") + " " + units[parameter]
                              + " (day " + str(points[-1][0]) + ") vs in-flight plateau " + plateau_text)
        min_index = values.index(min(values))
        max_index = values.index(max(values))
        last_day, last_value = points[-1]

        baseline_text = "n/a"
        change_text = "n/a"
        if parameter in baseline:
            baseline_value = float(baseline[parameter])
            baseline_text = format(baseline_value, "g")
            if baseline_value != 0:
                percentage = (mean(last) - baseline_value) / abs(baseline_value) * 100
                change_text = format(percentage, "+.1f") + "%"

        # Every value with its label: with a column table the 4B model swapped the columns
        line = ("- " + parameter + " [" + units[parameter] + "]: pre-flight baseline " + baseline_text
                + "; first " + str(WINDOW_DAYS) + " flight days " + format(mean(first), ".1f")
                + "; in-flight plateau " + plateau_text
                + "; last " + str(WINDOW_DAYS) + " days " + format(mean(last), ".1f")
                + "; latest " + format(last_value, "g") + " (day " + str(last_day) + ")"
                + "; min " + format(min(values), "g") + " (day " + str(points[min_index][0]) + ")"
                + "; max " + format(max(values), "g") + " (day " + str(points[max_index][0]) + ")"
                + "; last " + str(WINDOW_DAYS) + " days vs baseline " + change_text
                + deviation_text)
        parameter_lines.append(line)

    # Deviations from the plateau at the top, in a block of their own: inside long lines the 4B model ignored them
    if len(alerts) == 0:
        lines.append("ALERTS: none (every latest value is within the crew member's own in-flight range).")
    else:
        lines.append("ALERTS (latest value outside the crew member's own in-flight range):")
        for alert in alerts:
            lines.append("! " + alert)
    lines.append("In-flight plateau = mean of the " + str(PLATEAU_DAYS) + " days before the last "
                 + str(WINDOW_DAYS) + " days (the crew member's own in-flight reference).")
    for line in parameter_lines:
        lines.append(line)
    return "\n".join(lines)
