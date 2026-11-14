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

SCHEMA_VERSION = "0.1.0"

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
    """A summary, written by the OrbitVitals team, of a paragraph on a public NASA page.

    The summary is not NASA text and not a quotation. `publisher`, `document_title`,
    `section` and `url` identify the source; NASA did not review or endorse the summary.
    """

    evidence_id: str
    publisher: str = Field(description="Publisher of the source page.")
    document_title: str
    section: str
    url: str
    summary: str = Field(description="Summary written by the OrbitVitals team; not NASA text.")
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


class SpecialistInfo(AgentModel):
    configured: str
    consulted: bool
    reason: str
    findings: list[SpecialistFinding] = Field(default_factory=list)


class GenerationInfo(AgentModel):
    mode: Literal["generative", "deterministic_fallback"]
    generative: bool
    fallback_reason: str | None = None
    primary_model: str | None = None
    attempts: int = 0
    model_runs: list[ModelRun] = Field(default_factory=list)
    specialist: SpecialistInfo
    timings_ms: dict[str, float] = Field(default_factory=dict)


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
    data_provenance: DataProvenance
    data_access: DataAccess
    generation: GenerationInfo
    verification: VerificationReport
    disclaimer: str = DISCLAIMER
