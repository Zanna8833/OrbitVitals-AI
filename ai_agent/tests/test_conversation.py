"""Conversation, general questions and honest limits, with scripted Qwen drafts."""

from __future__ import annotations

from typing import Any

import pytest

from orbit_agent.models import ExplanationRequest
from orbit_agent.routing import answer_profile, classify_question
from orbit_agent.verifier import capability_problems
from tests.support import FIRST_RETRIEVED, NOOR, FakeOllama, make_agent, offered_evidence_ids
from tests.test_integration import TwoModelOllama, medgemma_agent


def _draft(headline: str, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "headline": headline,
        "observations": [],
        "evidence_context": evidence or [],
        "interpretations": [],
        "uncertainties": [],
    }


@pytest.mark.parametrize(
    ("question", "kind", "profile"),
    [
        ("Hello!", "greeting", "conversation"),
        ("Good morning", "greeting", "conversation"),
        ("What can you do?", "greeting", "conversation"),
        ("Thanks a lot", "greeting", "conversation"),
        ("Hi, why is Noor's sleep flagged?", "interpretive", "full"),
        ("How does microgravity affect bones in general?", "general", "general"),
        ("What does the attention status mean on the dashboard?", "general", "general"),
        ("How long is the mission?", "general", "general"),
        ("What was Noor's latest sleep duration?", "factual", "brief"),
        ("Which medication should Noor take?", "clinical_advice", "full"),
    ],
)
def test_conversational_routing(question: str, kind: str, profile: str) -> None:
    assert classify_question(question) == kind
    assert answer_profile(kind) == profile


def test_greeting_is_answered_by_qwen_alone_without_evidence() -> None:
    ollama = TwoModelOllama(
        drafts=[
            _draft(
                "Hello. I explain the stored monitoring results of the selected crew "
                "member and can answer questions about them."
            )
        ]
    )
    response = medgemma_agent(ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question="Hello!")
    )

    assert response.generation.mode == "generative"
    assert response.generation.question_kind == "greeting"
    assert response.generation.answer_profile == "conversation"
    assert response.headline_origin == "model" and response.headline.startswith("Hello.")
    assert response.citations == [] and response.evidence_context == []
    assert response.generation.specialist.decision == "conversational_question"
    assert ollama.specialist_requests == []
    request = ollama.chat_requests[0]
    assert request["options"]["num_predict"] == 200
    assert request["format"]["properties"]["observations"]["maxItems"] == 0
    # No report: no crew facts in the prompt, no limits, checks or review banner shown.
    assert '"facts": []' in ollama.prompt(0)
    assert response.uncertainties == [] and response.suggested_checks == []
    assert response.human_review.recommended is False
    assert response.observations == [] and response.interpretations == []
    # The data stays available for the dashboard, and provenance is unchanged.
    assert response.status_summary and response.facts
    assert response.data_provenance.crew_data_kind == "simulated"
    assert response.verification.passed


def test_general_question_is_answered_from_the_evidence_without_specialist() -> None:
    ollama = TwoModelOllama(
        drafts=[
            _draft(
                "Spaceflight changes several body systems, as the cited research describes.",
                [
                    {
                        "text": "Spaceflight conditions affect the body.",
                        "evidence_ids": [FIRST_RETRIEVED],
                    }
                ],
            )
        ]
    )
    response = medgemma_agent(ollama).explain(
        ExplanationRequest(
            crew_member_id=NOOR, question="How does microgravity affect bones in general?"
        )
    )

    assert response.generation.question_kind == "general"
    assert response.generation.answer_profile == "general"
    assert response.generation.mode == "generative"
    assert response.citations, "a general answer cites the corpus"
    assert response.generation.specialist.decision == "general_question"
    assert ollama.specialist_requests == []
    assert response.verification.passed


def test_general_question_retrieves_evidence_on_its_own_subject() -> None:
    # Noor's sleep and activity are flagged; a general question about bones must still
    # be offered bone evidence, not entries chosen for the flagged domains.
    ollama = FakeOllama(drafts=[_draft("Spaceflight affects bones, as the cited entries say.")])
    make_agent(ollama=ollama).explain(
        ExplanationRequest(
            crew_member_id=NOOR, question="How does microgravity affect bones in general?"
        )
    )
    offered = offered_evidence_ids(ollama.chat_requests[0])

    assert offered and all("BONE" in item or "GRAVITY" in item for item in offered), offered

    flagged = FakeOllama(drafts=[_draft("Sleep duration shows a decline.")])
    make_agent(ollama=flagged).explain(
        ExplanationRequest(crew_member_id=NOOR, question="Why is Noor's sleep flagged?")
    )
    # A question about the crew member keeps evidence chosen from the flagged domains.
    assert not any("BONE" in item for item in offered_evidence_ids(flagged.chat_requests[0]))


def test_dashboard_question_is_answered_from_the_statuses_without_literature() -> None:
    # In the corpus "attention" is a cognitive skill; a search would offer unrelated entries.
    ollama = FakeOllama(
        drafts=[_draft("The attention status means a screening signal that a person reviews.")]
    )
    response = make_agent(ollama=ollama).explain(
        ExplanationRequest(
            crew_member_id=NOOR, question="What does the attention status mean on the dashboard?"
        )
    )

    assert response.generation.question_kind == "general"
    assert offered_evidence_ids(ollama.chat_requests[0]) == []
    assert response.citations == []
    assert response.headline_origin == "model"
    assert response.verification.passed


def test_claim_of_memory_or_action_is_rejected() -> None:
    for text in (
        "As I said earlier, sleep was flagged.",
        "I remember your last question about Noor.",
        "I will notify the flight surgeon.",
        "I have contacted the crew member.",
        # Seen live: false, the agent reads the selected crew member's stored results.
        "I can explain crew health data, but I don't have access to specific results yet.",
        "I cannot compare today's data because no monitoring records are available for this "
        "crew member.",
    ):
        assert capability_problems(text), text
    assert capability_problems("I don't have access to weather information.") == []
    assert capability_problems("The screen returned 'attention' for sleep duration.") == []

    ollama = FakeOllama(drafts=[_draft("As I said earlier, I can help with the records.")])
    response = make_agent(ollama=ollama).explain(
        ExplanationRequest(crew_member_id=NOOR, question="Hello")
    )
    # The only sentence of the reply is rejected, so the rule-based answer is returned.
    assert response.headline_origin == "rule"
    assert response.generation.fallback_reason == "draft_failed_verification"
    assert all(run.rejected_sentences == 1 for run in response.generation.model_runs)
    assert "earlier" not in response.headline
    assert response.verification.passed


def test_question_about_an_earlier_exchange_and_the_mission_gets_honest_limits() -> None:
    response = make_agent().explain(
        ExplanationRequest(
            crew_member_id=NOOR,
            question="As I asked before, how long is the mission?",
            mode="deterministic",
        )
    )
    texts = [u.text for u in response.uncertainties]

    assert any("keeps no memory of earlier questions" in t for t in texts)
    assert any("no information about the mission" in t for t in texts)
    assert response.verification.passed


def test_greeting_falls_back_safely_when_qwen_is_down() -> None:
    response = make_agent(ollama=FakeOllama(reachable=False)).explain(
        ExplanationRequest(crew_member_id=NOOR, question="Hello")
    )

    # A fixed greeting, not a status report.
    assert response.generation.mode == "deterministic_fallback"
    assert response.headline.startswith("Hello! I am the OrbitVitals assistant")
    assert response.headline_origin == "rule"
    assert response.observations == [] and response.interpretations == []
    assert response.uncertainties == [] and response.suggested_checks == []
    assert response.verification.passed
