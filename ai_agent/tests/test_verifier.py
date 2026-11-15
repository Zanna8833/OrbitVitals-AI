"""Sentence-level guardrails applied to model drafts."""

from typing import Any

import pytest

from orbit_agent.composer import Draft, draft_schema
from orbit_agent.evidence.store import EvidenceStore, ScoredPassage
from orbit_agent.rules import rule_evidence_context
from orbit_agent.verifier import VerifiedDraft, _Context, language_problems, verify_draft
from tests.support import CHEN, NOOR, fact_id, fact_sheet, noor_draft

STORE = EvidenceStore.load()
SLEEP_PASSAGES = [STORE.get("NASA-SLEEP-RISK-01"), STORE.get("NASA-SLEEP-RISK-03")]


def _verify_noor(change: dict[str, Any] | None = None) -> VerifiedDraft:
    sheet = fact_sheet(NOOR, "sleep")
    draft = noor_draft(sheet, "NASA-SLEEP-RISK-01")
    draft.update(change or {})
    return verify_draft(Draft.model_validate(draft), sheet, SLEEP_PASSAGES)


def _reasons(result: VerifiedDraft) -> str:
    return " | ".join(reason for item in result.rejected for reason in item.reasons)


def test_correct_draft_is_accepted_in_full() -> None:
    result = _verify_noor()

    assert result.rejected == []
    assert result.is_complete
    assert len(result.observations) == 2
    assert result.interpretations[0].kind == "screening_signal"
    assert {item.origin for item in result.observations} == {"model"}


def test_invented_number_is_rejected() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    result = _verify_noor(
        {
            "observations": [
                {
                    "text": "The observed value is 395 min, 85 min below baseline.",
                    "fact_ids": [latest],
                }
            ]
        }
    )

    assert result.observations == []
    assert "value not found in the cited sources: 395" in _reasons(result)
    assert "value not found in the cited sources: 85" in _reasons(result)


def test_value_from_an_uncited_fact_is_rejected() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    baseline = fact_id(sheet, kind="baseline", metric="sleep_duration")
    result = _verify_noor(
        {
            "observations": [
                {
                    "text": "The baseline is 480 min and the observed value 430 min.",
                    "fact_ids": [baseline],
                }
            ]
        }
    )

    assert "value not found in the cited sources: 430" in _reasons(result)


def test_status_of_another_window_cannot_be_merged() -> None:
    sheet = fact_sheet(CHEN)
    evaluations = [f for f in sheet.of_kind("evaluation") if f.domain == "sleep"]
    assert [f.data["status"] for f in evaluations] == ["nominal", "insufficient_data"]
    draft = {
        "headline": "No status could be determined.",
        "observations": [
            {
                "text": (
                    "Sleep evaluations for the windows ending 2026-10-19 and 2026-10-26 "
                    "returned 'insufficient_data'."
                ),
                "fact_ids": [fact.id for fact in evaluations],
            }
        ],
        "interpretations": [],
    }

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert result.observations == []
    assert "a cited fact has status 'nominal'" in _reasons(result)


def test_status_absent_from_cited_facts_is_rejected() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    efficiency = [f for f in sheet.of_kind("finding") if f.metric == "sleep_efficiency"][-1]
    result = _verify_noor(
        {
            "observations": [
                {"text": "Sleep efficiency has status 'attention'.", "fact_ids": [efficiency.id]}
            ]
        }
    )

    assert "'attention' is not the status of any cited fact" in _reasons(result)


@pytest.mark.parametrize(
    ("text", "accepted"),
    [
        ("Seven nights in the window have no usable record.", False),
        ("Eight nights in the window have no usable record.", True),
        ("The longest run of missing nights is 7 nights.", True),
        ("There is a run of eight consecutive missing nights.", False),
        ("Only 6 of 14 nights were included, and 8 nights are missing.", True),
        ("Only 6 of 14 nights were included, and 5 nights are missing.", False),
    ],
)
def test_count_of_missing_nights_must_match_the_backend(text: str, accepted: bool) -> None:
    sheet = fact_sheet(CHEN, "sleep")
    latest = [fact for fact in sheet.of_kind("finding") if fact.metric == "sleep_duration"][-1]
    details = latest.data["details_parsed_from_explanation"]
    assert len(details["missing_nights"]) == 8 and details["longest_missing_run"] == 7
    draft = {
        "headline": "No status could be determined.",
        "observations": [{"text": text, "fact_ids": [latest.id]}],
        "interpretations": [],
    }

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert (len(result.observations) == 1) is accepted, _reasons(result)
    if not accepted:
        assert "count mismatch" in _reasons(result)


def test_evidence_link_is_kept_only_when_the_reading_uses_the_passage() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)

    def reading(text: str) -> dict[str, Any]:
        return {
            "text": text,
            "kind": "screening_signal",
            "confidence": "low",
            "fact_ids": [latest],
            "evidence_ids": ["NASA-SLEEP-RISK-01"],
        }

    result = _verify_noor(
        {
            "interpretations": [
                reading("The screen detected a configured pattern and asks for a review."),
                reading(
                    "Heavy workloads and irregular light and dark periods are known "
                    "spaceflight conditions, which is why a flagged reduction is worth a "
                    "review."
                ),
            ]
        }
    )

    assert [item.evidence_ids for item in result.interpretations] == [[], ["NASA-SLEEP-RISK-01"]]


def test_reading_may_not_use_a_number_from_cited_evidence() -> None:
    """A literature value next to a crew value would read as a threshold comparison."""
    sheet = fact_sheet(NOOR, "sleep")
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    passage = STORE.get("LIT-WU2018-01")
    draft = noor_draft(sheet, passage.evidence_id)
    draft["evidence_context"] = [
        {
            "text": "Astronauts averaged about 6 hours of sleep per day in flight.",
            "evidence_ids": [passage.evidence_id],
        }
    ]
    draft["interpretations"] = [
        {
            "text": "The observed 430 min is above the 6 hours that astronauts average in flight.",
            "kind": "screening_signal",
            "confidence": "low",
            "fact_ids": [latest],
            "evidence_ids": [passage.evidence_id],
        },
        {
            "text": "The screen returned 'attention' and asks for a review.",
            "kind": "screening_signal",
            "confidence": "low",
            "fact_ids": [latest],
            "evidence_ids": [],
        },
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [passage])

    # The general statement keeps its number; the reading about the crew member does not.
    assert len(result.evidence_context) == 1
    assert [item.text for item in result.interpretations] == [
        "The screen returned 'attention' and asks for a review."
    ]
    assert "value not found in the cited sources: 6" in _reasons(result)


def test_article_summary_may_cite_its_own_year_and_section_numbers() -> None:
    passage = STORE.get("LIT-CHANCELLOR2014-01")
    sheet = fact_sheet(NOOR, "sleep")
    draft = noor_draft(sheet, passage.evidence_id)
    draft["evidence_context"] = [
        {
            "text": "A 2014 review explains that shielding only partly reduces the dose.",
            "evidence_ids": [passage.evidence_id],
        },
        {
            "text": "A 2019 review explains that shielding only partly reduces the dose.",
            "evidence_ids": [passage.evidence_id],
        },
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [passage])

    assert [item.text for item in result.evidence_context] == [
        "A 2014 review explains that shielding only partly reduces the dose."
    ]
    assert "value not found in the cited sources: 2019" in _reasons(result)


def test_quality_word_must_be_reported_by_a_cited_fact() -> None:
    sheet = fact_sheet(CHEN)
    overview = sheet.of_kind("quality_overview")[0]
    draft = {
        "headline": "No status could be determined.",
        "observations": [
            {
                "text": "The data quality of the stored records is degraded.",
                "fact_ids": [overview.id],
            },
            {"text": "Seven stored records are unusable.", "fact_ids": [overview.id]},
        ],
        "interpretations": [],
    }

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert [item.text for item in result.observations] == ["Seven stored records are unusable."]
    assert "no cited fact reports 'degraded' data quality" in _reasons(result)


def test_headline_may_only_name_a_latest_status() -> None:
    sheet = fact_sheet(CHEN)
    assert "nominal" in {fact.data.get("status") for fact in sheet.of_kind("evaluation")}
    draft = {
        "headline": "Sleep data shows 'nominal' trends but activity readings are unusable.",
        "observations": [],
        "interpretations": [],
    }

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert result.headline is None
    assert "'nominal' is not a latest stored status" in _reasons(result)


def test_series_fact_carries_the_latest_status_of_its_metric() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    series = fact_id(sheet, kind="measurement_series", metric="sleep_duration")
    result = _verify_noor(
        {
            "observations": [
                {
                    "text": (
                        "Sleep duration records have status 'attention', with values from "
                        "490 min to 370 min and no record on 2026-10-14 and 2026-10-18."
                    ),
                    "fact_ids": [series],
                }
            ]
        }
    )

    assert len(result.observations) == 1, _reasons(result)


def test_statement_about_one_metric_may_cite_a_flagged_evaluation() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    efficiency = [f for f in sheet.of_kind("finding") if f.metric == "sleep_efficiency"][-1]
    evaluation = sheet.of_kind("evaluation")[-1]
    result = _verify_noor(
        {
            "observations": [
                {
                    "text": "Sleep efficiency stays 'nominal' at 92 % in the latest window.",
                    "fact_ids": [efficiency.id, evaluation.id],
                }
            ]
        }
    )

    assert len(result.observations) == 1, _reasons(result)


@pytest.mark.parametrize(
    "text",
    [
        "The pattern is consistent with insomnia.",
        "The crew member should take melatonin before sleep.",
        "A dose of 5 mg is appropriate.",
        "This is an emergency.",
        "The crew member is fatigued and stressed.",
        "The crew member is healthy.",
        "This confirms a sleep disorder.",
        "The decline is clinically relevant.",
        "The reduction is statistically significant.",
        "Sleep duration shows a significant decline from baseline.",
        # Seen in a live draft (2026-11-15): the backend makes no significance claim.
        "The observed values deviated significantly from the personal baseline.",
        "Exercise duration decreased significantly.",
    ],
)
def test_medical_and_overreaching_wording_is_rejected(text: str) -> None:
    sheet = fact_sheet(NOOR, "sleep")
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    result = _verify_noor(
        {
            "interpretations": [
                {
                    "text": text,
                    "kind": "screening_signal",
                    "confidence": "low",
                    "fact_ids": [latest],
                    "evidence_ids": [],
                }
            ]
        }
    )

    assert result.interpretations == []
    assert result.rejected[0].section == "interpretations"


@pytest.mark.parametrize(
    "text",
    [
        "This is not a diagnosis.",
        "The settings are not clinical thresholds.",
        "The result does not show that the crew member is healthy.",
        "The data cannot show whether the crew member is fatigued.",
        "Several records contain significant recording errors.",
    ],
)
def test_denied_claims_are_allowed(text: str) -> None:
    assert language_problems(text) == []


def test_reading_without_a_screening_result_is_relabelled_and_cannot_claim_change() -> None:
    sheet = fact_sheet(CHEN)
    insufficient = [
        fact.id for fact in sheet.of_kind("finding") if fact.data["status"] == "insufficient_data"
    ][-2:]
    draft = {
        "headline": "No status could be determined.",
        "observations": [],
        "interpretations": [
            {
                "text": "No physiological conclusion is possible for these metrics.",
                "kind": "screening_signal",
                "confidence": "moderate",
                "fact_ids": insufficient,
                "evidence_ids": [],
            },
            {
                "text": "Sleep is declining in the latest window.",
                "kind": "screening_signal",
                "confidence": "moderate",
                "fact_ids": insufficient,
                "evidence_ids": [],
            },
        ],
    }

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert [item.kind for item in result.interpretations] == ["data_quality"]
    assert "claim of change without a screening result" in _reasons(result)


def test_evidence_statement_must_stay_within_its_passage() -> None:
    result = _verify_noor(
        {
            "evidence_context": [
                {
                    "text": "A 2014 study found crews sleep 6 hours per night.",
                    "evidence_ids": ["NASA-SLEEP-RISK-01"],
                },
                {
                    "text": "Crews on the station see 16 sunrises and 16 sunsets each day.",
                    "evidence_ids": ["NASA-SLEEP-RISK-03"],
                },
                {
                    "text": "Spaceflight stressors apply to sim-mission-v1-02.",
                    "evidence_ids": ["NASA-SLEEP-RISK-01"],
                },
            ]
        }
    )

    assert [item.evidence_ids for item in result.evidence_context] == [["NASA-SLEEP-RISK-03"]]
    assert "value not found in the cited sources: 2014" in _reasons(result)
    assert "general evidence must not refer to the crew member" in _reasons(result)


def test_evidence_summary_may_reuse_words_of_its_passage() -> None:
    passage = STORE.get("NASA-SLEEP-RISK-02")
    sheet = fact_sheet(NOOR, "sleep")
    draft = noor_draft(sheet)
    draft["evidence_context"] = [
        {
            "text": "Research looks at how light exposure and caffeine influence the body clock.",
            "evidence_ids": [passage.evidence_id],
        }
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [passage])

    assert len(result.evidence_context) == 1


@pytest.mark.parametrize(
    "text",
    [
        "According to NASA, sleep loss is a spaceflight risk.",
        "NASA notes that sleep loss and irregular schedules are spaceflight stressors.",
        "NASA's Human Research Program states that sleep loss is a risk.",
        "NASA lists work overload among the conditions of spaceflight.",
        "Sleep loss is a spaceflight risk, as reported by NASA.",
    ],
)
def test_evidence_statement_must_not_present_nasa_as_the_speaker(text: str) -> None:
    result = _verify_noor(
        {"evidence_context": [{"text": text, "evidence_ids": ["NASA-SLEEP-RISK-01"]}]}
    )

    assert result.evidence_context == []
    assert "presents NASA as the speaker" in _reasons(result)


def test_agency_may_be_named_only_when_the_cited_summary_names_it() -> None:
    """A NASA page can describe another agency's study; the publisher is not the actor."""
    sheet = fact_sheet(NOOR, "sleep")
    baseline_study = STORE.get("NASA-SLEEP-STATION-02")  # summary names no agency
    thermolab = STORE.get("NASA-WEARABLE-02")  # summary names ESA
    draft = noor_draft(sheet, baseline_study.evidence_id)
    draft["evidence_context"] = [
        {
            "text": "NASA records individual sleep baselines before a mission.",
            "evidence_ids": [baseline_study.evidence_id],
        },
        {
            "text": "Sleep on Earth is recorded before a mission to form an individual baseline.",
            "evidence_ids": [baseline_study.evidence_id],
        },
        {
            "text": "The ESA Thermolab investigation studied temperature regulation.",
            "evidence_ids": [thermolab.evidence_id],
        },
        {
            "text": "The NASA Thermolab investigation studied temperature regulation.",
            "evidence_ids": [thermolab.evidence_id],
        },
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [baseline_study, thermolab])

    assert [item.text for item in result.evidence_context] == [
        "Sleep on Earth is recorded before a mission to form an individual baseline.",
        "The ESA Thermolab investigation studied temperature regulation.",
    ]
    assert "'NASA' is not named in the cited summary" in _reasons(result)


def test_reading_about_the_crew_member_may_not_name_an_agency() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    result = _verify_noor(
        {
            "interpretations": [
                {
                    "text": "NASA would review this 'attention' result.",
                    "kind": "screening_signal",
                    "confidence": "low",
                    "fact_ids": [latest],
                    "evidence_ids": [],
                },
                {
                    "text": "The screen returned 'attention' and asks for a review.",
                    "kind": "screening_signal",
                    "confidence": "low",
                    "fact_ids": [latest],
                    "evidence_ids": [],
                },
            ]
        }
    )

    assert len(result.interpretations) == 1
    assert "'NASA' is not named in the cited summary" in _reasons(result)


def test_plain_evidence_statement_with_a_nasa_citation_is_accepted() -> None:
    result = _verify_noor(
        {
            "evidence_context": [
                {
                    "text": "Heavy workloads and disrupted sleep are spaceflight stressors.",
                    "evidence_ids": ["NASA-SLEEP-RISK-01"],
                }
            ]
        }
    )

    assert len(result.evidence_context) == 1, _reasons(result)


def test_every_corpus_summary_can_be_shown_by_the_rule_based_fallback() -> None:
    """A stored summary, with its label, title and section, must pass the evidence checks.

    The fixed label names the publisher, so it is checked as rule-based text; the same
    sentence written by a model would be refused for naming NASA as the actor.
    """
    sheet = fact_sheet(NOOR, "sleep")
    scored = [ScoredPassage(passage=passage, score=1.0) for passage in STORE.passages]
    context = _Context(
        facts={fact.id: fact for fact in sheet.facts},
        passages={passage.evidence_id: passage for passage in STORE.passages},
        crew_member_id=sheet.crew_member_id,
    )
    statements = rule_evidence_context(scored)

    assert len(statements) == len(STORE.passages) >= 100
    for statement in statements:
        problems = context.evidence_statement(
            statement.text, [], statement.evidence_ids, model_written=False
        )
        assert problems == [], f"{statement.evidence_ids}: {problems}"
    nasa_page = next(s for s in statements if s.evidence_ids == ["NASA-SLEEP-STATION-02"])
    assert context.evidence_statement(nasa_page.text, [], nasa_page.evidence_ids) == [
        "source attribution: 'NASA' is not named in the cited summary"
    ]


def test_unknown_references_are_rejected() -> None:
    result = _verify_noor(
        {
            "observations": [{"text": "A value was observed.", "fact_ids": ["F999"]}],
            "evidence_context": [
                {"text": "A source says so.", "evidence_ids": ["NASA-INVENTED-99"]}
            ],
        }
    )

    assert result.observations == [] and result.evidence_context == []
    assert "unknown fact F999" in _reasons(result)
    assert "unknown evidence NASA-INVENTED-99" in _reasons(result)


def test_incomplete_draft_is_not_complete() -> None:
    result = _verify_noor({"interpretations": []})

    assert not result.is_complete
    assert result.feedback() == []


def test_schema_only_offers_identifiers_of_the_request() -> None:
    schema = draft_schema(["F2", "F5"], ["NASA-SLEEP-RISK-01"])
    observation = schema["properties"]["observations"]["items"]["properties"]
    interpretation = schema["properties"]["interpretations"]["items"]["properties"]

    assert observation["fact_ids"]["items"]["enum"] == ["F2", "F5"]
    assert interpretation["evidence_ids"]["items"]["enum"] == ["NASA-SLEEP-RISK-01"]
    assert schema["additionalProperties"] is False
    assert "suggested_checks" not in schema["properties"]


def test_schema_forbids_citations_when_nothing_was_retrieved() -> None:
    schema = draft_schema(["F1"], [])

    assert schema["properties"]["evidence_context"]["maxItems"] == 0
    interpretation = schema["properties"]["interpretations"]["items"]["properties"]
    assert interpretation["evidence_ids"] == {"type": "array", "maxItems": 0}
