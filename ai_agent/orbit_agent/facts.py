"""Deterministic fact sheet built from backend responses.

Every value the agent may talk about is first written here as a `Fact`: a sentence in a
fixed wording, the structured values behind it and the backend path it came from. No
model is involved, no statistic is recomputed and nothing is estimated. The language
model later receives these facts and may only refer to them by identifier.

Some values, such as the Theil-Sen slope of a sleep trend, exist only inside the
free-text `explanation` of a finding. They are extracted with tolerant patterns; when a
pattern does not match, the value is simply absent and the original text is passed on.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from orbit_agent.models import Fact, FactSource, InterpretationRole

_SCREENING_STATUSES = {"nominal", "attention", "alert"}
_PROBLEM_QUALITY = {"degraded", "unusable"}
_MAX_SERIES_POINTS = 20
_MAX_ISSUE_FACTS = 12
_EXCERPT_CHARS = 500


@dataclass(frozen=True)
class BackendSnapshot:
    """Everything read from the backend for one crew member, as returned."""

    crew_member_id: str
    metric_catalog: list[dict[str, Any]]
    evaluations: list[dict[str, Any]]
    baselines: list[dict[str, Any]]
    measurements: list[dict[str, Any]]


@dataclass
class FactSheet:
    crew_member_id: str
    domains: list[str]
    facts: list[Fact] = field(default_factory=list)

    def by_id(self) -> dict[str, Fact]:
        return {fact.id: fact for fact in self.facts}

    def of_kind(self, *kinds: str) -> list[Fact]:
        return [fact for fact in self.facts if fact.kind in kinds]

    def add(self, **fields: Any) -> Fact:
        fact = Fact(id=f"F{len(self.facts) + 1}", **fields)
        self.facts.append(fact)
        return fact


def format_number(value: float | int | None) -> str:
    """Render a value without inventing precision: at most three decimals."""
    if value is None:
        return "not available"
    rounded = round(float(value), 3)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.3f}".rstrip("0").rstrip(".")


def _percent(fraction: float | None) -> str | None:
    return None if fraction is None else f"{format_number(round(fraction * 100, 1))}%"


def _excerpt(text: str | None, stop_markers: tuple[str, ...] = ()) -> str | None:
    if not text:
        return None
    for marker in stop_markers:
        position = text.find(marker)
        if position != -1:
            text = text[:position]
    text = text.strip()
    return text if len(text) <= _EXCERPT_CHARS else text[:_EXCERPT_CHARS].rstrip() + " [...]"


_NUMBER = r"[+-]?\d+(?:\.\d+)?"
_PATTERNS: dict[str, re.Pattern[str]] = {
    "included_nights": re.compile(r"Included (\d+)/(\d+) complete night buckets"),
    "coverage": re.compile(rf"coverage=({_NUMBER})"),
    "missing_nights": re.compile(r"missing nights=([^;]+);"),
    "longest_missing_run": re.compile(r"longest missing run=(\d+)"),
    "elapsed_span_days": re.compile(r"elapsed span=(\d+) days"),
    "slope": re.compile(rf"Theil-Sen slope=({_NUMBER}) ([^;]+?)/day"),
    "fitted_change": re.compile(rf"fitted change=({_NUMBER})"),
    "decreasing_fraction": re.compile(rf"decreasing transition fraction=({_NUMBER})"),
    "detected_pattern": re.compile(r"Configured statistical pattern detected: ([a-z_]+)"),
    "insufficiency_reasons": re.compile(r"Insufficient trend data: ([a-z_, ]+)\."),
    "aggregation": re.compile(r"Observed value is (the [^.;]+)[.;]"),
    "missed_targets": re.compile(r"Personal daily minimum target missed on: (.+?)\. Configured"),
    "daily_target": re.compile(rf"Configured daily target: ({_NUMBER})"),
    "weekly_target": re.compile(rf"weekly target: ({_NUMBER})"),
    "reduction_run": re.compile(
        r"Progressive reduction from (\d{4}-\d{2}-\d{2}) through (\d{4}-\d{2}-\d{2}): (\d+) "
        rf"consecutive comparable daily totals strictly decreased from ({_NUMBER}) to ({_NUMBER})"
    ),
}


def parse_explanation(text: str) -> dict[str, Any]:
    """Extract labelled values from an algorithm explanation. Missing labels are omitted."""
    details: dict[str, Any] = {}

    def first(name: str) -> re.Match[str] | None:
        return _PATTERNS[name].search(text)

    if match := first("included_nights"):
        details["included_nights"] = int(match.group(1))
        details["expected_nights"] = int(match.group(2))
    if match := first("coverage"):
        details["coverage"] = float(match.group(1))
    if match := first("missing_nights"):
        raw = match.group(1).strip()
        details["missing_nights"] = (
            [] if raw == "none" else [item.strip() for item in raw.split(",") if item.strip()]
        )
    if match := first("longest_missing_run"):
        details["longest_missing_run"] = int(match.group(1))
    if match := first("elapsed_span_days"):
        details["elapsed_span_days"] = int(match.group(1))
    if match := first("slope"):
        details["trend_slope_per_day"] = float(match.group(1))
        details["trend_slope_unit"] = f"{match.group(2).strip()}/day"
    if match := first("fitted_change"):
        details["trend_fitted_change"] = float(match.group(1))
    if match := first("decreasing_fraction"):
        details["decreasing_transition_fraction"] = float(match.group(1))
    if match := first("detected_pattern"):
        details["detected_pattern"] = match.group(1)
    elif "No configured trend pattern detected" in text:
        details["detected_pattern"] = None
    if match := first("insufficiency_reasons"):
        details["insufficiency_reasons"] = [
            item.strip() for item in match.group(1).split(",") if item.strip()
        ]
    if "A full activity assessment is unavailable" in text:
        details["insufficiency_reasons"] = ["usable_coverage_or_comparison_criteria_missing"]
    if match := first("aggregation"):
        details["aggregation"] = match.group(1).strip()
    if match := first("missed_targets"):
        details["missed_daily_targets"] = [
            item.strip() for item in re.split(r",\s*(?=\d{4}-\d{2}-\d{2})", match.group(1))
        ]
    if match := first("daily_target"):
        details["configured_daily_target"] = float(match.group(1))
    if match := first("weekly_target"):
        details["configured_weekly_target"] = float(match.group(1))
    if match := first("reduction_run"):
        details["progressive_reduction"] = {
            "from_date": match.group(1),
            "through_date": match.group(2),
            "consecutive_days": int(match.group(3)),
            "from_value": float(match.group(4)),
            "to_value": float(match.group(5)),
        }
    return details


def _quality_view(quality: dict[str, Any] | None) -> dict[str, Any] | None:
    if not quality:
        return None
    return {
        "status": quality.get("status"),
        "score": quality.get("score"),
        "completeness": quality.get("completeness"),
        "flags": list(quality.get("flags") or []),
        "notes": _excerpt(quality.get("notes")),
    }


def _quality_phrase(quality: dict[str, Any] | None) -> str:
    if not quality:
        return "data quality not reported"
    flags = quality.get("flags") or []
    phrase = f"data quality '{quality.get('status')}'"
    return phrase + (f" (flags: {', '.join(flags)})" if flags else "")


def _role_for_status(status: str | None) -> InterpretationRole:
    return "screening_signal" if status in _SCREENING_STATUSES else "no_physiological_basis"


def _finding_statement(
    finding: dict[str, Any], evaluation: dict[str, Any], details: dict[str, Any]
) -> str:
    unit = finding["unit"]
    # A difference between two percentages is expressed in percentage points.
    difference_unit = "percentage points" if unit == "%" else unit
    parts = [
        f"{finding['metric']} finding of the {evaluation['domain']} evaluation for the window "
        f"{evaluation['window_start']} to {evaluation['window_end']}: status "
        f"'{finding['status']}'."
    ]
    if finding.get("observed_value") is None:
        parts.append("No observed value could be computed.")
    else:
        aggregation = f" ({details['aggregation']})" if details.get("aggregation") else ""
        parts.append(
            f"Observed value {format_number(finding['observed_value'])} {unit}{aggregation}."
        )
    if finding.get("baseline_value") is not None:
        parts.append(f"Personal baseline value {format_number(finding['baseline_value'])} {unit}.")
    if finding.get("absolute_deviation") is not None:
        relative = _percent(finding.get("relative_deviation"))
        parts.append(
            f"Deviation from baseline {format_number(finding['absolute_deviation'])} "
            f"{difference_unit}" + (f" ({relative} relative to baseline)." if relative else ".")
        )
    if "included_nights" in details:
        coverage = (
            f" (coverage {format_number(details['coverage'])})" if "coverage" in details else ""
        )
        parts.append(
            f"Included {details['included_nights']} of {details['expected_nights']} night "
            f"buckets{coverage}."
        )
    if details.get("missing_nights"):
        parts.append(f"Missing nights: {', '.join(details['missing_nights'])}.")
    if "longest_missing_run" in details and details["longest_missing_run"] > 1:
        parts.append(f"Longest run of missing nights: {details['longest_missing_run']}.")
    if "trend_slope_per_day" in details:
        parts.append(
            f"Theil-Sen slope {format_number(details['trend_slope_per_day'])} "
            f"{details['trend_slope_unit']}."
        )
    if "trend_fitted_change" in details:
        parts.append(
            f"Fitted change over the window {format_number(details['trend_fitted_change'])} "
            f"{difference_unit}."
        )
    if details.get("detected_pattern"):
        parts.append(f"Configured pattern detected: {details['detected_pattern']}.")
    elif "detected_pattern" in details:
        parts.append("No configured trend pattern detected.")
    if details.get("insufficiency_reasons"):
        parts.append(
            f"Reasons the screen was not applied: {', '.join(details['insufficiency_reasons'])}."
        )
    if details.get("missed_daily_targets"):
        parts.append(
            f"Personal daily target missed on: {'; '.join(details['missed_daily_targets'])}."
        )
    if reduction := details.get("progressive_reduction"):
        parts.append(
            f"Progressive reduction from {reduction['from_date']} through "
            f"{reduction['through_date']}: {reduction['consecutive_days']} consecutive daily "
            f"totals decreased from {format_number(reduction['from_value'])} to "
            f"{format_number(reduction['to_value'])} {unit}."
        )
    parts.append(f"Records behind this finding: {_quality_phrase(finding.get('data_quality'))}.")
    return " ".join(parts)


def _measurement_window(evaluations: list[dict[str, Any]]) -> tuple[str, str] | None:
    if not evaluations:
        return None
    return (
        min(evaluation["window_start"] for evaluation in evaluations),
        max(evaluation["window_end"] for evaluation in evaluations),
    )


def build_fact_sheet(snapshot: BackendSnapshot, domain: str | None = None) -> FactSheet:
    """Turn backend responses into an ordered, numbered list of facts."""
    crew = snapshot.crew_member_id
    crew_path = f"/crew-members/{crew}"
    metric_domain = {entry["metric"]: entry["domain"] for entry in snapshot.metric_catalog}

    def in_scope(metric: str) -> bool:
        return domain is None or metric_domain.get(metric) == domain

    evaluations = sorted(
        (item for item in snapshot.evaluations if domain is None or item["domain"] == domain),
        key=lambda item: (item["window_end"], item["domain"], item["evaluation_id"]),
    )
    measurements = [item for item in snapshot.measurements if in_scope(item["metric"])]
    domains = [domain] if domain else sorted({evaluation["domain"] for evaluation in evaluations})
    sheet = FactSheet(crew_member_id=crew, domains=domains)

    sources = Counter(item["source"] for item in measurements)
    if not measurements:
        provenance = "No stored measurements were returned for this crew member in this scope."
    elif set(sources) == {"simulated"}:
        provenance = (
            f"All {len(measurements)} stored measurements in scope have source 'simulated': "
            "they are synthetic demonstration data, not recordings of a person."
        )
    else:
        listed = ", ".join(f"{name}: {count}" for name, count in sorted(sources.items()))
        provenance = f"The {len(measurements)} stored measurements in scope have sources {listed}."
    sheet.add(
        kind="provenance",
        statement=provenance,
        data={"measurement_count": len(measurements), "sources": dict(sorted(sources.items()))},
        source=FactSource(path=f"{crew_path}/measurements"),
        interpretation_role="data_quality",
    )

    if not evaluations:
        sheet.add(
            kind="evaluation",
            domain=domain,
            statement=(
                "The backend holds no stored evaluation for this crew member in this scope, "
                "so no physiological status is available."
            ),
            data={"evaluation_count": 0},
            source=FactSource(path=f"{crew_path}/evaluations"),
            interpretation_role="no_physiological_basis",
        )

    referenced_baselines: list[str] = []
    finding_metrics: list[str] = []
    latest_finding: dict[str, tuple[str, dict[str, Any]]] = {}
    for index, evaluation in enumerate(evaluations, start=1):
        quality = evaluation.get("data_quality")
        algorithm = evaluation.get("algorithm") or {}
        per_metric = []
        for finding in evaluation.get("findings", []):
            reasons = parse_explanation(finding.get("explanation") or "").get(
                "insufficiency_reasons"
            )
            per_metric.append(
                f"{finding['metric']} '{finding['status']}'"
                + (f" (reported reasons: {', '.join(reasons)})" if reasons else "")
            )
        sheet.add(
            kind="evaluation",
            domain=evaluation["domain"],
            statement=(
                f"Stored {evaluation['domain']} evaluation {index} of {len(evaluations)} "
                f"(window {evaluation['window_start']} to {evaluation['window_end']}, mission "
                f"phase {evaluation.get('mission_phase') or 'not specified'}): overall status "
                f"'{evaluation['status']}'; window {_quality_phrase(quality)}; produced by "
                f"algorithm {algorithm.get('name')} {algorithm.get('version')}."
                + (f" Status per metric: {'; '.join(per_metric)}." if per_metric else "")
            ),
            data={
                "evaluation_id": evaluation["evaluation_id"],
                "status": evaluation["status"],
                "status_per_metric": {
                    finding["metric"]: finding["status"]
                    for finding in evaluation.get("findings", [])
                },
                "window_start": evaluation["window_start"],
                "window_end": evaluation["window_end"],
                "mission_phase": evaluation.get("mission_phase"),
                "evaluated_at": evaluation.get("evaluated_at"),
                "algorithm": algorithm,
                "data_quality": _quality_view(quality),
                "summary": _excerpt(evaluation.get("summary"), (" Policy:",)),
            },
            source=FactSource(
                path=f"{crew_path}/evaluations", resource_id=evaluation["evaluation_id"]
            ),
            interpretation_role=_role_for_status(evaluation["status"]),
        )
        for finding in evaluation.get("findings", []):
            explanation = finding.get("explanation") or ""
            details = parse_explanation(explanation)
            if finding["metric"] not in finding_metrics:
                finding_metrics.append(finding["metric"])
            # Evaluations are in chronological order, so the last one seen is the latest.
            latest_finding[finding["metric"]] = (finding["status"], details)
            baseline_id = finding.get("baseline_id")
            if baseline_id and baseline_id not in referenced_baselines:
                referenced_baselines.append(baseline_id)
            relative = finding.get("relative_deviation")
            sheet.add(
                kind="finding",
                domain=evaluation["domain"],
                metric=finding["metric"],
                statement=_finding_statement(finding, evaluation, details),
                data={
                    "evaluation_id": evaluation["evaluation_id"],
                    "window_start": evaluation["window_start"],
                    "window_end": evaluation["window_end"],
                    "status": finding["status"],
                    "unit": finding["unit"],
                    "observed_value": finding.get("observed_value"),
                    "baseline_id": baseline_id,
                    "baseline_value": finding.get("baseline_value"),
                    "absolute_deviation": finding.get("absolute_deviation"),
                    "relative_deviation": relative,
                    "relative_deviation_percent": (
                        None if relative is None else round(relative * 100, 1)
                    ),
                    "details_parsed_from_explanation": details,
                    "algorithm_explanation": _excerpt(explanation, (" Excluded records:",)),
                    "data_quality": _quality_view(finding.get("data_quality")),
                },
                source=FactSource(
                    path=f"{crew_path}/evaluations", resource_id=evaluation["evaluation_id"]
                ),
                interpretation_role=_role_for_status(finding["status"]),
            )

    baselines = {item["baseline_id"]: item for item in snapshot.baselines}
    for baseline_id in referenced_baselines:
        baseline = baselines.get(baseline_id)
        if baseline is None:
            continue
        statistics = baseline.get("statistics") or {}
        unit = baseline["unit"]
        listed = ", ".join(
            f"{label} {format_number(statistics[key])} {unit}"
            for key, label in (
                ("median", "median"),
                ("mean", "mean"),
                ("standard_deviation", "standard deviation"),
                ("median_absolute_deviation", "median absolute deviation"),
                ("minimum", "minimum"),
                ("maximum", "maximum"),
            )
            if statistics.get(key) is not None
        )
        sheet.add(
            kind="baseline",
            domain=metric_domain.get(baseline["metric"]),
            metric=baseline["metric"],
            statement=(
                f"Personal baseline of {baseline['metric']} (mission phase "
                f"{baseline['mission_phase']}, status '{baseline['status']}'): {listed}; "
                f"computed from {baseline['sample_count']} samples in the reference window "
                f"{baseline['window_start']} to {baseline['window_end']}; reference "
                f"{_quality_phrase(baseline.get('data_quality'))}."
            ),
            data={
                "baseline_id": baseline_id,
                "status": baseline["status"],
                "unit": unit,
                "mission_phase": baseline["mission_phase"],
                "sample_count": baseline["sample_count"],
                "window_start": baseline["window_start"],
                "window_end": baseline["window_end"],
                "statistics": statistics,
                "data_quality": _quality_view(baseline.get("data_quality")),
            },
            source=FactSource(path=f"{crew_path}/baselines", resource_id=baseline_id),
            interpretation_role="context",
        )

    window = _measurement_window(evaluations)
    if window:
        for metric in finding_metrics:
            points = [
                item
                for item in measurements
                if item["metric"] == metric and window[0] <= item["measured_at"] < window[1]
            ]
            if not points:
                continue
            omitted = max(0, len(points) - _MAX_SERIES_POINTS)
            points = points[-_MAX_SERIES_POINTS:]
            unit = points[0]["unit"]
            status, latest_details = latest_finding[metric]
            missing_nights = latest_details.get("missing_nights") or []
            listed = "; ".join(
                f"{item['measured_at'][:10]}: {format_number(item['value'])} {unit} "
                f"({(item.get('data_quality') or {}).get('status', 'not reported')})"
                for item in points
            )
            sheet.add(
                kind="measurement_series",
                domain=metric_domain.get(metric),
                metric=metric,
                statement=(
                    f"Stored {metric} records with a start time between {window[0]} and "
                    f"{window[1]}, oldest first, as date: value (data quality): {listed}."
                    + (f" {omitted} older records are not listed." if omitted else "")
                    + (
                        f" Nights reported missing by the latest finding: "
                        f"{', '.join(missing_nights)}."
                        if missing_nights
                        else ""
                    )
                    + f" The latest stored finding for this metric has status '{status}'."
                ),
                data={
                    "unit": unit,
                    "window_start": window[0],
                    "window_end": window[1],
                    "latest_finding_status": status,
                    "missing_nights_in_latest_finding": missing_nights,
                    "omitted_older_records": omitted,
                    "points": [
                        {
                            "measurement_id": item["measurement_id"],
                            "measured_at": item["measured_at"],
                            "value": item["value"],
                            "quality_status": (item.get("data_quality") or {}).get("status"),
                        }
                        for item in points
                    ],
                },
                source=FactSource(path=f"{crew_path}/measurements"),
                interpretation_role="context",
            )

    if measurements:
        statuses = Counter(
            (item.get("data_quality") or {}).get("status", "not_reported") for item in measurements
        )
        problem_by_metric = Counter(
            item["metric"]
            for item in measurements
            if (item.get("data_quality") or {}).get("status") in _PROBLEM_QUALITY
        )
        listed = ", ".join(f"{name}: {count}" for name, count in sorted(statuses.items()))
        by_metric = ", ".join(
            f"{name}: {count}" for name, count in sorted(problem_by_metric.items())
        )
        sheet.add(
            kind="quality_overview",
            statement=(
                f"Data quality status of the {len(measurements)} stored measurements in "
                f"scope: {listed}."
                + (f" Records with a quality problem per metric: {by_metric}." if by_metric else "")
            ),
            data={
                "measurement_count": len(measurements),
                "status_counts": dict(sorted(statuses.items())),
                "problem_records_by_metric": dict(sorted(problem_by_metric.items())),
            },
            source=FactSource(path=f"{crew_path}/measurements"),
            interpretation_role="data_quality",
        )

    issues = [
        item
        for item in measurements
        if (item.get("data_quality") or {}).get("status") in _PROBLEM_QUALITY
    ]
    for item in issues[:_MAX_ISSUE_FACTS]:
        quality = item["data_quality"]
        note = f" Quality note: {quality['notes']}" if quality.get("notes") else ""
        sheet.add(
            kind="measurement_quality_issue",
            domain=metric_domain.get(item["metric"]),
            metric=item["metric"],
            statement=(
                f"The {item['metric']} record with start time {item['measured_at']} has the "
                f"stored value {format_number(item['value'])} {item['unit']} and "
                f"{_quality_phrase(quality)}.{note}"
            ),
            data={
                "measurement_id": item["measurement_id"],
                "measured_at": item["measured_at"],
                "value": item["value"],
                "unit": item["unit"],
                "source": item["source"],
                "device_id": item.get("device_id"),
                "data_quality": _quality_view(quality),
            },
            source=FactSource(path=f"{crew_path}/measurements", resource_id=item["measurement_id"]),
            interpretation_role="data_quality",
        )
    if len(issues) > _MAX_ISSUE_FACTS:
        sheet.add(
            kind="quality_overview",
            statement=(
                f"{len(issues) - _MAX_ISSUE_FACTS} further degraded or unusable records are "
                "stored but not listed individually."
            ),
            data={"unlisted_problem_records": len(issues) - _MAX_ISSUE_FACTS},
            source=FactSource(path=f"{crew_path}/measurements"),
            interpretation_role="data_quality",
        )
    return sheet
