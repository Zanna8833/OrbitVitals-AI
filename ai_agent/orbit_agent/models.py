"""Request and response contract of the agent service.

The response is designed for a dashboard: every sentence is a separate item that names
the facts and the evidence it rests on, so the interface can link a sentence to the
backend value or to the NASA passage behind it.

Three kinds of content are kept apart and never mixed in one list:

- `observations`: what the backend returned for this crew member.
- `evidence_context`: general NASA evidence about spaceflight, not about this person.
- `interpretations`: cautious readings that connect the two, with stated confidence.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# 0.2.0: optional source fields on citations (articles), `dataset_evidence`, routing
# details in `generation` and the specialist's model and duration. All additions; no
# field of 0.1.0 was removed or renamed except `Citation.quote` (renamed `summary` in the
# publication-safe release, which kept 0.1.0). Still 0.2.0, not yet released: optional
# request fields `conversation` and `language`, and `generation.reply_language` and
# `generation.context_turns` (INTEGRATION.md, "Contract changes").
SCHEMA_VERSION = "0.2.0"

DISCLAIMER = (
    "Research prototype, not a medical device. This explanation supports a review by a "
    "person. It is not a diagnosis and it does not recommend any treatment."
)

Domain = Literal["vital_signs", "sleep", "physical_activity", "nutrition"]
Origin = Literal["model", "rule"]
FactKind = Literal[
    "provenance",
    "evaluation",
    "finding",
    "baseline",
    "measurement_series",
    "quality_overview",
    "measurement_quality_issue",
]
# What a fact can justify. Only `screening_signal` facts can support a statement about
# the crew member's physiology; `no_physiological_basis` facts explicitly cannot.
InterpretationRole = Literal[
    "screening_signal", "no_physiological_basis", "context", "data_quality"
]


class AgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ReplyLanguage = Literal["en", "it"]


class ConversationTurn(AgentModel):
    """One earlier message of the chat, as the dashboard showed it."""

    role: Literal["operator", "assistant"]
    text: str = Field(min_length=1, max_length=2000)
    crew_member_id: str | None = Field(
        default=None,
        max_length=128,
        description="Crew member the message was about. Turns about another one are not used.",
    )
    domain: Domain | None = None


class ExplanationRequest(AgentModel):
    crew_member_id: str = Field(min_length=1, max_length=128, description="Opaque crew ID.")
    domain: Domain | None = Field(
        default=None, description="Restrict the explanation to one health domain."
    )
    question: str | None = Field(
        default=None, max_length=500, description="Optional question from the operator."
    )
    mode: Literal["auto", "deterministic"] = Field(
        default="auto",
        description=(
            "`auto` uses the local model when it is available. `deterministic` never calls a model."
        ),
    )
    conversation: list[ConversationTurn] = Field(
        default_factory=list,
        max_length=40,
        description=(
            "Earlier messages of this chat, oldest first, kept by the client. The agent keeps "
            "no history of its own; it uses the most recent turns to understand follow-up "
            "questions. They are never used as facts."
        ),
    )
    language: ReplyLanguage | None = Field(
        default=None,
        description=(
            "Reply language. Omitted: English, or Italian when the operator writes in or asks "
            "for Italian."
        ),
    )


class FactSource(AgentModel):
    method: Literal["GET"] = "GET"
    path: str = Field(description="Backend path the fact was read from.")
    resource_id: str | None = Field(default=None, description="Identifier of the resource.")


class Fact(AgentModel):
    """One piece of information read from the backend, stated without interpretation."""

    id: str
    kind: FactKind
    domain: str | None = None
    metric: str | None = None
    statement: str
    data: dict[str, Any] = Field(description="Structured values behind the statement.")
    source: FactSource
    interpretation_role: InterpretationRole


class Citation(AgentModel):
    """A summary, written by the OrbitVitals team, of one paragraph of a published source.

    The source is a public NASA web page or an open-access peer-reviewed article. The
    summary is not the source's text and not a quotation. `publisher`, `document_title`,
    `section` and `url` identify the source; neither NASA nor the authors or publishers
    of the articles reviewed or endorsed the summary.
    """

    evidence_id: str
    source_type: Literal["nasa_web_page", "peer_reviewed_article"] = "nasa_web_page"
    publisher: str = Field(description="NASA for a NASA page; the journal for an article.")
    document_title: str
    section: str
    url: str = Field(description="The NASA page, or the DOI link of the article.")
    authors: str | None = Field(default=None, description="Article authors, abbreviated.")
    year: int | None = Field(default=None, description="Publication year of the article.")
    license: str | None = Field(
        default=None, description="Licence of the article as listed by Europe PMC."
    )
    verification_url: str | None = Field(
        default=None,
        description=(
            "Where the summarised paragraph can be fetched to check its digest, when "
            "that is not `url`."
        ),
    )
    summary: str = Field(description="Summary written by the OrbitVitals team; not source text.")
    text_kind: Literal["independent_summary"] = "independent_summary"
    sha256: str = Field(description="SHA-256 digest of `summary`, as stored in the corpus.")
    source_paragraph_sha256: str = Field(
        description=(
            "SHA-256 digest of the summarised paragraph on the source page (whitespace "
            "collapsed). The paragraph itself is not stored."
        )
    )
    source_checked_on: str = Field(
        description="Date the source paragraph was last confirmed on its page."
    )
    scope: Literal["general_evidence"] = "general_evidence"
    relevance_score: float


class Statement(AgentModel):
    id: str
    text: str
    origin: Origin = Field(description="`model`: drafted by the language model and verified.")
    fact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Interpretation(Statement):
    kind: Literal["screening_signal", "data_quality"]
    confidence: Literal["low", "moderate"]


class SuggestedCheck(AgentModel):
    id: str
    action_code: str
    text: str = Field(description="Fixed wording from the action catalogue.")
    rationale: str = Field(description="Fixed wording: why the rule selected this check.")
    fact_ids: list[str] = Field(description="Facts that triggered the check.")
    requires_human_review: bool


class HumanReview(AgentModel):
    recommended: bool
    reasons: list[str]
    fact_ids: list[str]


class ModelRun(AgentModel):
    role: Literal["primary", "specialist"]
    model: str
    attempt: int
    accepted: bool
    duration_ms: float
    load_ms: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prompt_eval_ms: float | None = None
    output_eval_ms: float | None = None
    rejected_sentences: int | None = Field(
        default=None, description="Sentences of this draft dropped by the verifier."
    )


class SpecialistFinding(AgentModel):
    statement_id: str
    verdict: Literal["supported", "overstated", "unsupported", "no_opinion"]
    comment: str | None = None
    applied: str = Field(description="What the agent did with this verdict.")


SpecialistDecision = Literal[
    "consulted",
    "not_configured",
    "non_generative",
    "conversational_question",
    "general_question",
    "factual_question",
    "clinical_advice_question",
    "no_physiological_reading",
    "no_flagged_result",
    "unavailable",
    "failed",
]


class SpecialistEvidenceRef(AgentModel):
    """A reviewed knowledge-base section given to the specialist as background."""

    evidence_id: str
    document_id: str
    document_title: str
    section: str
    sources: list[str]
    similarity: float
    knowledge_base: Literal["rag/knowledge_base"] = "rag/knowledge_base"


class SpecialistInfo(AgentModel):
    configured: str
    consulted: bool
    reason: str
    evidence_status: str = Field(
        default="not_used",
        description=(
            "Specialist background evidence: used, none_relevant, unavailable: <reason>, or "
            "not_used when the specialist was not consulted or has no retrieval."
        ),
    )
    evidence: list[SpecialistEvidenceRef] = Field(
        default_factory=list,
        description="Provenance of the background sections the specialist was given.",
    )
    decision: SpecialistDecision = Field(
        default="not_configured",
        description="Routing outcome, as a code. `consulted` means a model was really called.",
    )
    model: str | None = Field(default=None, description="Specialist model, when one was called.")
    duration_ms: float | None = None
    findings: list[SpecialistFinding] = Field(default_factory=list)
    notice: str = Field(
        default=(
            "A specialist verdict is a language model's opinion about the readings. It is not "
            "a validated clinical assessment."
        )
    )


class GenerationInfo(AgentModel):
    mode: Literal["generative", "deterministic_fallback"]
    generative: bool
    fallback_reason: str | None = None
    primary_model: str | None = None
    question_kind: Literal[
        "none", "greeting", "general", "factual", "interpretive", "clinical_advice"
    ] = Field(default="none", description="How the question was classified for routing.")
    answer_profile: Literal["conversation", "general", "brief", "full"] = Field(
        default="full",
        description=(
            "Size of the model draft: conversation (a short reply), general (an "
            "evidence-led answer), brief (stored values) or full (an explanation)."
        ),
    )
    reply_language: ReplyLanguage = Field(
        default="en", description="Language the model was asked to write in."
    )
    context_turns: int = Field(
        default=0,
        description=(
            "Earlier conversation turns sent by the client and given to the model as context. "
            "0 means the question was answered on its own."
        ),
    )
    attempts: int = 0
    model_runs: list[ModelRun] = Field(default_factory=list)
    specialist: SpecialistInfo
    timings_ms: dict[str, float] = Field(default_factory=dict)


class DatasetVariable(AgentModel):
    source_column: str
    description: str
    canonical_unit: str | None = Field(
        description="Null when the unit of the NASA export is unresolved. Never inferred."
    )
    unit_verification: Literal["reviewed_source_dictionary", "unresolved"]


class DatasetEvidenceItem(AgentModel):
    """Ground-analogue research context from the backend's NASA Dataset Evidence Adapter."""

    evidence_id: str
    dataset_id: str
    title: str
    nasa_source_url: str
    topic: str
    study_population: str
    study_context: Literal["terrestrial_bed_rest_analogue"]
    evidence_scope: Literal["scientific_context_only"]
    crew_telemetry: Literal[False]
    clinically_validated: Literal[False]
    nasa_endorsement: Literal[False]
    redistribution_status: Literal["unconfirmed"]
    source_verification: str = Field(
        description="`not_configured` means reviewed context only; files were not re-checked."
    )
    variables: list[DatasetVariable]
    context: list[str]
    limitations: list[str]


class DatasetEvidenceFailure(AgentModel):
    dataset_id: str
    code: str
    message: str


class DatasetEvidence(AgentModel):
    status: Literal[
        "not_requested",
        "disabled",
        "ok",
        "partial",
        "unavailable",
        "no_matching_evidence",
        "endpoint_unavailable",
        "rejected",
    ]
    topics: list[str] = Field(default_factory=list)
    reason: str
    items: list[DatasetEvidenceItem] = Field(default_factory=list)
    failures: list[DatasetEvidenceFailure] = Field(default_factory=list)
    notice: str = (
        "NASA dataset evidence describes terrestrial bed-rest studies of volunteers. It is "
        "research context only: not crew telemetry, not a reference range and not a "
        "clinical assessment. Structural counts from the adapter are not shown."
    )


class VerificationCheck(AgentModel):
    name: str
    passed: bool
    detail: str


class RejectedStatement(AgentModel):
    section: str
    text: str
    reasons: list[str]


class VerificationReport(AgentModel):
    passed: bool
    checks: list[VerificationCheck]
    rejected_statements: list[RejectedStatement] = Field(default_factory=list)


class DataProvenance(AgentModel):
    crew_data_kind: Literal["simulated", "mixed", "not_simulated", "no_measurements"]
    measurement_sources: dict[str, int]
    crew_data_notice: str
    evidence_notice: str


class BackendRequest(AgentModel):
    method: str
    path: str
    status: int
    item_count: int | None


class DataAccess(AgentModel):
    read_only: Literal[True] = True
    requests: list[BackendRequest]


class AgentResponse(AgentModel):
    schema_version: str = SCHEMA_VERSION
    generated_at: str
    crew_member_id: str
    domains: list[str]
    question: str | None
    status_summary: str = Field(
        description="Rule-based line with the latest stored status of each domain."
    )
    headline: str = Field(
        description="One-sentence answer. Written by the model when it passes verification."
    )
    headline_origin: Origin
    observations: list[Statement]
    evidence_context: list[Statement]
    interpretations: list[Interpretation]
    uncertainties: list[Statement]
    suggested_checks: list[SuggestedCheck]
    human_review: HumanReview
    facts: list[Fact]
    citations: list[Citation]
    dataset_evidence: DatasetEvidence
    data_provenance: DataProvenance
    data_access: DataAccess
    generation: GenerationInfo
    verification: VerificationReport
    disclaimer: str = DISCLAIMER
