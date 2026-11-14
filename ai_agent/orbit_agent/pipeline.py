"""Orchestration of one explanation request.

The control flow is fixed code, not a model deciding what to do next:

1. read the crew member's stored results from the backend (GET only);
2. turn them into a numbered fact sheet;
3. retrieve summaries of NASA web pages from the local corpus;
4. derive suggested checks and the human-review flag with fixed rules;
5. ask the local model for a draft, verify it sentence by sentence, retry once;
6. optionally ask a registered specialist to review physiological readings;
7. assemble the response and audit it as a whole.

If the model is unavailable, or nothing it wrote survives verification, step 5 is
replaced by rule-based sentences and the response says so in `generation`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from orbit_agent.backend_client import ReadOnlyBackendClient
from orbit_agent.composer import (
    SYSTEM_PROMPT,
    DraftParseError,
    build_user_prompt,
    draft_schema,
    parse_draft,
)
from orbit_agent.config import Settings
from orbit_agent.evidence.sanitizer import screen_text
from orbit_agent.evidence.store import EvidenceStore, ScoredPassage
from orbit_agent.facts import BackendSnapshot, FactSheet, build_fact_sheet
from orbit_agent.grounding import fact_dates, fact_numbers, ungrounded_values
from orbit_agent.http import Transport, urllib_transport
from orbit_agent.llm import ModelUnavailable, OllamaClient
from orbit_agent.models import (
    AgentResponse,
    BackendRequest,
    Citation,
    DataAccess,
    DataProvenance,
    ExplanationRequest,
    Fact,
    GenerationInfo,
    Interpretation,
    ModelRun,
    SpecialistFinding,
    SpecialistInfo,
    Statement,
    SuggestedCheck,
    VerificationCheck,
    VerificationReport,
)
from orbit_agent.rules import (
    CandidateAction,
    derive_actions,
    human_review,
    latest_evaluations,
    latest_findings,
    rule_evidence_context,
    rule_headline,
    rule_interpretations,
    rule_observations,
    rule_uncertainties,
)
from orbit_agent.specialist import (
    SpecialistAdapter,
    SpecialistError,
    SpecialistRequest,
    create_specialist,
    should_consult,
)
from orbit_agent.verifier import VerifiedDraft, audit_response, language_problems, verify_draft

# Topic tags of the evidence corpus that each health domain maps to.
_DOMAIN_TOPICS: dict[str, frozenset[str]] = {
    "sleep": frozenset({"sleep", "circadian", "fatigue", "workload"}),
    "physical_activity": frozenset({"exercise", "fitness", "countermeasure"}),
    "vital_signs": frozenset({"cardiovascular"}),
}
_QUALITY_TOPICS = frozenset({"monitoring", "autonomy"})
_BASELINE_TOPICS = frozenset({"baseline", "individual_variability"})
_FLAGGED = {"attention", "alert"}

_EVIDENCE_NOTICE = (
    "Citations are summaries, written by the OrbitVitals team, of paragraphs on public "
    "NASA web pages, with the source URL. They are not NASA text, and NASA did not review "
    "or endorse them. They give general context about spaceflight; they are not "
    "measurements of this crew member."
)
_PROVENANCE_NOTICES = {
    "simulated": "All crew measurements are simulated (source: simulated). No astronaut data.",
    "mixed": "Crew measurements mix simulated and non-simulated sources.",
    "not_simulated": "Crew measurements are not labelled as simulated.",
    "no_measurements": "No crew measurements were returned.",
}


@dataclass(frozen=True)
class RetrievalPlan:
    query: str
    focus_topics: frozenset[str]
    background_topics: frozenset[str]


def plan_retrieval(sheet: FactSheet, question: str | None) -> RetrievalPlan:
    """Choose what to look for in the corpus from what the backend reported."""
    findings = latest_findings(sheet)
    flagged_domains = {fact.domain for fact in findings if fact.data["status"] in _FLAGGED}
    quality_trouble = bool(sheet.of_kind("measurement_quality_issue")) or any(
        fact.data["status"] == "insufficient_data" for fact in latest_evaluations(sheet)
    )
    focus: set[str] = set()
    background: set[str] = set()
    for domain in sheet.domains:
        topics = _DOMAIN_TOPICS.get(domain, frozenset())
        if domain in flagged_domains or not (flagged_domains or quality_trouble):
            focus |= topics
        else:
            background |= topics
    if quality_trouble:
        (background if flagged_domains else focus).update(_QUALITY_TOPICS)
    if any(fact.data.get("baseline_id") for fact in findings):
        background |= _BASELINE_TOPICS
    # Query words come from what needs explaining: the flagged domains, or every domain
    # in scope when nothing is flagged and the data can be trusted.
    focus_domains = flagged_domains or (set() if quality_trouble else set(sheet.domains))
    terms = [question or "", *sorted(domain or "" for domain in focus_domains)]
    for fact in findings:
        if fact.domain in focus_domains:
            terms.append(fact.metric or "")
            details = fact.data.get("details_parsed_from_explanation") or {}
            terms.append(details.get("detected_pattern") or "")
    flags = {
        flag
        for fact in sheet.of_kind("measurement_quality_issue")
        for flag in (fact.data.get("data_quality") or {}).get("flags", [])
    }
    terms.extend(sorted(flags))
    query = " ".join(term.replace("_", " ") for term in terms if term)
    return RetrievalPlan(query, frozenset(focus), frozenset(background))


def prompt_facts(sheet: FactSheet, withheld: list[str]) -> list[Fact]:
    """Facts shown to the model: everything except superseded, unremarkable findings.

    A finding from an earlier evaluation window is kept only when it was flagged, so
    that the model can describe how a signal developed. The provenance fact is left
    out because the program states it in every explanation. The complete fact sheet is
    still returned to the caller.
    """
    latest = {fact.id for fact in latest_findings(sheet)}
    return [
        fact
        for fact in sheet.facts
        if fact.id not in withheld
        and fact.kind != "provenance"
        and (fact.kind != "finding" or fact.id in latest or fact.data["status"] in _FLAGGED)
    ]


def _tokens(text: str) -> set[str]:
    return {
        word for word in text.lower().replace(".", " ").replace(",", " ").split() if len(word) > 3
    }


def _repeats(text: str, others: list[str]) -> bool:
    """True when `text` mostly restates one of `others`.

    The 0.6 shared-word ratio is an engineering choice with no external source. It only
    hides a model sentence that duplicates a rule-based limit already shown.
    """
    words = _tokens(text)
    return any(words and len(words & _tokens(other)) / len(words) > 0.6 for other in others)


@dataclass
class _Generation:
    draft: VerifiedDraft | None = None
    fallback_reason: str | None = None
    attempts: int = 0
    runs: list[ModelRun] = field(default_factory=list)
    elapsed_ms: float = 0.0


@dataclass
class Agent:
    settings: Settings
    store: EvidenceStore
    backend_transport: Transport = urllib_transport
    model_transport: Transport = urllib_transport
    specialist: SpecialistAdapter | None = None
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def __post_init__(self) -> None:
        if self.specialist is None:
            self.specialist = create_specialist(self.settings)
        self._llm = OllamaClient(
            base_url=self.settings.ollama_base_url,
            transport=self.model_transport,
            timeout_seconds=self.settings.model_timeout_seconds,
        )

    def _backend(self) -> ReadOnlyBackendClient:
        return ReadOnlyBackendClient(
            base_url=self.settings.backend_base_url,
            transport=self.backend_transport,
            timeout_seconds=self.settings.backend_timeout_seconds,
        )

    def status(self) -> dict[str, Any]:
        """Report which dependencies are reachable. Never raises."""
        backend_ok = True
        try:
            self._backend().health()
        except Exception:  # noqa: BLE001 - a status probe reports, it does not fail
            backend_ok = False
        model_reason = None
        try:
            self._llm.require_model(self.settings.primary_model)
        except ModelUnavailable as error:
            model_reason = error.reason
        assert self.specialist is not None
        return {
            "backend": {"base_url": self.settings.backend_base_url, "reachable": backend_ok},
            "primary_model": {
                "name": self.settings.primary_model,
                "available": model_reason is None,
                "unavailable_reason": model_reason,
            },
            "specialist": {
                "configured": self.specialist.name,
                "available": self.specialist.is_available(),
            },
            "evidence_corpus": {
                "corpus_id": self.store.corpus_id,
                "passages": len(self.store.passages),
                "quarantined": sorted(self.store.quarantined),
            },
        }

    def explain(self, request: ExplanationRequest) -> AgentResponse:
        """Build one explanation. Raises `BackendUnavailable` if the data cannot be read."""
        started = time.perf_counter()
        timings: dict[str, float] = {}

        mark = time.perf_counter()
        backend = self._backend()
        snapshot = BackendSnapshot(
            crew_member_id=request.crew_member_id,
            metric_catalog=backend.metrics(),
            evaluations=backend.evaluations(request.crew_member_id, request.domain),
            baselines=backend.baselines(request.crew_member_id),
            measurements=backend.measurements(request.crew_member_id),
        )
        timings["backend_read_ms"] = _elapsed(mark)

        mark = time.perf_counter()
        sheet = build_fact_sheet(snapshot, request.domain)
        plan = plan_retrieval(sheet, request.question)
        passages = self.store.search(
            plan.query,
            focus_topics=plan.focus_topics,
            background_topics=plan.background_topics,
            top_k=self.settings.evidence_top_k,
        )
        actions = derive_actions(sheet)
        withheld = [fact.id for fact in sheet.facts if screen_text(fact.statement)]
        timings["facts_and_retrieval_ms"] = _elapsed(mark)

        generation = (
            _Generation(fallback_reason="deterministic_mode_requested")
            if request.mode == "deterministic"
            else self._generate(request, sheet, passages, actions, withheld)
        )
        timings["generation_ms"] = round(generation.elapsed_ms, 1)

        mark = time.perf_counter()
        response = self._assemble(
            request, sheet, passages, actions, backend, generation, timings, withheld
        )
        if not response.verification.passed and response.generation.generative:
            # Safety net: a generative response that fails its own audit is not returned.
            generation = _Generation(
                fallback_reason="final_audit_failed",
                attempts=generation.attempts,
                runs=generation.runs,
            )
            response = self._assemble(
                request, sheet, passages, actions, backend, generation, timings, withheld
            )
        timings["assembly_and_audit_ms"] = _elapsed(mark)
        timings["total_ms"] = _elapsed(started)
        response.generation.timings_ms = timings
        return response

    def _generate(
        self,
        request: ExplanationRequest,
        sheet: FactSheet,
        passages: list[ScoredPassage],
        actions: list[CandidateAction],
        withheld: list[str],
    ) -> _Generation:
        generation = _Generation()
        started = time.perf_counter()
        model = self.settings.primary_model
        facts = prompt_facts(sheet, withheld)
        stated_limits = [
            item.text for item in rule_uncertainties(sheet, has_evidence=bool(passages))
        ]
        schema = draft_schema(
            [fact.id for fact in facts], [item.passage.evidence_id for item in passages]
        )
        options = {
            "temperature": self.settings.model_temperature,
            "seed": self.settings.model_seed,
            "presence_penalty": self.settings.model_presence_penalty,
            "num_ctx": self.settings.model_context_tokens,
            "num_predict": self.settings.model_max_output_tokens,
        }
        best: VerifiedDraft | None = None
        feedback: list[str] | None = None
        failure = "draft_failed_verification"
        try:
            self._llm.require_model(model)
            for attempt in range(1, self.settings.max_generation_attempts + 1):
                generation.attempts = attempt
                result = self._llm.chat(
                    model=model,
                    system=SYSTEM_PROMPT,
                    user=build_user_prompt(
                        question=request.question,
                        domains=sheet.domains,
                        facts=facts,
                        passages=passages,
                        actions=actions,
                        stated_limits=stated_limits,
                        feedback=feedback,
                    ),
                    schema=schema,
                    options=options,
                    keep_alive=self.settings.model_keep_alive,
                    think=self.settings.model_think,
                )
                run = ModelRun(
                    role="primary",
                    model=model,
                    attempt=attempt,
                    accepted=False,
                    duration_ms=result.duration_ms,
                    load_ms=result.load_ms,
                    prompt_tokens=result.prompt_tokens,
                    output_tokens=result.output_tokens,
                    prompt_eval_ms=result.prompt_eval_ms,
                    output_eval_ms=result.output_eval_ms,
                )
                generation.runs.append(run)
                try:
                    draft = parse_draft(result.content)
                except DraftParseError:
                    failure = "model_output_not_parseable"
                    feedback = ["The previous output was not a complete JSON object."]
                    continue
                verified = verify_draft(draft, sheet, [item.passage for item in passages])
                run.rejected_sentences = len(verified.rejected)
                if best is None or _quality(verified) > _quality(best):
                    best = verified
                    for earlier in generation.runs:
                        earlier.accepted = False
                    run.accepted = True
                if verified.is_complete:
                    # Rejected sentences are dropped and reported. A second draft is
                    # requested only when too little of the first one survived.
                    break
                feedback = verified.feedback()
        except ModelUnavailable as error:
            failure = error.reason
            best = None
        generation.elapsed_ms = (time.perf_counter() - started) * 1000
        if best is not None and best.is_complete:
            generation.draft = best
        else:
            generation.fallback_reason = failure
            for run in generation.runs:
                run.accepted = False
        return generation

    def _assemble(
        self,
        request: ExplanationRequest,
        sheet: FactSheet,
        passages: list[ScoredPassage],
        actions: list[CandidateAction],
        backend: ReadOnlyBackendClient,
        generation: _Generation,
        timings: dict[str, float],
        withheld: list[str],
    ) -> AgentResponse:
        draft = generation.draft
        generative = draft is not None
        rule_evidence = rule_evidence_context(passages)

        status_summary = rule_headline(sheet)
        if draft is not None:
            # A model headline that failed verification is replaced by the rule-based one.
            headline = draft.headline or status_summary
            headline_origin = "model" if draft.headline else "rule"
            observations = draft.observations
            # Retrieved passages are always shown. When the model wrote no evidence
            # statement, the stored summaries are shown instead.
            evidence_context = draft.evidence_context or rule_evidence
            interpretations = draft.interpretations
            extra_uncertainties = draft.uncertainties
        else:
            headline, headline_origin = status_summary, "rule"
            observations = rule_observations(sheet)
            evidence_context = rule_evidence
            interpretations = rule_interpretations(sheet)
            extra_uncertainties = []

        specialist_info, interpretations, specialist_notes, specialist_ms = self._consult(
            request, sheet, interpretations, generative=generative
        )
        if specialist_ms is not None:
            timings["specialist_ms"] = specialist_ms

        stated = rule_uncertainties(sheet, has_evidence=bool(passages))
        stated_texts = [item.text for item in stated]
        uncertainties = [
            *stated,
            *(item for item in extra_uncertainties if not _repeats(item.text, stated_texts)),
            *specialist_notes,
        ]
        _number(observations, "O")
        _number(evidence_context, "E")
        _number(interpretations, "I")
        _number(uncertainties, "U")

        used_evidence = {
            evidence_id
            for item in [*evidence_context, *interpretations]
            for evidence_id in item.evidence_ids
        }
        citations = [
            Citation(
                evidence_id=item.passage.evidence_id,
                publisher=item.passage.publisher,
                document_title=item.passage.document_title,
                section=item.passage.section,
                url=item.passage.url,
                summary=item.passage.text,
                sha256=item.passage.sha256,
                source_paragraph_sha256=item.passage.source_paragraph_sha256,
                source_checked_on=item.passage.source_checked_on,
                relevance_score=item.score,
            )
            for item in passages
            if item.passage.evidence_id in used_evidence
        ]
        sources: dict[str, int] = sheet.of_kind("provenance")[0].data["sources"]
        kind = (
            "no_measurements"
            if not sources
            else "simulated"
            if set(sources) == {"simulated"}
            else "not_simulated"
            if "simulated" not in sources
            else "mixed"
        )
        response = AgentResponse(
            generated_at=self.clock().isoformat().replace("+00:00", "Z"),
            crew_member_id=request.crew_member_id,
            domains=sheet.domains,
            question=request.question,
            status_summary=status_summary,
            headline=headline,
            headline_origin=headline_origin,
            observations=observations,
            evidence_context=evidence_context,
            interpretations=interpretations,
            uncertainties=uncertainties,
            suggested_checks=[
                SuggestedCheck(
                    id=action.id,
                    action_code=action.code,
                    text=action.text,
                    rationale=action.rationale,
                    fact_ids=list(action.fact_ids),
                    requires_human_review=action.requires_human_review,
                )
                for action in actions
            ],
            human_review=human_review(sheet),
            facts=sheet.facts,
            citations=citations,
            data_provenance=DataProvenance(
                crew_data_kind=kind,
                measurement_sources=sources,
                crew_data_notice=_PROVENANCE_NOTICES[kind],
                evidence_notice=_EVIDENCE_NOTICE,
            ),
            data_access=DataAccess(
                requests=[
                    BackendRequest(
                        method=record.method,
                        path=record.path,
                        status=record.status,
                        item_count=record.item_count,
                    )
                    for record in backend.access_log
                ]
            ),
            generation=GenerationInfo(
                mode="generative" if generative else "deterministic_fallback",
                generative=generative,
                fallback_reason=generation.fallback_reason,
                primary_model=self.settings.primary_model if generative else None,
                attempts=generation.attempts,
                model_runs=generation.runs,
                specialist=specialist_info,
                timings_ms=timings,
            ),
            verification=VerificationReport(passed=False, checks=[]),
        )
        checks = audit_response(response, self.store)
        screened = [*sorted(self.store.quarantined), *withheld]
        checks.append(
            VerificationCheck(
                name="untrusted_text_screening",
                passed=not (set(self.store.quarantined) & used_evidence),
                detail=(
                    "No instruction-like text was found in retrieved passages or backend text."
                    if not screened
                    else "Withheld from the model as instruction-like: " + ", ".join(screened)
                ),
            )
        )
        response.verification = VerificationReport(
            passed=all(check.passed for check in checks),
            checks=checks,
            rejected_statements=draft.rejected if draft is not None else [],
        )
        return response

    def _consult(
        self,
        request: ExplanationRequest,
        sheet: FactSheet,
        interpretations: list[Interpretation],
        *,
        generative: bool,
    ) -> tuple[SpecialistInfo, list[Interpretation], list[Statement], float | None]:
        """Ask the registered specialist, if any, and apply its opinions conservatively."""
        assert self.specialist is not None
        name = self.specialist.name

        def skipped(reason: str) -> tuple[SpecialistInfo, list[Interpretation], list, None]:
            info = SpecialistInfo(configured=name, consulted=False, reason=reason)
            return info, interpretations, [], None

        if name == "none":
            return skipped("No specialist is configured.")
        if not generative:
            # The fallback is non-generative by contract: no model of any kind is called.
            return skipped("The response is non-generative, so no model was called.")
        wanted, reason = should_consult(interpretations)
        if not wanted:
            return skipped(reason)
        # Temporary identifiers so that opinions can refer to interpretations.
        _number(interpretations, "I")
        mark = time.perf_counter()
        try:
            if not self.specialist.is_available():
                raise SpecialistError("The specialist is not available.")
            report = self.specialist.review(
                SpecialistRequest(
                    crew_member_id=request.crew_member_id,
                    question=request.question,
                    facts=tuple(sheet.facts),
                    interpretations=tuple(interpretations),
                )
            )
        except Exception as error:  # noqa: BLE001 - a plug-in must never break the answer
            info = SpecialistInfo(
                configured=name,
                consulted=False,
                reason=f"The specialist could not be consulted: {type(error).__name__}.",
            )
            return info, interpretations, [], _elapsed(mark)
        by_id = {item.id: item for item in interpretations}
        findings: list[SpecialistFinding] = []
        notes: list[Statement] = []
        removed: set[str] = set()
        for opinion in report.opinions:
            target = by_id.get(opinion.statement_id)
            if target is None:
                continue
            if opinion.verdict == "unsupported":
                removed.add(target.id)
                applied = "interpretation removed"
            elif opinion.verdict == "overstated":
                target.confidence = "low"
                applied = "confidence set to low"
            else:
                applied = "no change"
            comment = (opinion.comment or "").strip() or None
            if comment and not _comment_is_safe(comment, target, sheet):
                comment = None
                applied += "; comment withheld by the verifier"
            elif comment and opinion.verdict in {"overstated", "unsupported"}:
                notes.append(
                    Statement(
                        id="",
                        text=f"Specialist review ({name}): {comment}",
                        origin="model",
                        fact_ids=target.fact_ids,
                    )
                )
            findings.append(
                SpecialistFinding(
                    statement_id=target.id,
                    verdict=opinion.verdict,
                    comment=comment,
                    applied=applied,
                )
            )
        kept = [item for item in interpretations if item.id not in removed]
        info = SpecialistInfo(configured=name, consulted=True, reason=reason, findings=findings)
        return info, kept, notes, _elapsed(mark)


def _comment_is_safe(comment: str, target: Interpretation, sheet: FactSheet) -> bool:
    """A specialist comment is shown only if it would pass as an agent sentence."""
    facts = [sheet.by_id()[fact_id] for fact_id in target.fact_ids if fact_id in sheet.by_id()]
    numbers = set().union(*(fact_numbers(fact) for fact in facts)) if facts else set()
    dates = set().union(*(fact_dates(fact) for fact in facts)) if facts else set()
    return (
        not ungrounded_values(comment, numbers, dates)
        and not language_problems(comment)
        and not screen_text(comment)
    )


def _quality(draft: VerifiedDraft) -> tuple[int, int]:
    """Order drafts: more accepted sentences first, then fewer rejections."""
    return (draft.accepted_count, -len(draft.rejected))


def _number(items: list[Any], prefix: str) -> None:
    for index, item in enumerate(items, start=1):
        item.id = f"{prefix}{index}"


def _elapsed(mark: float) -> float:
    return round((time.perf_counter() - mark) * 1000, 1)
