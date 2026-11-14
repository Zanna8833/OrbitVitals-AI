"""Facts carry the backend values unchanged."""

import pytest

from orbit_agent.facts import BackendSnapshot, build_fact_sheet, format_number, parse_explanation
from tests.support import CHEN, NOOR, fact_sheet, load_fixture, snapshot


def _api_findings(crew: str, domain: str | None = None) -> list[tuple[dict, dict]]:
    return [
        (evaluation, finding)
        for evaluation in load_fixture(crew, "evaluations.json")
        if domain is None or evaluation["domain"] == domain
        for finding in evaluation["findings"]
    ]


@pytest.mark.parametrize(("crew", "domain"), [(NOOR, "sleep"), (NOOR, None), (CHEN, None)])
def test_every_finding_value_equals_the_api_value(crew: str, domain: str | None) -> None:
    sheet = fact_sheet(crew, domain)
    facts = {(fact.data["evaluation_id"], fact.metric): fact for fact in sheet.of_kind("finding")}
    api = _api_findings(crew, domain)

    assert len(facts) == len(api)
    for evaluation, finding in api:
        fact = facts[(evaluation["evaluation_id"], finding["metric"])]
        for key in ("status", "unit", "observed_value", "baseline_value", "absolute_deviation"):
            assert fact.data[key] == finding[key]
        assert fact.data["relative_deviation"] == finding["relative_deviation"]
        assert fact.source.resource_id == evaluation["evaluation_id"]
        assert fact.source.method == "GET"


def test_noor_latest_sleep_duration_finding() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    latest = [fact for fact in sheet.of_kind("finding") if fact.metric == "sleep_duration"][-1]
    details = latest.data["details_parsed_from_explanation"]

    assert latest.data["status"] == "attention"
    assert latest.data["observed_value"] == 430.0
    assert latest.data["baseline_value"] == 480.0
    assert latest.data["absolute_deviation"] == -50.0
    assert latest.data["relative_deviation_percent"] == -10.4
    assert details["trend_slope_per_day"] == -15.0
    assert details["trend_slope_unit"] == "min/day"
    assert details["trend_fitted_change"] == -120.0
    assert details["included_nights"] == 7
    assert details["expected_nights"] == 9
    assert details["missing_nights"] == ["2026-10-14", "2026-10-18"]
    assert details["detected_pattern"] == "progressive_duration_reduction"
    assert latest.interpretation_role == "screening_signal"
    assert "430 min" in latest.statement and "-120 min" in latest.statement


def test_noor_sleep_progression_and_baseline() -> None:
    sheet = fact_sheet(NOOR, "sleep")

    statuses = [fact.data["status"] for fact in sheet.of_kind("evaluation")]
    assert statuses == ["insufficient_data", "attention", "attention"]

    series = next(f for f in sheet.of_kind("measurement_series") if f.metric == "sleep_duration")
    assert [point["value"] for point in series.data["points"]] == [
        490.0,
        475.0,
        445.0,
        430.0,
        415.0,
        385.0,
        370.0,
    ]

    baseline = next(f for f in sheet.of_kind("baseline") if f.metric == "sleep_duration")
    api_baseline = next(
        item for item in load_fixture(NOOR, "baselines.json") if item["metric"] == "sleep_duration"
    )
    assert baseline.data["statistics"] == api_baseline["statistics"]
    assert baseline.data["sample_count"] == api_baseline["sample_count"] == 14
    assert baseline.data["status"] == "established"
    assert baseline.interpretation_role == "context"


def test_insufficient_findings_carry_no_physiological_basis() -> None:
    sheet = fact_sheet(CHEN)

    insufficient = [
        fact for fact in sheet.of_kind("finding") if fact.data["status"] == "insufficient_data"
    ]
    assert len(insufficient) == 6
    assert {fact.interpretation_role for fact in insufficient} == {"no_physiological_basis"}
    activity = next(fact for fact in insufficient if fact.metric == "exercise_duration")
    assert activity.data["observed_value"] is None
    assert "No observed value could be computed." in activity.statement


def test_chen_quality_issues_match_the_api() -> None:
    sheet = fact_sheet(CHEN)
    api_problems = {
        item["measurement_id"]: item
        for item in load_fixture(CHEN, "measurements.json")
        if item["data_quality"]["status"] != "acceptable"
    }
    issues = sheet.of_kind("measurement_quality_issue")

    assert len(issues) == len(api_problems) == 7
    for fact in issues:
        api = api_problems[fact.data["measurement_id"]]
        assert fact.data["value"] == api["value"]
        assert fact.data["data_quality"]["status"] == api["data_quality"]["status"] == "unusable"
        assert fact.data["data_quality"]["flags"] == api["data_quality"]["flags"]
        assert api["data_quality"]["notes"] in fact.statement
        assert fact.interpretation_role == "data_quality"
    overview = sheet.of_kind("quality_overview")[0]
    assert overview.data["status_counts"] == {"acceptable": 132, "unusable": 7}


def test_provenance_reports_simulated_sources() -> None:
    sheet = fact_sheet(NOOR)
    provenance = sheet.of_kind("provenance")[0]

    assert provenance.data["sources"] == {"simulated": 171}
    assert "synthetic" in provenance.statement


def test_domain_filter_limits_measurements_to_that_domain() -> None:
    sheet = fact_sheet(NOOR, "sleep")

    assert sheet.domains == ["sleep"]
    assert sheet.of_kind("provenance")[0].data["measurement_count"] == 42
    assert {fact.metric for fact in sheet.of_kind("finding")} == {
        "sleep_duration",
        "sleep_efficiency",
    }


def test_crew_member_without_stored_results() -> None:
    empty = BackendSnapshot(
        crew_member_id="unknown-crew",
        metric_catalog=load_fixture("metrics.json"),
        evaluations=[],
        baselines=[],
        measurements=[],
    )
    sheet = build_fact_sheet(empty)

    assert [fact.kind for fact in sheet.facts] == ["provenance", "evaluation"]
    assert sheet.facts[1].interpretation_role == "no_physiological_basis"
    assert "no stored evaluation" in sheet.facts[1].statement


def test_fact_sheet_is_deterministic() -> None:
    first = build_fact_sheet(snapshot(CHEN))
    second = build_fact_sheet(snapshot(CHEN))

    assert [fact.model_dump() for fact in first.facts] == [
        fact.model_dump() for fact in second.facts
    ]
    assert [fact.id for fact in first.facts] == [f"F{n}" for n in range(1, len(first.facts) + 1)]


def test_unrecognised_explanation_yields_no_parsed_values() -> None:
    assert parse_explanation("A completely different wording.") == {}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (480.0, "480"),
        (-0.10416666, "-0.104"),
        (241.66666, "241.667"),
        (0.5, "0.5"),
        (None, "not available"),
    ],
)
def test_format_number_adds_no_precision(value: float | None, expected: str) -> None:
    assert format_number(value) == expected
