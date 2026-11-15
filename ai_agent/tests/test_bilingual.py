"""Natural conversation in English and Italian, with scripted model replies.

Regression tests for the report that "ciao" produced a physiological analysis. The Italian
messages are in tests/fixtures/conversation_cases.json, so that this file stays ASCII
English like the rest of the source code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orbit_agent.composer import Draft
from orbit_agent.language import detect_language
from orbit_agent.lexicon import italian_text
from orbit_agent.models import ExplanationRequest
from orbit_agent.routing import answer_profile, classify_question, conversation_intent
from orbit_agent.verifier import (
    attribution_problems,
    capability_problems,
    language_problems,
    verify_draft,
)
from tests.support import NOOR, FakeOllama, fact_sheet, make_agent, noor_draft
from tests.test_integration import TwoModelOllama, medgemma_agent, verdicts

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "conversation_cases.json").read_text(encoding="utf-8")
)
MESSAGES: dict[str, str] = CASES["messages"]
DRAFTS: dict[str, str] = CASES["drafts"]
ITALIAN_INSTRUCTION = "The operator wrote in Italian"


def _reply(headline: str) -> dict[str, Any]:
    return {
        "headline": headline,
        "observations": [],
        "evidence_context": [],
        "interpretations": [],
        "uncertainties": [],
    }


@pytest.mark.parametrize("case", CASES["routing"], ids=lambda case: case["text"])
def test_routing_and_language_in_both_languages(case: dict[str, str]) -> None:
    kind = classify_question(case["text"])

    assert kind == case["kind"]
    assert answer_profile(kind) == case["profile"]
    assert detect_language(case["text"]) == case["language"]


@pytest.mark.parametrize(
    ("key", "intent"),
    [
        ("greeting", "greeting"),
        ("platform", "about"),
        ("memory", "earlier_exchange"),
        ("off_topic", "out_of_scope"),
    ],
)
def test_conversational_messages_get_one_targeted_instruction(key: str, intent: str) -> None:
    assert conversation_intent(MESSAGES[key]) == intent
    ollama = FakeOllama(drafts=[_reply("Ok.")])
    make_agent(ollama=ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question=MESSAGES[key])
    )
    prompt = ollama.prompt(0)
    expected = {
        "greeting": "greets or thanks you",
        "about": "restate this description",
        "earlier_exchange": "refers to an earlier message",
        "out_of_scope": "cannot help with that request",
    }
    assert expected[intent] in prompt
    assert all(text not in prompt for name, text in expected.items() if name != intent)


def _assert_conversational(response: Any) -> None:
    """A conversational reply: headline only, no report, no review banner, no MedGemma."""
    assert response.generation.question_kind == "greeting"
    assert response.generation.answer_profile == "conversation"
    assert response.observations == [] and response.interpretations == []
    assert response.evidence_context == [] and response.citations == []
    assert response.suggested_checks == []
    assert response.human_review.recommended is False
    assert response.generation.specialist.consulted is False
    assert response.generation.specialist.decision in {
        "conversational_question",
        "non_generative",
        "not_configured",
    }
    assert response.verification.passed


def test_italian_greeting_gets_an_italian_greeting_and_no_report() -> None:
    ollama = TwoModelOllama(drafts=[_reply(DRAFTS["greeting"])])
    response = medgemma_agent(ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question=MESSAGES["greeting"])
    )

    _assert_conversational(response)
    assert response.generation.mode == "generative"
    assert response.headline == DRAFTS["greeting"] and response.headline_origin == "model"
    assert response.uncertainties == []
    assert ollama.specialist_requests == []
    prompt = ollama.prompt(0)
    assert ITALIAN_INSTRUCTION in prompt
    assert '"facts": []' in prompt and '"checks_already_suggested": []' in prompt


def test_platform_question_is_answered_from_the_fixed_description() -> None:
    ollama = FakeOllama(drafts=[_reply(DRAFTS["platform"])])
    response = make_agent(ollama=ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question=MESSAGES["platform"])
    )

    _assert_conversational(response)
    assert response.headline == DRAFTS["platform"]
    assert "does not remember earlier questions" in ollama.prompt(0)


def test_italian_greeting_falls_back_to_a_fixed_italian_greeting() -> None:
    response = make_agent(ollama=FakeOllama(reachable=False)).explain(
        ExplanationRequest(crew_member_id=NOOR, question=MESSAGES["greeting"])
    )

    _assert_conversational(response)
    assert response.generation.mode == "deterministic_fallback"
    assert response.headline == italian_text("greeting")
    assert response.headline_origin == "rule"


def test_greeting_reply_that_reports_results_is_rejected() -> None:
    # A reply with a value the facts do not hold fails the verifier like any sentence.
    ollama = FakeOllama(drafts=[_reply("Hello! Noor slept 395 minutes last night.")])
    response = make_agent(ollama=ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question="Hello!")
    )

    assert response.headline_origin == "rule"
    assert response.headline.startswith("Hello! I am the OrbitVitals assistant")
    assert response.verification.passed


def test_memory_question_gets_an_honest_reply_in_italian() -> None:
    ollama = FakeOllama(drafts=[_reply(DRAFTS["memory"])])
    response = make_agent(ollama=ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question=MESSAGES["memory"])
    )

    _assert_conversational(response)
    assert [item.text for item in response.uncertainties] == [italian_text("memory_limit")]


def test_off_topic_question_gets_no_report() -> None:
    response = make_agent(ollama=FakeOllama(reachable=False)).explain(
        ExplanationRequest(crew_member_id=NOOR, domain="sleep", question=MESSAGES["off_topic"])
    )

    _assert_conversational(response)


def test_italian_factual_question_gets_a_brief_grounded_answer_in_italian() -> None:
    draft = noor_draft(fact_sheet(NOOR, "sleep"))
    draft["observations"] = draft["observations"][:1]
    draft["evidence_context"], draft["uncertainties"] = [], []
    ollama = TwoModelOllama(drafts=[draft])
    response = medgemma_agent(ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, domain="sleep", question=MESSAGES["factual"])
    )

    assert response.generation.question_kind == "factual"
    assert response.generation.specialist.decision == "factual_question"
    assert ollama.specialist_requests == []
    assert ITALIAN_INSTRUCTION in ollama.prompt(0)
    # A data answer keeps the report sections and the review recommendation.
    assert response.observations and response.human_review.recommended
    assert response.verification.passed


def test_italian_biomedical_question_is_reviewed_by_medgemma() -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[verdicts(("I1", "supported", None))],
    )
    response = medgemma_agent(ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, domain="sleep", question=MESSAGES["biomedical"])
    )

    assert response.generation.question_kind == "interpretive"
    assert response.generation.specialist.decision == "consulted"
    assert len(ollama.specialist_requests) == 1
    assert ITALIAN_INSTRUCTION in ollama.prompt(0)
    assert response.verification.passed


@pytest.mark.parametrize("text", CASES["verifier"]["rejected"])
def test_italian_unsafe_wording_is_rejected(text: str) -> None:
    assert language_problems(text) or attribution_problems(text) or capability_problems(text)


@pytest.mark.parametrize("text", CASES["verifier"]["accepted"])
def test_italian_denials_are_accepted(text: str) -> None:
    assert not (language_problems(text) or attribution_problems(text) or capability_problems(text))


def test_ordinary_italian_word_for_alarm_is_not_a_status_name() -> None:
    # Seen live (2026-11-15): "segnali di allarme" in a reading of a 'nominal' result was
    # taken for the status 'alert', and the reading was dropped. Only "allerta" names it.
    sheet = fact_sheet(NOOR, "sleep")
    efficiency = [f for f in sheet.of_kind("finding") if f.metric == "sleep_efficiency"][-1]
    draft = noor_draft(sheet)
    draft["observations"] = [
        {"text": CASES["verifier"]["alarm_words"], "fact_ids": [efficiency.id]}
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert not any("'alert'" in reason for item in result.rejected for reason in item.reasons)


def test_italian_status_name_must_match_the_cited_fact() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    efficiency = [f for f in sheet.of_kind("finding") if f.metric == "sleep_efficiency"][-1]
    assert efficiency.data["status"] != "alert"
    draft = noor_draft(sheet)
    draft["observations"] = [
        {"text": CASES["verifier"]["status_mismatch"], "fact_ids": [efficiency.id]}
    ]

    result = verify_draft(Draft.model_validate(draft), sheet, [])

    assert any(
        "'alert' is not the status of any cited fact" in reason
        for item in result.rejected
        for reason in item.reasons
    )
