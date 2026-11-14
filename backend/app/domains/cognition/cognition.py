"""Scores the cognitive test battery (emulation of NASA's 'Cognition' battery, Basner et al. 2015)
and builds the report for the ground researcher. The astronaut never sees these numbers: the test
screens only say that a test is complete.

Input: one session file written by the test frontend (raw trials for each test).
Output: registry[astronaut_id][mission_day] = session report, saved as JSON (same functions as
vitals.py).
Usage, from backend/:
    python -m app.domains.cognition.cognition session.json [...] --registry cognition_registry.json
"""

import json
import os
import statistics
import sys

from app.domains.vitals import vitals

# Pre-flight scores of 25 NASA astronauts before 6-month ISS missions: (mean, standard deviation).
# Dev et al. 2024, Front Physiol 15:1451269, Table 1. Speed = mean response time in ms (lower is
# faster); for the PVT speed = 10 - 1/RT with RT in seconds (lower is faster). BART accuracy = risk
# score.
# Motor Praxis has no accuracy norm in that table.
NORMS = {
    "MPT": {"speed": (1061.18, 153.53)},
    "VOLT": {"speed": (1627.96, 617.83), "accuracy": (0.95, 0.06)},
    "F2B": {"speed": (552.94, 60.95), "accuracy": (0.92, 0.07)},
    "AM": {"speed": (2353.32, 877.69), "accuracy": (0.81, 0.11)},
    "LOT": {"speed": (4691.30, 1183.95), "accuracy": (0.78, 0.08)},
    "ERT": {"speed": (2645.30, 886.40), "accuracy": (0.72, 0.11)},
    "MRT": {"speed": (8546.15, 2340.55), "accuracy": (0.79, 0.14)},
    "DSST": {"speed": (1209.38, 145.95), "accuracy": (0.98, 0.02)},
    "BART": {"speed": (637.83, 429.65), "risk": (0.72, 0.11)},
    "PVT": {"speed": (5.25, 0.24), "accuracy": (0.97, 0.04)},
}

TEST_NAMES = {
    "MPT": "Motor Praxis",
    "VOLT": "Visual Object Learning",
    "F2B": "Fractal 2-Back",
    "AM": "Abstract Matching",
    "LOT": "Line Orientation",
    "ERT": "Emotion Recognition",
    "MRT": "Matrix Reasoning",
    "DSST": "Digit Symbol Substitution",
    "BART": "Balloon Analog Risk",
    "PVT": "Psychomotor Vigilance",
}

# Dev et al. 2024 count a score as low when z <= -1.5 (a cut-off used to detect impairment in
# clinical groups).
LOW_SCORE_Z = -1.5

# Scoring rules from Basner et al. 2021, Front Physiol 12:643854 (Methods, Cognition outcome
# variables). Motor Praxis: clicking the centre is 100%, 50 px or more away is 0%, linear
# in between.
MPT_ZERO_ACCURACY_PX = 50
LOT_MAX_CLICKS_OFF = 3  # accuracy = (3 - mean clicks off) / 3, and 0 above 3 clicks
PVT_FALSE_START_MS = 100
PVT_LAPSE_MS = 355  # lapse threshold of the 3-minute PVT (500 ms is for the 10-minute version)

# Not applied: the published corrections for practice and stimulus set (Basner et al. 2020) were not
# verified on the full text, so early sessions may look slightly worse than later ones.


def mean_response_time(trials: list[dict]) -> float | None:
    times = []
    for trial in trials:
        if trial.get("rt_ms") is not None:
            times.append(trial["rt_ms"])
    if len(times) == 0:
        return None
    return statistics.mean(times)


def score_motor_praxis(test: dict) -> dict:
    accuracies = []
    for trial in test["trials"]:
        accuracy = 1 - trial["distance_px"] / MPT_ZERO_ACCURACY_PX
        if accuracy < 0:
            accuracy = 0
        accuracies.append(accuracy)
    return {"speed": mean_response_time(test["trials"]), "accuracy": statistics.mean(accuracies)}


def score_correct_or_wrong(test: dict) -> dict:
    """VOLT, AM, ERT, MRT, DSST: accuracy = share of correct answers.
    Items not reached count as wrong."""
    correct = 0
    for trial in test["trials"]:
        if trial["correct"]:
            correct = correct + 1
    return {"speed": mean_response_time(test["trials"]), "accuracy": correct / len(test["trials"])}


def score_fractal_two_back(test: dict) -> dict:
    # Accuracy = mean of the % correct on matches and on non-matches, so never pressing does not
    # score well
    matches = 0
    hits = 0
    non_matches = 0
    correct_rejections = 0
    responded = []
    for trial in test["trials"]:
        if trial["is_match"]:
            matches = matches + 1
            if trial["responded"]:
                hits = hits + 1
        else:
            non_matches = non_matches + 1
            if not trial["responded"]:
                correct_rejections = correct_rejections + 1
        if trial["responded"]:
            responded.append(trial)
    accuracy = (hits / matches + correct_rejections / non_matches) / 2
    return {"speed": mean_response_time(responded), "accuracy": accuracy}


def score_line_orientation(test: dict) -> dict:
    clicks_off = []
    for trial in test["trials"]:
        clicks_off.append(trial["clicks_off"])
    accuracy = (LOT_MAX_CLICKS_OFF - statistics.mean(clicks_off)) / LOT_MAX_CLICKS_OFF
    if accuracy < 0:
        accuracy = 0
    return {"speed": mean_response_time(test["trials"]), "accuracy": accuracy}


def score_balloon(test: dict) -> dict:
    # Each pump adds 1 / (pumps possible over all balloons) to the risk score
    pumps = 0
    possible_pumps = 0
    pump_times = []
    for balloon in test["balloons"]:
        pumps = pumps + balloon["pumps"]
        possible_pumps = possible_pumps + balloon["pop_point"]
        for pump_time in balloon["pump_rts_ms"]:
            pump_times.append(pump_time)
    speed = None
    if len(pump_times) > 0:
        speed = statistics.mean(pump_times)
    return {"speed": speed, "risk": pumps / possible_pumps}


def score_vigilance(test: dict) -> dict:
    # Accuracy = 1 - (lapses + false starts) / (stimuli + false starts);
    # speed = 10 - mean(1/RT in seconds)
    false_starts = test["false_starts"]  # presses with no stimulus on screen
    lapses = 0
    reciprocals = []
    for stimulus in test["stimuli"]:
        reaction_time = stimulus["rt_ms"]
        if reaction_time is None or reaction_time >= PVT_LAPSE_MS:
            lapses = lapses + 1
        if reaction_time is not None and reaction_time < PVT_FALSE_START_MS:
            false_starts = false_starts + 1
        elif reaction_time is not None:
            reciprocals.append(1000 / reaction_time)
    accuracy = 1 - (lapses + false_starts) / (len(test["stimuli"]) + test["false_starts"])
    speed = None
    if len(reciprocals) > 0:
        speed = 10 - statistics.mean(reciprocals)
    return {"speed": speed, "accuracy": accuracy, "lapses": lapses, "false_starts": false_starts}


def score_test(code: str, test: dict) -> dict:
    if code == "MPT":
        return score_motor_praxis(test)
    if code in ["VOLT", "AM", "ERT", "MRT", "DSST"]:
        return score_correct_or_wrong(test)
    if code == "F2B":
        return score_fractal_two_back(test)
    if code == "LOT":
        return score_line_orientation(test)
    if code == "BART":
        return score_balloon(test)
    if code == "PVT":
        return score_vigilance(test)
    raise ValueError("Unknown test: " + code)


def z_score(code: str, metric: str, value: float) -> float:
    """z against the astronaut norms. Speed is flipped so that a higher z always means faster."""
    mean, standard_deviation = NORMS[code][metric]
    z = (value - mean) / standard_deviation
    if metric == "speed":
        z = -z
    return z


def preflight_summaries(registry: dict, astronaut_id: str) -> list[dict]:
    """Summaries of the astronaut's sessions before launch (negative mission days, L-90 = -90)."""
    summaries = []
    if astronaut_id not in registry:
        return summaries
    for day in sorted(registry[astronaut_id]):
        if day < 0:
            summaries.append(registry[astronaut_id][day]["summary"])
    return summaries


def score_session(registry: dict, session: dict) -> dict:
    tests = {}
    speed_z = []
    accuracy_z = []
    low_scores = []
    for code in session["tests"]:
        metrics = score_test(code, session["tests"][code])
        z_values = {}
        for metric in NORMS[code]:
            if metrics.get(metric) is None:
                continue
            z = z_score(code, metric, metrics[metric])
            z_values[metric] = round(z, 2)
            if z <= LOW_SCORE_Z:
                low_scores.append(code + " " + metric)
            if metric == "speed":
                speed_z.append(z)
            # BART risk is not an accuracy: it stays out of the accuracy summary (Basner 2021)
            if metric == "accuracy":
                accuracy_z.append(z)
        rounded_metrics = {}
        for metric in metrics:
            rounded_metrics[metric] = metrics[metric]
            if isinstance(metrics[metric], float):
                rounded_metrics[metric] = round(metrics[metric], 3)
        tests[code] = {"name": TEST_NAMES[code], "metrics": rounded_metrics, "z": z_values}

    # Summaries as in Basner et al. 2021: mean z of speed, mean z of accuracy, efficiency = their
    # mean
    summary = {"speed": None, "accuracy": None, "efficiency": None}
    if len(speed_z) > 0:
        summary["speed"] = round(statistics.mean(speed_z), 2)
    if len(accuracy_z) > 0:
        summary["accuracy"] = round(statistics.mean(accuracy_z), 2)
    if summary["speed"] is not None and summary["accuracy"] is not None:
        summary["efficiency"] = round((summary["speed"] + summary["accuracy"]) / 2, 2)

    # Change from the astronaut's own pre-flight sessions, when there are any
    change_from_preflight = None
    previous = preflight_summaries(registry, session["astronaut_id"])
    if session["mission_day"] >= 0 and len(previous) > 0:
        change_from_preflight = {}
        for key in summary:
            values = []
            for old_summary in previous:
                if old_summary[key] is not None:
                    values.append(old_summary[key])
            if summary[key] is None or len(values) == 0:
                change_from_preflight[key] = None
            else:
                change_from_preflight[key] = round(summary[key] - statistics.mean(values), 2)

    return {
        "astronaut_id": session["astronaut_id"],
        "mission_day": session["mission_day"],
        "started_at": session.get("started_at"),
        "survey": session.get("survey", {}),
        "tests": tests,
        "summary": summary,
        "change_from_preflight": change_from_preflight,
        "low_scores": low_scores,
    }


def record_session(registry: dict, session: dict) -> dict:
    report = score_session(registry, session)
    astronaut_id = session["astronaut_id"]
    if astronaut_id not in registry:
        registry[astronaut_id] = {}
    registry[astronaut_id][session["mission_day"]] = report
    return report


def text_report(report: dict) -> str:
    """Short text version of a session report for the ground researcher."""
    lines = []
    lines.append(
        "Astronaut " + report["astronaut_id"] + ", mission day " + str(report["mission_day"])
    )
    for code in report["tests"]:
        test = report["tests"][code]
        parts = []
        for metric in test["z"]:
            parts.append(metric + " z " + format(test["z"][metric], "+.2f"))
        lines.append("  " + test["name"] + ": " + ", ".join(parts))
    summary = report["summary"]
    lines.append(
        "  Summary: speed "
        + str(summary["speed"])
        + ", accuracy "
        + str(summary["accuracy"])
        + ", efficiency "
        + str(summary["efficiency"])
    )
    if report["change_from_preflight"] is not None:
        lines.append("  Change from own pre-flight: " + str(report["change_from_preflight"]))
    if len(report["low_scores"]) == 0:
        lines.append("  Low scores (z <= -1.5): none")
    else:
        lines.append("  Low scores (z <= -1.5): " + ", ".join(report["low_scores"]))
    return "\n".join(lines)


def main():
    arguments = sys.argv[1:]
    if "--registry" not in arguments or len(arguments) < 3:
        print(
            "Usage: python -m app.domains.cognition.cognition session.json [...]"
            " --registry cognition_registry.json"
        )
        sys.exit(1)
    position = arguments.index("--registry")
    registry_path = arguments[position + 1]
    session_paths = arguments[:position] + arguments[position + 2 :]

    registry = {}
    if os.path.exists(registry_path):
        registry = vitals.load_registry(registry_path)
    # Sessions in mission-day order, so that pre-flight sessions are there before the in-flight ones
    sessions = []
    for path in session_paths:
        with open(path, encoding="utf-8") as file:
            sessions.append(json.load(file))
    sessions.sort(key=session_day)
    for session in sessions:
        report = record_session(registry, session)
        print(text_report(report))
    vitals.save_registry(registry, registry_path)


def session_day(session: dict) -> int:
    return session["mission_day"]


if __name__ == "__main__":
    main()
