"""Qwen + MedGemma + NASA evidence integration, with in-memory stand-ins (no network).

These tests check routing, failure handling and the boundaries of each source. They do
not test the models themselves: a scripted reply is not a MedGemma review. Live model
runs are in `scripts/validate_integration.py`.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from orbit_agent.backend_client import BackendUnavailable
from orbit_agent.config import Settings
from orbit_agent.evidence.store import EvidenceStore
from orbit_agent.http import HttpResponse, TransportError
from orbit_agent.medgemma import (
    MedGemmaSpecialist,
    build_user_prompt,
    parse_review,
    review_schema,
    strip_reasoning,
)
from orbit_agent.models import ExplanationRequest, Interpretation
from orbit_agent.nasa_datasets import plan_topics
from orbit_agent.pipeline import Agent
from orbit_agent.routing import classify_question, route_specialist
from orbit_agent.specialist import SpecialistError, SpecialistRequest, create_specialist
from tests.support import (
    BACKEND_URL,
    CHEN,
    MODEL,
    NOOR,
    OLLAMA_URL,
    FakeBackend,
    FakeOllama,
    fact_id,
    fact_sheet,
    make_agent,
    noor_draft,
)

SPECIALIST_MODEL = "medgemma1.5:4b"


def _json(status: int, payload: Any) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload).encode("utf-8"))


# --- NASA Dataset Evidence Adapter stand-in (contract 1.0.0) -------------------------

_MR001G_ITEM = {
    "evidence_id": "nasa-evidence-v1-" + "a" * 64,
    "dataset_id": "nasa-lsda-mr001g-utmb-campaign-3-tilt",
    "title": "UTMB Bedrest Campaign 3 Tilt (MR001G)",
    "nasa_source_url": "https://nlsp.nasa.gov/search/data/details/f4a134da",
    "study_population": "Human ground-study volunteers in a bed-rest campaign.",
    "study_context": "terrestrial_bed_rest_analogue",
    "evidence_scope": "scientific_context_only",
    "crew_telemetry": False,
    "clinically_validated": False,
    "nasa_endorsement": False,
    "topic": "heart_rate",
    "relevant_variables": [
        {
            "source_column": "HR",
            "description": "Heart rate channel as labelled in the export.",
            "source_representation": "numeric cell",
            "unit_verification": "unresolved",
            "canonical_unit": None,
            "transformation": "None.",
        }
    ],
    "context_findings": ["Tilt and supine protocol steps are recorded as context."],
    "structural_findings": [],
    "source_verification": {"state": "not_configured", "checks": [], "pipeline_code_sha256": None},
    "provenance": {},
    "redistribution_status": "unconfirmed",
    "publication_policy": "authored_context_and_verified_structural_counts_only",
    "limitations": ["Units of the export are unresolved; values cannot be compared."],
}


def adapter_payload(topic: str = "heart_rate", **changes: Any) -> dict[str, Any]:
    item = copy.deepcopy(_MR001G_ITEM)
    item["topic"] = topic
    item.update(changes.pop("item", {}))
    payload = {
        "contract_version": "1.0.0",
        "topic": topic,
        "status": "ok",
        "contains_synthetic_findings": False,
        "items": [item],
        "failures": [],
        "notice": "Scientific dataset context only.",
    }
    payload.update(changes)
    return payload


@dataclass
class BackendWithEvidence(FakeBackend):
    """The recorded crew fixtures plus a scripted `/nasa-evidence` endpoint."""

    evidence: dict[str, Any] | None = None
    evidence_status: int = 200
    foreign_crew: str | None = None

    def __call__(self, method: str, url: str, body: Any, timeout: float) -> HttpResponse:
        parsed = urlparse(url)
        if parsed.path.endswith("/nasa-evidence"):
            self.requests.append((method, url))
            topic = parse_qs(parsed.query)["topic"][0]
            if self.evidence_status != 200:
                return _json(self.evidence_status, {"detail": "Not Found"})
            return _json(200, self.evidence or adapter_payload(topic))
        response = super().__call__(method, url, body, timeout)
        if self.foreign_crew and parsed.path.endswith("/measurements"):
            payload = json.loads(response.body)
            payload["items"][0]["crew_member_id"] = self.foreign_crew
            return _json(200, payload)
        return response


# --- MedGemma through Ollama stand-in --------------------------------------------------


@dataclass
class TwoModelOllama(FakeOllama):
    """Qwen drafts plus scripted MedGemma replies, routed by the `model` field."""

    models: list[str] = field(default_factory=lambda: [MODEL, SPECIALIST_MODEL])
    specialist_replies: list[str] = field(default_factory=list)
    specialist_requests: list[dict[str, Any]] = field(default_factory=list)
    specialist_error: bool = False

    def __call__(self, method: str, url: str, body: Any, timeout: float) -> HttpResponse:
        if urlparse(url).path == "/api/chat" and body.get("model") == SPECIALIST_MODEL:
            self.specialist_requests.append(body)
            if self.specialist_error:
                raise TransportError("timed out")
            content = self.specialist_replies[len(self.specialist_requests) - 1]
            return _json(
                200,
                {
                    "message": {"role": "assistant", "content": content},
                    "total_duration": 900_000_000,
                    "load_duration": 4_000_000,
                    "prompt_eval_count": 300,
                    "eval_count": 40,
                },
            )
        return super().__call__(method, url, body, timeout)


def verdicts(*items: tuple[str, str, str | None]) -> str:
    return json.dumps(
        {
            "opinions": [
                {"statement_id": sid, "verdict": verdict, **({"comment": c} if c else {})}
                for sid, verdict, c in items
            ]
        }
    )


def medgemma_agent(
    ollama: TwoModelOllama, backend: FakeBackend | None = None, **settings: Any
) -> Agent:
    config = Settings(
        backend_base_url=BACKEND_URL,
        ollama_base_url=OLLAMA_URL,
        specialist="medgemma",
        specialist_model=SPECIALIST_MODEL,
        specialist_knowledge=settings.pop("specialist_knowledge", False),
        **settings,
    )
    return Agent(
        settings=config,
        store=EvidenceStore.load(),
        backend_transport=backend or FakeBackend(),
        model_transport=ollama,
        specialist=MedGemmaSpecialist(settings=config, transport=ollama),
    )


def _noor(question: str | None = None, **request: Any) -> ExplanationRequest:
    return ExplanationRequest(crew_member_id=NOOR, domain="sleep", question=question, **request)


def _brief_noor_draft() -> dict[str, Any]:
    draft = noor_draft(fact_sheet(NOOR, "sleep"))
    draft["observations"] = draft["observations"][:1]
    draft["evidence_context"] = []
    draft["uncertainties"] = []
    return draft


# --- Routing ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        (None, "none"),
        ("What was Noor's latest sleep duration?", "factual"),
        ("How many nights are missing?", "factual"),
        ("Why is Noor's sleep flagged?", "interpretive"),
        ("What does the attention status mean for Noor?", "interpretive"),
        ("Is Chen sleeping well?", "interpretive"),
        ("What does NASA bed rest research say about sleep?", "general"),
        ("Which medication should Noor take?", "clinical_advice"),
        ("Could this be a sleep disorder?", "clinical_advice"),
    ],
)
def test_questions_are_classified_for_routing(question: str | None, kind: str) -> None:
    assert classify_question(question) == kind


def _reading(kind: str, fact_ids: list[str]) -> Interpretation:
    return Interpretation(
        id="I1", text="A reading.", origin="model", fact_ids=fact_ids, kind=kind, confidence="low"
    )


def test_specialist_routing_rules() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    facts = sheet.by_id()
    flagged = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    nominal = next(
        fact.id
        for fact in sheet.of_kind("finding")
        if fact.metric == "sleep_efficiency" and fact.data.get("status") == "nominal"
    )
    signal = [_reading("screening_signal", [flagged])]

    assert route_specialist("interpretive", signal, facts).consult is True
    assert route_specialist("none", signal, facts).decision == "consulted"
    assert route_specialist("factual", signal, facts).decision == "factual_question"
    assert route_specialist("clinical_advice", signal, facts).decision == (
        "clinical_advice_question"
    )
    quality = [_reading("data_quality", [flagged])]
    assert route_specialist("interpretive", quality, facts).decision == "no_physiological_reading"
    calm = [_reading("screening_signal", [nominal])]
    assert route_specialist("interpretive", calm, facts).decision == "no_flagged_result"


def test_factual_question_gets_a_brief_qwen_draft_and_no_specialist() -> None:
    ollama = TwoModelOllama(drafts=[_brief_noor_draft()])
    response = medgemma_agent(ollama).explain(_noor("What was Noor's latest sleep duration?"))

    assert response.generation.mode == "generative"
    assert response.generation.question_kind == "factual"
    assert response.generation.answer_profile == "brief"
    assert len(ollama.chat_requests) == 1  # Qwen once, MedGemma never
    assert ollama.specialist_requests == []
    request = ollama.chat_requests[0]
    assert request["model"] == MODEL
    assert request["options"]["num_predict"] == Settings().brief_max_output_tokens
    assert request["format"]["properties"]["observations"]["maxItems"] == 2
    assert response.generation.specialist.decision == "factual_question"
    assert response.verification.passed


# --- MedGemma adapter ------------------------------------------------------------------


def test_medgemma_reviews_the_verified_reading_of_a_flagged_result() -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[verdicts(("I1", "supported", None))],
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    info = response.generation.specialist
    assert info.consulted is True and info.decision == "consulted"
    assert info.model == SPECIALIST_MODEL
    assert [run.role for run in response.generation.model_runs] == ["primary", "specialist"]
    assert len(ollama.specialist_requests) == 1
    sent = ollama.specialist_requests[0]
    assert sent["options"]["temperature"] == 0.0
    assert sent["format"]["properties"]["opinions"]["items"]["properties"]["statement_id"][
        "enum"
    ] == ["I1"]
    # The specialist receives the verified reading and only the facts it cites.
    prompt = json.loads(sent["messages"][1]["content"])
    assert [item["id"] for item in prompt["readings"]] == ["I1"]
    assert {fact["id"] for fact in prompt["facts"]} == set(response.interpretations[0].fact_ids)
    assert any("not a validated clinical assessment" in u.text for u in response.uncertainties)
    assert response.verification.passed


def test_contradiction_is_resolved_conservatively() -> None:
    """MedGemma calls the reading unsupported: it is removed, never replaced."""
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[
            verdicts(("I1", "unsupported", "The cited facts do not show a trend this strong."))
        ],
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    assert response.interpretations == []
    finding = response.generation.specialist.findings[0]
    assert finding.verdict == "unsupported" and finding.applied == "interpretation removed"
    note = [u for u in response.uncertainties if u.text.startswith("Second-opinion model")]
    assert len(note) == 1 and note[0].origin == "model"
    # Backend facts and the rule-based status line are untouched by the specialist.
    assert response.status_summary.startswith("sleep")
    assert response.observations
    assert response.verification.passed


def test_medgemma_cannot_add_a_diagnosis_or_a_value() -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[
            verdicts(("I1", "overstated", "This looks like insomnia at 300 min; give melatonin."))
        ],
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    assert response.interpretations[0].confidence == "low"
    finding = response.generation.specialist.findings[0]
    assert finding.comment is None and "comment withheld by the verifier" in finding.applied
    sentences = [
        response.headline,
        *(item.text for item in response.observations),
        *(item.text for item in response.interpretations),
        *(item.text for item in response.uncertainties),
    ]
    for banned in ("insomnia", "melatonin", "300"):
        assert not any(banned in sentence.lower() for sentence in sentences), banned
    assert response.verification.passed


def test_medgemma_reply_with_unknown_ids_or_verdicts_is_ignored() -> None:
    reply = json.dumps(
        {
            "opinions": [
                {"statement_id": "I9", "verdict": "unsupported"},
                {"statement_id": "I1", "verdict": "diagnosis"},
                {"statement_id": "I1", "verdict": "supported"},
                {"statement_id": "I1", "verdict": "unsupported"},
            ]
        }
    )
    opinions = parse_review("<unused94>thinking...<unused95>" + reply, ["I1"])

    assert [(o.statement_id, o.verdict) for o in opinions] == [("I1", "supported")]
    assert strip_reasoning("<unused94>x<unused95> {}") == "{}"
    with pytest.raises(SpecialistError):
        parse_review("not json", ["I1"])
    schema = review_schema(["I1", "I2"])
    assert schema["properties"]["opinions"]["minItems"] == 2


def test_medgemma_prompt_contains_only_cited_facts_of_this_crew_member() -> None:
    sheet = fact_sheet(NOOR, "sleep")
    flagged = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    request = SpecialistRequest(
        crew_member_id=NOOR,
        question="Why?",
        facts=tuple(sheet.facts),
        interpretations=(_reading("screening_signal", [flagged]),),
    )
    prompt = json.loads(build_user_prompt(request))

    assert [fact["id"] for fact in prompt["facts"]] == [flagged]
    assert CHEN not in json.dumps(prompt)


@pytest.mark.parametrize("failure", ["not_installed", "timeout"])
def test_specialist_unavailable_or_timed_out_is_reported(failure: str) -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_error=failure == "timeout",
        models=[MODEL] + ([SPECIALIST_MODEL] if failure == "timeout" else []),
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    info = response.generation.specialist
    assert response.generation.mode == "generative"
    assert info.consulted is False
    assert info.decision == ("failed" if failure == "timeout" else "unavailable")
    assert "specialist review did not occur" in info.reason
    assert any("specialist review did not occur" in u.text for u in response.uncertainties)
    assert response.interpretations  # Qwen's verified reading is kept
    assert response.verification.passed


def test_qwen_unavailable_means_no_model_at_all() -> None:
    ollama = TwoModelOllama(reachable=False)
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    assert response.generation.mode == "deterministic_fallback"
    assert response.generation.fallback_reason == "ollama_unreachable"
    assert response.generation.specialist.decision == "non_generative"
    assert ollama.specialist_requests == []
    assert response.generation.model_runs == []
    assert response.verification.passed


def test_medgemma_adapter_is_registered_by_name() -> None:
    import orbit_agent.medgemma  # noqa: F401 - registration side effect

    adapter = create_specialist(Settings(specialist="medgemma"))
    assert adapter.name == "medgemma"
    assert adapter.model == "medgemma1.5:4b"


# --- NASA dataset evidence ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "domains", "topics"),
    [
        ("Why is Noor's sleep flagged?", ["sleep"], []),
        ("What does NASA bed rest research say about sleep?", ["sleep"], ["sleep"]),
        ("Is there NASA research data on heart rate in tilt tests?", [], ["heart_rate"]),
        ("What about blood pressure and orthostatic tolerance?", [], ["blood_pressure"]),
        ("actigraphy studies", ["sleep"], ["actigraphy"]),
    ],
)
def test_dataset_topics_follow_the_question(question, domains, topics) -> None:
    planned = plan_topics(question, domains)
    assert planned[: len(topics)] == topics if topics else planned == []


def test_nasa_dataset_evidence_with_unresolved_units() -> None:
    backend = BackendWithEvidence()
    question = "Is there NASA research data on heart rate in bed rest tilt tests?"
    response = make_agent(backend=backend).explain(
        ExplanationRequest(crew_member_id=NOOR, question=question, mode="deterministic")
    )

    section = response.dataset_evidence
    assert section.status == "ok" and section.topics[0] == "heart_rate"
    item = section.items[0]
    assert item.crew_telemetry is False and item.clinically_validated is False
    assert item.study_context == "terrestrial_bed_rest_analogue"
    assert item.variables[0].canonical_unit is None
    assert item.variables[0].unit_verification == "unresolved"
    texts = [u.text for u in response.uncertainties]
    assert any("terrestrial bed-rest studies of volunteers" in t for t in texts)
    assert any("unresolved units" in t for t in texts)
    # The dataset is never presented as crew data: no fact comes from it.
    assert all("/nasa-evidence" not in fact.source.path for fact in response.facts)
    assert any("/nasa-evidence?topic=heart_rate" in r.path for r in response.data_access.requests)
    assert response.verification.passed


@pytest.mark.parametrize(
    "payload",
    [
        adapter_payload(contains_synthetic_findings=True),
        adapter_payload(contract_version="2.0.0"),
        adapter_payload(item={"crew_telemetry": True}),
        adapter_payload(item={"nasa_source_url": "https://example.org/data"}),
        adapter_payload(
            item={
                "relevant_variables": [
                    {
                        "source_column": "HR",
                        "description": "Heart rate.",
                        "unit_verification": "unresolved",
                        "canonical_unit": "bpm",
                    }
                ]
            }
        ),
    ],
)
def test_unsafe_dataset_evidence_is_rejected_as_a_whole(payload: dict[str, Any]) -> None:
    backend = BackendWithEvidence(evidence=payload)
    response = make_agent(backend=backend).explain(
        ExplanationRequest(
            crew_member_id=NOOR, question="NASA research on heart rate?", mode="deterministic"
        )
    )

    assert response.dataset_evidence.status == "rejected"
    assert response.dataset_evidence.items == []
    assert response.verification.passed


def test_missing_dataset_endpoint_is_reported_not_invented() -> None:
    backend = BackendWithEvidence(evidence_status=404)
    response = make_agent(backend=backend).explain(
        ExplanationRequest(
            crew_member_id=NOOR, question="NASA research on heart rate?", mode="deterministic"
        )
    )

    assert response.dataset_evidence.status == "endpoint_unavailable"
    assert response.dataset_evidence.items == []
    assert response.verification.passed


def test_dataset_evidence_never_reaches_the_model() -> None:
    backend = BackendWithEvidence()
    ollama = FakeOllama(drafts=[noor_draft(fact_sheet(NOOR, "sleep"))])
    make_agent(backend=backend, ollama=ollama).explain(
        _noor("What does NASA bed rest research say about sleep?")
    )

    assert "nasa-lsda" not in ollama.prompt()
    assert "bed-rest campaign" not in ollama.prompt()


# --- Crew identity and missing data -----------------------------------------------------


def test_records_of_another_crew_member_are_refused() -> None:
    backend = BackendWithEvidence(foreign_crew=CHEN)

    with pytest.raises(BackendUnavailable, match="another crew member"):
        make_agent(backend=backend).explain(_noor(mode="deterministic"))


def test_crew_identity_is_consistent_across_the_response() -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[verdicts(("I1", "supported", None))],
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    check = next(c for c in response.verification.checks if c.name == "crew_identity")
    assert check.passed
    assert response.crew_member_id == NOOR
    assert all(NOOR in r.path for r in response.data_access.requests if "crew-members" in r.path)
    assert CHEN not in json.dumps(ollama.specialist_requests)


def test_crew_identity_audit_catches_a_foreign_identifier() -> None:
    from orbit_agent.verifier import audit_response

    response = make_agent().explain(_noor(mode="deterministic"))
    tampered = response.model_copy(deep=True)
    tampered.observations[0].text += f" See also {CHEN}."
    failed = {c.name for c in audit_response(tampered, EvidenceStore.load()) if not c.passed}

    assert "crew_identity" in failed


def test_crew_member_without_stored_data() -> None:
    response = make_agent().explain(
        ExplanationRequest(crew_member_id="sim-mission-v1-09", mode="deterministic")
    )

    assert response.facts
    assert response.data_provenance.crew_data_kind == "no_measurements"
    assert any("no stored evaluation" in u.text for u in response.uncertainties)
    assert response.interpretations == [] or all(
        i.kind != "screening_signal" for i in response.interpretations
    )
    assert response.verification.passed


def test_unsupported_clinical_question_gets_no_advice_and_no_specialist() -> None:
    ollama = TwoModelOllama(drafts=[noor_draft(fact_sheet(NOOR, "sleep"))])
    response = medgemma_agent(ollama).explain(_noor("Which medication and dose should Noor take?"))

    assert response.generation.question_kind == "clinical_advice"
    assert response.generation.specialist.decision == "clinical_advice_question"
    assert ollama.specialist_requests == []
    assert "not a diagnosis" in response.disclaimer
    assert response.verification.passed


def test_citation_verification_failure_is_never_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    """A citation that differs from the corpus fails the audit, also after a review.

    The generative answer (already reviewed by the specialist) is replaced by the
    rule-based one; if that one fails too, it is returned flagged, never as passed.
    """
    import orbit_agent.pipeline as pipeline

    original = pipeline.citation_from

    def tampered(item):  # an attacker-controlled or corrupted citation
        citation = original(item)
        citation.summary += " Crews need 9 hours of sleep."
        return citation

    monkeypatch.setattr(pipeline, "citation_from", tampered)
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[verdicts(("I1", "supported", None))],
    )
    response = medgemma_agent(ollama).explain(_noor("Why is Noor's sleep flagged?"))

    assert response.generation.mode == "deterministic_fallback"
    assert response.generation.fallback_reason == "final_audit_failed"
    assert response.verification.passed is False
    failed = {c.name for c in response.verification.checks if not c.passed}
    assert failed == {"citation_authenticity"}
    # The specialist did run on the first draft, and that is recorded, not hidden.
    assert [run.role for run in response.generation.model_runs] == ["primary", "specialist"]
