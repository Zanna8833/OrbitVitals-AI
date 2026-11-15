"""Orchestration of one explanation request.

The control flow is fixed code, not a model deciding what to do next:

1. classify the question (`orbit_agent.routing`): brief or full draft;
2. read the crew member's stored results from the backend (GET only) and check that
   every record belongs to the requested crew member;
3. turn them into a numbered fact sheet;
4. retrieve summaries of published sources from the local corpus, and, when the question
   asks for it, NASA dataset context from the backend's evidence adapter;
5. derive suggested checks and the human-review flag with fixed rules;
6. ask the primary model (Qwen) for a draft, verify it sentence by sentence, retry once;
7. when routing says so, ask the specialist (MedGemma) to review the verified readings;
8. assemble the response and audit it as a whole.

If the primary model is unavailable, or nothing it wrote survives verification, step 6
is replaced by rule-based sentences, no model of any kind is called, and the response
says so in `generation`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from orbit_agent import nasa_datasets
from orbit_agent.backend_client import BackendUnavailable, ReadOnlyBackendClient
from orbit_agent.composer import (
    DraftParseError,
    build_user_prompt,
    draft_schema,
    parse_draft,
    system_prompt,
)
from orbit_agent.config import Settings
from orbit_agent.conversation import (
    Context,
    build_context,
    other_crew_pattern,
    parse_crew_aliases,
)
from orbit_agent.evidence.sanitizer import screen_text
from orbit_agent.evidence.store import EvidenceStore, ScoredPassage
from orbit_agent.facts import BackendSnapshot, FactSheet, build_fact_sheet
from orbit_agent.grounding import fact_dates, fact_numbers, ungrounded_values
from orbit_agent.http import Transport, urllib_transport
from orbit_agent.language import Language, reply_language
from orbit_agent.lexicon import italian_text
from orbit_agent.llm import ModelUnavailable, OllamaClient
from orbit_agent.models import (
    AgentResponse,
    BackendRequest,
    Citation,
    DataAccess,
    DataProvenance,
    DatasetEvidence,
    ExplanationRequest,
    Fact,
    GenerationInfo,
    HumanReview,
    Interpretation,
    ModelRun,
    SpecialistEvidenceRef,
    SpecialistFinding,
    SpecialistInfo,
    Statement,
    SuggestedCheck,
    VerificationCheck,
    VerificationReport,
)
from orbit_agent.routing import (
    AnswerProfile,
    QuestionKind,
    answer_profile,
    asks_about_the_dashboard,
    classify_question,
    conversation_intent,
    mentions_mission,
    refers_to_earlier_exchange,
    route_specialist,
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
)
from orbit_agent.verifier import (
    VerifiedDraft,
    agency_problems,
    attribution_problems,
    audit_response,
    language_problems,
    verify_draft,
)

# Topic tags of the evidence corpus that each health domain maps to. "countermeasure" is
# not a domain topic: it also tags lighting and other measures unrelated to exercise.
_DOMAIN_TOPICS: dict[str, frozenset[str]] = {
    "sleep": frozenset({"sleep", "circadian", "fatigue", "workload"}),
    "physical_activity": frozenset({"exercise", "fitness", "muscle"}),
    "vital_signs": frozenset({"cardiovascular"}),
}
_QUALITY_TOPICS = frozenset({"monitoring", "autonomy"})
_BASELINE_TOPICS = frozenset({"baseline", "individual_variability"})
_FLAGGED = {"attention", "alert"}

_EVIDENCE_NOTICE = (
    "Citations are summaries, written by the OrbitVitals team, of paragraphs on public "
    "NASA web pages and in open-access peer-reviewed articles, with the source URL or "
    "DOI. They are not the sources' text, and neither NASA nor the authors or publishers "
    "reviewed or endorsed them. They give general context about spaceflight; they are not "
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


def citation_from(item: ScoredPassage) -> Citation:
    """The citation shown for a retrieved corpus entry, copied field by field."""
    passage = item.passage
    return Citation(
        evidence_id=passage.evidence_id,
        source_type=passage.source_type,
        publisher=passage.publisher,
        document_title=passage.document_title,
        section=passage.section,
        url=passage.url,
        authors=passage.authors,
        year=passage.year,
        license=passage.license,
        verification_url=passage.verification_url,
        summary=passage.text,
        sha256=passage.sha256,
        source_paragraph_sha256=passage.source_paragraph_sha256,
        source_checked_on=passage.source_checked_on,
        relevance_score=item.score,
    )


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
    question_kind: QuestionKind = "none"
    profile: AnswerProfile = "full"
    language: Language = "en"
    context: Context = field(default_factory=lambda: Context((), None, False))


def foreign_crew_ids(snapshot: BackendSnapshot) -> list[str]:
    """Crew identifiers in the returned records that are not the requested one."""
    found = {
        item.get("crew_member_id")
        for group in (snapshot.evaluations, snapshot.baselines, snapshot.measurements)
        for item in group
        if isinstance(item, dict) and item.get("crew_member_id") is not None
    }
    return sorted(str(value) for value in found if value != snapshot.crew_member_id)


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

    def warm_up(self) -> dict[str, Any]:
        """Load the primary model and the specialist's retrieval index now. Never raises.

        The specialist model itself is not loaded in advance: when GPU memory is short,
        loading it would push the primary model out.
        """
        result: dict[str, Any] = {"model": self.settings.primary_model}
        try:
            load_ms = self._llm.warm_up(self.settings.primary_model, self.settings.model_keep_alive)
            result.update(loaded=True, load_ms=load_ms)
        except ModelUnavailable as error:
            result.update(loaded=False, reason=error.reason)
        specialist_warm_up = getattr(self.specialist, "warm_up", None)
        if callable(specialist_warm_up):
            result["specialist"] = specialist_warm_up()
        return result

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
        specialist = {
            "configured": self.specialist.name,
            "available": self.specialist.is_available(),
        }
        if getattr(self.specialist, "model", None):
            specialist["model"] = self.specialist.model
        return {
            "backend": {"base_url": self.settings.backend_base_url, "reachable": backend_ok},
            "primary_model": {
                "name": self.settings.primary_model,
                "available": model_reason is None,
                "unavailable_reason": model_reason,
            },
            "specialist": specialist,
            "nasa_dataset_evidence": {"enabled": self.settings.nasa_dataset_evidence},
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
        # Earlier turns sent by the client. A follow-up without a subject of its own is
        # routed together with the question it continues; the reply still answers the
        # current message.
        context = build_context(
            request,
            self.settings.conversation_max_turns,
            parse_crew_aliases(self.settings.crew_aliases),
        )
        routed = context.routed
        kind = classify_question(routed)
        profile = answer_profile(kind)
        language = reply_language(
            request.question,
            [turn.text for turn in context.turns if turn.role == "operator"],
            request.language,
            detect=self.settings.reply_language_detection,
        )

        mark = time.perf_counter()
        backend = self._backend()
        snapshot = BackendSnapshot(
            crew_member_id=request.crew_member_id,
            metric_catalog=backend.metrics(),
            evaluations=backend.evaluations(request.crew_member_id, request.domain),
            baselines=backend.baselines(request.crew_member_id),
            measurements=backend.measurements(request.crew_member_id),
        )
        foreign = foreign_crew_ids(snapshot)
        if foreign:
            # Never explain one crew member with another one's records.
            raise BackendUnavailable(
                f"The backend returned records of another crew member ({', '.join(foreign)})"
            )
        timings["backend_read_ms"] = _elapsed(mark)

        mark = time.perf_counter()
        sheet = build_fact_sheet(snapshot, request.domain)
        # A general question is not about this crew member's results, so the question
        # alone chooses the evidence; the flagged domains would crowd out its subject.
        plan = (
            RetrievalPlan(routed or "", frozenset(), frozenset())
            if kind == "general"
            else plan_retrieval(sheet, routed)
        )
        # A greeting needs no evidence; retrieving some would only lengthen the answer. A
        # question about the dashboard is answered from the statuses, not the literature.
        passages = (
            []
            if kind == "greeting" or (kind == "general" and asks_about_the_dashboard(routed))
            else self.store.search(
                plan.query,
                focus_topics=plan.focus_topics,
                background_topics=plan.background_topics,
                top_k=self.settings.evidence_top_k,
            )
        )
        actions = derive_actions(sheet)
        withheld = [fact.id for fact in sheet.facts if screen_text(fact.statement)]
        timings["facts_and_retrieval_ms"] = _elapsed(mark)

        mark = time.perf_counter()
        dataset = nasa_datasets.retrieve(
            backend,
            routed,
            sheet.domains,
            enabled=self.settings.nasa_dataset_evidence,
        )
        timings["dataset_evidence_ms"] = _elapsed(mark)

        generation = (
            _Generation(fallback_reason="deterministic_mode_requested")
            if request.mode == "deterministic"
            else self._generate(
                request, sheet, passages, actions, withheld, profile, language, context
            )
        )
        generation.question_kind, generation.profile = kind, profile
        generation.language, generation.context = language, context
        timings["generation_ms"] = round(generation.elapsed_ms, 1)

        mark = time.perf_counter()
        response = self._assemble(
            request, sheet, passages, actions, backend, generation, timings, withheld, dataset
        )
        if not response.verification.passed and response.generation.generative:
            # Safety net: a generative response that fails its own audit is not returned.
            generation = _Generation(
                fallback_reason="final_audit_failed",
                attempts=generation.attempts,
                runs=generation.runs,
                question_kind=kind,
                profile=profile,
                language=language,
                context=context,
            )
            response = self._assemble(
                request, sheet, passages, actions, backend, generation, timings, withheld, dataset
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
        profile: AnswerProfile = "full",
        language: Language = "en",
        context: Context | None = None,
    ) -> _Generation:
        generation = _Generation()
        started = time.perf_counter()
        model = self.settings.primary_model
        context = context or Context((), None, False)
        history = [{"role": turn.role, "text": turn.text} for turn in context.turns]
        # A conversational reply describes no result, so Qwen gets no crew facts, checks or
        # limits to talk about; the verifier still checks the reply against all facts.
        conversation = profile == "conversation"
        facts = [] if conversation else prompt_facts(sheet, withheld)
        stated_limits = (
            []
            if conversation
            else [
                item.text
                for item in rule_uncertainties(
                    sheet,
                    has_evidence=bool(passages),
                    cited_topics=frozenset(t for item in passages for t in item.passage.topics),
                )
            ]
        )
        schema = draft_schema(
            [fact.id for fact in facts], [item.passage.evidence_id for item in passages], profile
        )
        options = {
            "temperature": self.settings.model_temperature,
            "seed": self.settings.model_seed,
            "presence_penalty": self.settings.model_presence_penalty,
            "num_ctx": self.settings.model_context_tokens,
            "num_predict": {
                "conversation": self.settings.conversation_max_output_tokens,
                "general": self.settings.general_max_output_tokens,
                "brief": self.settings.brief_max_output_tokens,
            }.get(profile, self.settings.model_max_output_tokens),
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
                    system=system_prompt(language),
                    user=build_user_prompt(
                        question=request.question,
                        domains=sheet.domains,
                        facts=facts,
                        passages=passages,
                        actions=[] if conversation else actions,
                        stated_limits=stated_limits,
                        feedback=feedback,
                        profile=profile,
                        language=language,
                        intent=conversation_intent(context.routed or request.question),
                        conversation=history,
                        question_in_context=context.question_in_context,
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
                verified = verify_draft(
                    draft,
                    sheet,
                    [item.passage for item in passages],
                    history=context.has_history,
                )
                run.rejected_sentences = len(verified.rejected)
                if best is None or _quality(verified) > _quality(best):
                    best = verified
                    for earlier in generation.runs:
                        earlier.accepted = False
                    run.accepted = True
                if verified.complete_for(profile):
                    # Rejected sentences are dropped and reported. A second draft is
                    # requested only when too little of the first one survived.
                    break
                feedback = verified.feedback()
        except ModelUnavailable as error:
            failure = error.reason
            best = None
        generation.elapsed_ms = (time.perf_counter() - started) * 1000
        if best is not None and best.complete_for(profile):
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
        dataset: DatasetEvidence | None = None,
    ) -> AgentResponse:
        dataset = dataset or DatasetEvidence(
            status="not_requested", reason="The question does not ask for NASA dataset context."
        )
        draft = generation.draft
        generative = draft is not None
        rule_evidence = rule_evidence_context(passages)

        status_summary = rule_headline(sheet)
        conversation = generation.profile == "conversation"
        if conversation:
            # A conversational reply describes no result: no report sections. Without a
            # verified model reply, a fixed greeting is returned instead of a status report.
            replied = draft is not None and draft.headline is not None
            headline = draft.headline if replied else _fixed_greeting(generation.language)
            headline_origin = "model" if replied else "rule"
            observations, evidence_context, interpretations = [], [], []
            extra_uncertainties = []
        elif draft is not None:
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

        specialist_info, interpretations, specialist_notes, specialist_run = self._consult(
            request,
            sheet,
            interpretations,
            generative=generative,
            kind=generation.question_kind,
            question=generation.context.question_in_context or request.question,
        )
        if specialist_info.duration_ms is not None:
            timings["specialist_ms"] = specialist_info.duration_ms
        if specialist_run is not None:
            generation.runs.append(specialist_run)

        used_evidence = {
            evidence_id
            for item in [*evidence_context, *interpretations]
            for evidence_id in item.evidence_ids
        }
        cited = [item for item in passages if item.passage.evidence_id in used_evidence]
        stated = (
            []
            if conversation
            else rule_uncertainties(
                sheet,
                has_evidence=bool(passages),
                cited_topics=frozenset(topic for item in cited for topic in item.passage.topics),
            )
            + _integration_limits(specialist_info, dataset)
        )
        stated += _conversation_limits(
            request.question, generation.language, history=generation.context.has_history
        )
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

        citations = [citation_from(item) for item in cited]
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
                for action in ([] if conversation else actions)
            ],
            # The review recommendation belongs to answers that present results.
            human_review=(
                HumanReview(recommended=False, reasons=[], fact_ids=[])
                if conversation
                else human_review(sheet)
            ),
            facts=sheet.facts,
            citations=citations,
            dataset_evidence=dataset,
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
                question_kind=generation.question_kind,
                answer_profile=generation.profile,
                reply_language=generation.language,
                context_turns=len(generation.context.turns),
                attempts=generation.attempts,
                model_runs=generation.runs,
                specialist=specialist_info,
                timings_ms=timings,
            ),
            verification=VerificationReport(passed=False, checks=[]),
        )
        checks = audit_response(
            response,
            self.store,
            other_crew_pattern(
                parse_crew_aliases(self.settings.crew_aliases), request.crew_member_id
            ),
        )
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
        kind: QuestionKind = "none",
        question: str | None = None,
    ) -> tuple[SpecialistInfo, list[Interpretation], list[Statement], ModelRun | None]:
        """Route to the registered specialist and apply its opinions conservatively.

        The specialist sees only verified readings and the facts they cite; it can remove
        a reading or lower its confidence, never add one. Its comments pass the same
        checks as the primary model's sentences, and the whole response is audited after.
        """
        assert self.specialist is not None
        name = self.specialist.name

        def skipped(
            decision: str, reason: str, duration: float | None = None
        ) -> tuple[SpecialistInfo, list[Interpretation], list, None]:
            info = SpecialistInfo(
                configured=name,
                consulted=False,
                decision=decision,
                reason=reason,
                duration_ms=duration,
            )
            return info, interpretations, [], None

        if name == "none":
            return skipped("not_configured", "No specialist is configured.")
        if not generative:
            # The fallback is non-generative by contract: no model of any kind is called.
            return skipped(
                "non_generative", "The response is non-generative, so no model was called."
            )
        route = route_specialist(kind, interpretations, sheet.by_id())
        if not route.consult:
            return skipped(route.decision, route.reason)
        # Temporary identifiers so that opinions can refer to interpretations.
        _number(interpretations, "I")
        mark = time.perf_counter()
        try:
            if not self.specialist.is_available():
                return skipped(
                    "unavailable",
                    "The specialist was selected but is not available; specialist review did "
                    "not occur.",
                    _elapsed(mark),
                )
            report = self.specialist.review(
                SpecialistRequest(
                    crew_member_id=request.crew_member_id,
                    # A follow-up is reviewed with the question it continues.
                    question=question or request.question,
                    facts=tuple(sheet.facts),
                    interpretations=tuple(interpretations),
                )
            )
        except Exception as error:  # noqa: BLE001 - a plug-in must never break the answer
            detail = str(error)[:160] if isinstance(error, SpecialistError) else ""
            return skipped(
                "failed",
                "The specialist could not be consulted; specialist review did not occur: "
                f"{type(error).__name__}{': ' + detail if detail else ''}.",
                _elapsed(mark),
            )
        duration = _elapsed(mark)
        raw = report.raw if isinstance(report.raw, dict) else {}
        run = ModelRun(
            role="specialist",
            model=report.model or name,
            attempt=1,
            accepted=True,
            duration_ms=report.duration_ms if report.duration_ms is not None else duration,
            load_ms=raw.get("load_ms"),
            prompt_tokens=raw.get("prompt_tokens"),
            output_tokens=raw.get("output_tokens"),
        )
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
                        text=f"Second-opinion model ({name}): {comment}",
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
        info = SpecialistInfo(
            configured=name,
            consulted=True,
            decision="consulted",
            reason=route.reason,
            model=report.model,
            duration_ms=duration,
            findings=findings,
            evidence_status=report.evidence_status or "not_used",
            evidence=[SpecialistEvidenceRef(**item) for item in report.evidence],
        )
        return info, kept, notes, run


_FIXED_TEXTS: dict[str, dict[str, str]] = {
    "greeting": {
        "en": (
            "Hello! I am the OrbitVitals assistant: I explain the stored monitoring results of "
            "the selected crew member, with research context. What would you like to know?"
        ),
    },
    "memory_limit": {
        "en": (
            "The assistant keeps no memory of earlier questions. This reply is based on the "
            "current question and the stored records alone."
        ),
    },
    "mission_limit": {
        "en": (
            "The assistant has no information about the mission beyond the stored records of "
            "the selected crew member."
        ),
    },
}


def _fixed_text(key: str, language: Language) -> str:
    """A fixed sentence in the operator's language (English, or Italian from the lexicon)."""
    return italian_text(key) if language == "it" else _FIXED_TEXTS[key]["en"]


def _fixed_greeting(language: Language) -> str:
    return _fixed_text("greeting", language)


def _conversation_limits(
    question: str | None, language: Language = "en", *, history: bool = False
) -> list[Statement]:
    """Fixed statements about what the assistant cannot know, when a question asks for it.

    With earlier turns sent by the client, a reference to them is answered from them, so
    the statement that no earlier message is kept would be wrong and is not added.
    """
    limits: list[Statement] = []
    if refers_to_earlier_exchange(question) and not history:
        limits.append(Statement(id="", text=_fixed_text("memory_limit", language), origin="rule"))
    if mentions_mission(question):
        limits.append(Statement(id="", text=_fixed_text("mission_limit", language), origin="rule"))
    return limits


def _integration_limits(specialist: SpecialistInfo, dataset: DatasetEvidence) -> list[Statement]:
    """Fixed statements about the second model and the NASA dataset context."""
    limits: list[Statement] = []
    if specialist.consulted:
        limits.append(
            Statement(
                id="",
                text=(
                    f"A second model ({specialist.configured}) reviewed the readings. Its "
                    "verdicts are a model's opinion, not a validated clinical assessment."
                ),
                origin="rule",
            )
        )
    elif specialist.decision in {"unavailable", "failed"}:
        limits.append(
            Statement(
                id="",
                text=(
                    "The second-opinion model was selected for this explanation but could not "
                    "be consulted, so specialist review did not occur."
                ),
                origin="rule",
            )
        )
    if dataset.items:
        limits.append(
            Statement(
                id="",
                text=(
                    "The research datasets listed in this answer come from terrestrial "
                    "bed-rest studies of volunteers, not from this crew member, and provide no "
                    "reference values for this crew member."
                ),
                origin="rule",
            )
        )
        if any(
            variable.unit_verification == "unresolved"
            for item in dataset.items
            for variable in item.variables
        ):
            limits.append(
                Statement(
                    id="",
                    text=(
                        "Some variables of those datasets have unresolved units, so none of "
                        "their values can be compared with anything."
                    ),
                    origin="rule",
                )
            )
    return limits


def _comment_is_safe(comment: str, target: Interpretation, sheet: FactSheet) -> bool:
    """A specialist comment is shown only if it would pass as an agent sentence."""
    facts = [sheet.by_id()[fact_id] for fact_id in target.fact_ids if fact_id in sheet.by_id()]
    numbers = set().union(*(fact_numbers(fact) for fact in facts)) if facts else set()
    dates = set().union(*(fact_dates(fact) for fact in facts)) if facts else set()
    return (
        not ungrounded_values(comment, numbers, dates)
        and not language_problems(comment)
        and not attribution_problems(comment)
        and not agency_problems(comment, [])
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
