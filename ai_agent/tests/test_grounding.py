"""Numbers and dates in a sentence must come from the cited sources."""

import pytest

from orbit_agent.grounding import (
    dates_in,
    fact_dates,
    fact_numbers,
    numbers_in,
    ungrounded_values,
)
from tests.support import CHEN, NOOR, fact_sheet


def _latest_duration_finding():
    sheet = fact_sheet(NOOR, "sleep")
    return [fact for fact in sheet.of_kind("finding") if fact.metric == "sleep_duration"][-1]


def test_identifiers_dates_and_timestamps_are_not_values() -> None:
    text = (
        "Record sim-mission-v1-02:current:sim-sleep-restriction-05-sleep_duration of baseline "
        "544f923a-eb02-52a0-83bf-7b177b3570f9 at 2026-10-17T22:00:00Z, see NASA-SLEEP-RISK-01 "
        "and F12: 415 min."
    )

    assert numbers_in(text) == [415.0]
    assert dates_in(text) == {"2026-10-17"}


def test_signs_ranges_fractions_and_number_words() -> None:
    assert numbers_in("slope=-15 min/day over 7/9 nights, 10-12% lower") == [15, 7, 9, 10, 12]
    assert numbers_in("a 7-night window and two missing nights") == [7, 2]
    assert numbers_in("1,200 kcal") == [1200]
    assert numbers_in("the 2nd window of v1") == []


def test_fact_allows_its_own_values_in_usual_presentations() -> None:
    fact = _latest_duration_finding()
    numbers, dates = fact_numbers(fact), fact_dates(fact)

    for sentence in (
        "Observed 430 min against a baseline of 480 min, 50 min lower.",
        "That is 10.4% below baseline, about 10%.",
        "Coverage was 0.778, or 77.8%, with 7 of 9 nights included.",
        "The slope is 15 min/day and the fitted change is 120 min.",
        "The observed value is about 7.2 hours, the baseline 8 hours.",
        "Two nights are missing: 2026-10-14 and 2026-10-18.",
        "Nights on October 14 and October 18 are missing.",
    ):
        assert ungrounded_values(sentence, numbers, dates) == [], sentence


@pytest.mark.parametrize(
    ("sentence", "invented"),
    [
        ("The observed value is 400 min.", ["400"]),
        ("Sleep fell by 25% from baseline.", ["25"]),
        ("The night of 2026-10-19 is missing.", ["2026-10-19"]),
        ("The slope is 16.5 min/day.", ["16.5"]),
        ("Three nights are missing.", ["3"]),
        ("The crew member slept 6 hours.", ["6"]),
    ],
)
def test_invented_values_are_reported(sentence: str, invented: list[str]) -> None:
    fact = _latest_duration_finding()

    assert ungrounded_values(sentence, fact_numbers(fact), fact_dates(fact)) == invented


def test_values_of_another_fact_are_not_allowed() -> None:
    sheet = fact_sheet(CHEN)
    issue = sheet.of_kind("measurement_quality_issue")[0]
    other = sheet.of_kind("measurement_quality_issue")[4]

    assert "125" in issue.statement and "-30" in other.statement
    assert ungrounded_values("The value is 30 min.", fact_numbers(issue), fact_dates(issue)) == [
        "30"
    ]
