"""Deterministic guardrails applied to every sentence of an explanation.

Two entry points share the same checks:

- `verify_draft` filters a model draft sentence by sentence. A sentence that fails any
  check is dropped and reported; its text is never repaired or reworded.
- `audit_response` re-checks a finished response from the outside, including the
  rule-based sentences. Its result is published in `verification`.

What is checked:

1. Grounding: every number and date appears in the cited facts or passages, a status
   is named only when the cited facts have it, a headline names only a latest status,
   and a stated number of missing nights equals the number the backend reported.
2. References: cited facts and passages exist in this request. A link from a reading
   to a passage is removed when the sentence does not share wording with the passage.
3. Scope: observations cite only crew facts; evidence statements cite only passages.
4. Insufficient data: a reading of the crew member's physiology must cite a screening
   result; facts that carry no physiological basis cannot support one.
5. Language: no disease names, no diagnosis, no medication or treatment, no emergency
   wording, no unsupported claims about how the crew member feels.
6. Attribution: no sentence presents NASA as the speaker ("according to NASA"); the
   source of general evidence is disclosed in the citation, as a project summary.

These are lexical and structural checks. They do not understand meaning: a sentence can
pass all of them and still be a poor explanation. They exist to make the most harmful
failures (invented values, fabricated sources, medical advice) impossible to ship.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from orbit_agent.composer import Draft
from orbit_agent.evidence.sanitizer import screen_text
from orbit_agent.evidence.store import EvidenceStore, Passage, sha256_text, tokenize
from orbit_agent.facts import FactSheet
from orbit_agent.grounding import (
    dates_in,
    fact_dates,
    fact_numbers,
    numbers_in,
    passage_numbers,
    passage_source_text,
    ungrounded_values,
)
from orbit_agent.models import (
    AgentResponse,
    Fact,
    Interpretation,
    RejectedStatement,
    Statement,
    VerificationCheck,
)
from orbit_agent.rules import latest_evaluations, latest_findings

# Wording that is never acceptable in a sentence about the crew member.
_HARD_TERMS = re.compile(
    r"\b(prescri\w*|medication\w*|medicine\w*|drug\w*|dos(e|es|age|ing)\b|mg\b|pill\w*|"
    r"tablet\w*|melatonin|zolpidem|hypnotic\w*|sedative\w*|stimulant\w*|caffeine|"
    r"supplement\w*|administer\w*|emergenc\w*|urgent\w*|life-threatening|insomnia|"
    r"apnea|apnoea|narcolepsy|hypox\w*|arr?h?ythmi\w*|tachycardia|bradycardia|hypertension|"
    r"hypotension|depress\w*|anxiety|infection\w*|syndrome\w*)",
    re.IGNORECASE,
)
# Wording that is acceptable only when the sentence denies it ("this is not a diagnosis").
_SOFT_TERMS = re.compile(
    r"\b(diagnos\w*|disorder\w*|disease\w*|illness\w*|patholog\w*|medical condition\w*|"
    r"treat\w*|therap\w*|healthy|unhealthy|unwell|normal|abnormal\w*|all clear|clinical\w*|"
    r"validated|prove[sn]?|significance|(statistically|medically) significant|"
    r"significant(ly)? (\w+ )?(declin|reduc|decreas|drop|chang|deviat|increas|differ|trend|"
    r"worsen|improv|los[st])\w*|fatigue\w*|"
    r"tired\w*|exhaust\w*|stress\w*|burnout|impair\w*|sleep deprivation|sleep debt|"
    r"deconditioning)\b",
    re.IGNORECASE,
)
# Status names of the backend contract. A sentence may name a status only if a cited
# fact has it.
_EVALUATION_STATUS = {
    "nominal": re.compile(r"\bnominal\b", re.IGNORECASE),
    "attention": re.compile(r"\battention\b", re.IGNORECASE),
    "alert": re.compile(r"\balert\b", re.IGNORECASE),
    "insufficient_data": re.compile(r"\binsufficient[_ ]data\b", re.IGNORECASE),
}
# Other ways a sentence can acknowledge a status without naming it.
_STATUS_PARAPHRASE = {
    "nominal": re.compile(r"no configured (signal|trend|pattern)|did not trigger", re.I),
    "attention": re.compile(r"\bflag\w*|\breview\b", re.I),
    "alert": re.compile(r"\bflag\w*", re.I),
    "insufficient_data": re.compile(
        r"\binsufficient\b|not (be )?determined|undetermined|no (physiological )?status", re.I
    ),
}
_QUALITY_STATUS = re.compile(r"\b(degraded|unusable)\b", re.IGNORECASE)
# "<number> [up to two words] night(s)" in a sentence about missing records.
_NIGHT_COUNT = re.compile(
    r"\b(\d+|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen)\b"
    r"(?:\s+(?!of\b)[A-Za-z-]+){0,2}?\s+nights?\b",
    re.IGNORECASE,
)
_MISSING_CUE = re.compile(
    r"missing|no usable record|no record|not recorded|without a (usable )?record|\black\b",
    re.IGNORECASE,
)
_RUN_CUE = re.compile(r"\b(run|consecutive|in a row|streak)\b", re.IGNORECASE)
_OF_TOTAL = re.compile(r"\d\s+of\s*$", re.IGNORECASE)
# Claims of change over time. Not allowed in a reading that cites no screening result.
_TREND_TERMS = re.compile(
    r"\b(declin\w*|worsen\w*|deteriorat\w*|improv\w*|decreas\w*|increas\w*|reduc\w*)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(
    r"\b(not|no|never|without|cannot|neither|nor|rather than|instead of)\b|n't\b",
    re.IGNORECASE,
)
# How many characters before a term are searched for a negation. An engineering choice
# with no external source: long enough for "does not establish a cause or a ...", and
# limited to the current sentence by `_negated`.
_NEGATION_WINDOW = 90


def _negated(text: str, position: int) -> bool:
    """True when a negation precedes `position` within the same sentence."""
    window = text[max(0, position - _NEGATION_WINDOW) : position]
    sentence = re.split(r"[.;!?]\s", window)[-1]
    return bool(_NEGATION.search(sentence))


def language_problems(text: str, *, source_texts: tuple[str, ...] = ()) -> list[str]:
    """Return forbidden wording found in `text`.

    A term that is present in one of `source_texts` is accepted: a summary of a NASA
    passage may repeat the passage's own words.
    """
    sources = [source.lower() for source in source_texts]
    problems: list[str] = []

    def in_source(term: str) -> bool:
        # Compare word stems so that "diagnosing" matches a passage saying "diagnose".
        # Six letters is an engineering choice with no external source.
        stem = term[:6]
        return any(stem in source for source in sources)

    for match in _HARD_TERMS.finditer(text):
        term = match.group(0).lower()
        if not in_source(term):
            problems.append(f"forbidden medical wording: '{term}'")
    for match in _SOFT_TERMS.finditer(text):
        term = match.group(0).lower()
        if not in_source(term) and not _negated(text, match.start()):
            problems.append(f"unsupported claim wording: '{term}'")
    return list(dict.fromkeys(problems))


# Wording that presents NASA as the speaker of a statement. NASA's media usage guidelines
# (https://www.nasa.gov/nasa-brand-center/images-and-media/, section "Super Intelligence
# (SI) Applications", read 2026-11-15) ask that outputs of AI products be attributed to
# the product, not to NASA, and prohibit references such as "according to NASA". The
# source is disclosed in the citation instead. The verb list is an engineering choice.
_NASA_AS_SPEAKER = re.compile(
    r"\b(according to|per|as (stated|noted|reported|described) by|cited by)\s+(the\s+)?NASA\b"
    r"|\bNASA(['\N{RIGHT SINGLE QUOTATION MARK}]s)?(\s+[A-Za-z-]+){0,3}?\s+"
    r"(says|said|states|stated|notes|noted|"
    r"reports|reported|warns|warned|recommends|recommended|advises|advised|indicates|"
    r"indicated|explains|explained|describes|described|confirms|confirmed|suggests|"
    r"suggested|shows|showed|finds|found|concludes|concluded|highlights|highlighted|"
    r"emphasi[sz]es|stresses|acknowledges|identifies|identified|considers|believes|"
    r"points out)\b",
    re.IGNORECASE,
)


def attribution_problems(text: str) -> list[str]:
    """Return a problem when a sentence attributes information to NASA as its speaker."""
    match = _NASA_AS_SPEAKER.search(text)
    if match is None:
        return []
    return [f"source attribution: '{match.group(0)}' presents NASA as the speaker"]


def _shares_wording(text: str, passage: Passage) -> bool:
    """True when a sentence shares at least two content words with a passage.

    Used to drop evidence links that a model attaches to a reading without using the
    passage. Two words is an engineering choice with no external source; the sentence
    itself is kept either way.
    """
    words = {token for token in tokenize(text) if len(token) > 3}
    return len(words & set(tokenize(passage_source_text(passage)))) >= 2


def _trend_claims(text: str) -> list[str]:
    return list(
        dict.fromkeys(
            f"claim of change without a screening result: '{match.group(0).lower()}'"
            for match in _TREND_TERMS.finditer(text)
            if not _negated(text, match.start())
        )
    )


@dataclass
class _Context:
    facts: dict[str, Fact]
    passages: dict[str, Passage]
    crew_member_id: str
    _numbers: dict[str, set[float]] = field(default_factory=dict)

    def grounding_problems(
        self, text: str, fact_ids: list[str], evidence_ids: list[str], *, all_facts: bool = False
    ) -> list[str]:
        numbers: set[float] = set()
        dates: set[str] = set()
        facts = list(self.facts.values()) if all_facts else [self.facts[i] for i in fact_ids]
        for fact in facts:
            if fact.id not in self._numbers:
                self._numbers[fact.id] = fact_numbers(fact)
            numbers |= self._numbers[fact.id]
            dates |= fact_dates(fact)
        for evidence_id in evidence_ids:
            passage = self.passages[evidence_id]
            numbers |= passage_numbers(passage)
            dates |= dates_in(passage_source_text(passage))
        return [
            f"value not found in the cited sources: {value}"
            for value in ungrounded_values(text, numbers, dates)
        ]

    def reference_problems(self, fact_ids: list[str], evidence_ids: list[str]) -> list[str]:
        problems = [f"unknown fact {i}" for i in fact_ids if i not in self.facts]
        problems += [f"unknown evidence {i}" for i in evidence_ids if i not in self.passages]
        return problems

    def latest_statuses(self) -> set[str]:
        """Statuses of the most recent evaluation of each domain and of each metric."""
        sheet = FactSheet(crew_member_id="", domains=[], facts=list(self.facts.values()))
        return {
            fact.data["status"] for fact in [*latest_evaluations(sheet), *latest_findings(sheet)]
        }

    def headline_problems(self, text: str) -> list[str]:
        """A headline speaks for the whole answer, so it may only name current statuses."""
        problems = self.crew_statement(
            text, [], [], need_fact=False, ground_in_all_facts_if_uncited=True
        )
        latest = self.latest_statuses()
        problems += [
            f"status mismatch: '{name}' is not a latest stored status"
            for name, pattern in _EVALUATION_STATUS.items()
            if pattern.search(text) and name not in latest
        ]
        return list(dict.fromkeys(problems))

    def status_problems(self, text: str, fact_ids: list[str], *, all_facts: bool) -> list[str]:
        """A status named in a sentence must be the status of the facts it cites.

        Two errors are caught: naming a status that no cited fact has, and attributing
        one status to several cited results when some of them have another.
        """
        facts = list(self.facts.values()) if all_facts else [self.facts[i] for i in fact_ids]
        cited = {
            fact.data["status"]
            for fact in facts
            if fact.kind in {"evaluation", "finding"} and "status" in fact.data
        }
        for fact in facts:
            cited |= set((fact.data.get("status_per_metric") or {}).values())
            if fact.data.get("latest_finding_status"):
                cited.add(fact.data["latest_finding_status"])
        named = {name for name, pattern in _EVALUATION_STATUS.items() if pattern.search(text)}
        problems = [
            f"status mismatch: '{name}' is not the status of any cited fact"
            for name in sorted(named - cited)
        ]
        if named and not all_facts:
            # Only the cited results the sentence is about are compared: those of a
            # metric it names and of an evaluation window whose end date it gives.
            lowered = text.lower()
            results = [
                fact
                for fact in facts
                if fact.kind in {"evaluation", "finding"} and "status" in fact.data
            ]
            known_metrics = {fact.metric for fact in results if fact.metric}
            for fact in results:
                known_metrics |= set(fact.data.get("status_per_metric") or {})
            metrics = {
                metric
                for metric in known_metrics
                if metric in lowered or metric.replace("_", " ") in lowered
            }
            dates = dates_in(text)
            relevant: set[str] = set()
            for fact in results:
                if dates and fact.data["window_end"][:10] not in dates:
                    continue
                per_metric = fact.data.get("status_per_metric") or {}
                if fact.metric is None and metrics & set(per_metric):
                    # An evaluation cited for one metric: that metric's status counts.
                    relevant |= {per_metric[metric] for metric in metrics & set(per_metric)}
                elif fact.metric is None or not metrics or fact.metric in metrics:
                    relevant.add(fact.data["status"])
            problems += [
                f"status mismatch: a cited fact has status '{name}', which the sentence "
                "does not acknowledge"
                for name in sorted(relevant - named)
                if not _STATUS_PARAPHRASE[name].search(text)
            ]
        source = " ".join(fact.statement for fact in facts).lower()
        problems += [
            f"status mismatch: no cited fact reports '{word}' data quality"
            for word in sorted({match.lower() for match in _QUALITY_STATUS.findall(text)})
            if word not in source
        ]
        return problems

    def missing_night_problems(
        self, text: str, fact_ids: list[str], *, all_facts: bool
    ) -> list[str]:
        """A stated number of missing nights must be the number the backend reported.

        Number grounding alone accepts any value present in a cited fact, so "seven
        nights are missing" passed when seven was the longest run and eight nights were
        missing. This check compares the count with the list of missing nights, or with
        the longest run when the sentence speaks of a run.
        """
        facts = list(self.facts.values()) if all_facts else [self.facts[i] for i in fact_ids]
        counts: set[float] = set()
        runs: set[float] = set()
        for fact in facts:
            details = fact.data.get("details_parsed_from_explanation") or {}
            if "missing_nights" in details:
                counts.add(float(len(details["missing_nights"])))
            if "longest_missing_run" in details:
                runs.add(float(details["longest_missing_run"]))
            if "missing_nights_in_latest_finding" in fact.data:
                counts.add(float(len(fact.data["missing_nights_in_latest_finding"])))
        problems: list[str] = []
        for clause in re.split(r"(?<=[.;!?,])\s+", text):
            if not _MISSING_CUE.search(clause):
                continue
            for match in _NIGHT_COUNT.finditer(clause):
                value = numbers_in(match.group(1))
                # "7 of 9 nights" counts the nights of the window, not the missing ones.
                if not value or _OF_TOTAL.search(clause[: match.start()]):
                    continue
                context = clause[max(0, match.start() - 40) : match.end() + 25]
                expected = runs if _RUN_CUE.search(context) else counts
                if expected and value[0] not in expected:
                    problems.append(
                        f"count mismatch: {match.group(1)} missing nights stated, the cited "
                        f"facts report {', '.join(str(int(n)) for n in sorted(expected))}"
                    )
        return problems

    def crew_statement(
        self,
        text: str,
        fact_ids: list[str],
        evidence_ids: list[str],
        *,
        need_fact: bool,
        ground_in_all_facts_if_uncited: bool = False,
    ) -> list[str]:
        problems = self.reference_problems(fact_ids, evidence_ids)
        if problems:
            return problems
        if need_fact and not fact_ids:
            return ["no fact cited"]
        all_facts = ground_in_all_facts_if_uncited and not fact_ids
        problems += self.grounding_problems(text, fact_ids, evidence_ids, all_facts=all_facts)
        problems += self.status_problems(text, fact_ids, all_facts=all_facts)
        problems += self.missing_night_problems(text, fact_ids, all_facts=all_facts)
        problems += language_problems(text)
        problems += attribution_problems(text)
        if screen_text(text):
            problems.append("instruction-like wording")
        return problems

    def evidence_statement(
        self, text: str, fact_ids: list[str], evidence_ids: list[str]
    ) -> list[str]:
        problems = self.reference_problems(fact_ids, evidence_ids)
        if problems:
            return problems
        if not evidence_ids:
            return ["no passage cited"]
        if fact_ids:
            problems.append("general evidence must not cite crew facts")
        if self.crew_member_id.lower() in text.lower():
            problems.append("general evidence must not refer to the crew member")
        problems += self.grounding_problems(text, [], evidence_ids)
        sources = tuple(passage_source_text(self.passages[i]) for i in evidence_ids)
        problems += language_problems(text, source_texts=sources)
        problems += attribution_problems(text)
        return problems

    def interpretation(
        self, text: str, kind: str, fact_ids: list[str], evidence_ids: list[str]
    ) -> list[str]:
        problems = self.crew_statement(text, fact_ids, evidence_ids, need_fact=True)
        if problems and any(p.startswith(("unknown", "no fact")) for p in problems):
            return problems
        has_signal = any(self.facts[i].interpretation_role == "screening_signal" for i in fact_ids)
        if kind == "screening_signal" and not has_signal:
            problems.append(
                "a physiological reading must cite a screening result; the cited facts "
                "carry no physiological basis"
            )
        if not has_signal:
            problems += _trend_claims(text)
        return problems


@dataclass
class VerifiedDraft:
    headline: str | None = None
    observations: list[Statement] = field(default_factory=list)
    evidence_context: list[Statement] = field(default_factory=list)
    interpretations: list[Interpretation] = field(default_factory=list)
    uncertainties: list[Statement] = field(default_factory=list)
    rejected: list[RejectedStatement] = field(default_factory=list)

    @property
    def accepted_count(self) -> int:
        return (
            len(self.observations)
            + len(self.evidence_context)
            + len(self.interpretations)
            + len(self.uncertainties)
            + (1 if self.headline else 0)
        )

    @property
    def is_complete(self) -> bool:
        """Enough verified text to stand on its own, so no second draft is needed.

        The headline is not required: a rejected headline is replaced by the rule-based
        one without discarding the rest of the draft.
        """
        return len(self.observations) >= 2 and bool(self.interpretations)

    def feedback(self) -> list[str]:
        """Rejection reasons phrased for a second drafting attempt."""
        return [
            f'In {item.section}, the sentence "{item.text[:160]}" was rejected: '
            f"{'; '.join(item.reasons)}."
            for item in self.rejected[:8]
        ]


def verify_draft(draft: Draft, sheet: FactSheet, passages: list[Passage]) -> VerifiedDraft:
    """Keep the sentences of a model draft that pass every check; report the others."""
    context = _Context(
        facts=sheet.by_id(),
        passages={passage.evidence_id: passage for passage in passages},
        crew_member_id=sheet.crew_member_id,
    )
    result = VerifiedDraft()
    seen: set[str] = set()

    def accept(section: str, text: str, problems: list[str]) -> bool:
        text = text.strip()
        if text.lower() in seen:
            problems = [*problems, "duplicate sentence"]
        if problems:
            result.rejected.append(
                RejectedStatement(section=section, text=text, reasons=list(dict.fromkeys(problems)))
            )
            return False
        seen.add(text.lower())
        return True

    headline = draft.headline.strip()
    if accept("headline", headline, context.headline_problems(headline)):
        result.headline = headline

    for item in draft.observations:
        fact_ids = list(dict.fromkeys(item.fact_ids))
        problems = context.crew_statement(item.text, fact_ids, [], need_fact=True)
        if accept("observations", item.text, problems):
            result.observations.append(
                Statement(id="", text=item.text.strip(), origin="model", fact_ids=fact_ids)
            )

    for item in draft.evidence_context:
        evidence_ids = list(dict.fromkeys(item.evidence_ids))
        problems = context.evidence_statement(item.text, item.fact_ids, evidence_ids)
        if accept("evidence_context", item.text, problems):
            result.evidence_context.append(
                Statement(id="", text=item.text.strip(), origin="model", evidence_ids=evidence_ids)
            )

    for item in draft.interpretations:
        fact_ids = list(dict.fromkeys(item.fact_ids))
        evidence_ids = list(dict.fromkeys(item.evidence_ids))
        # The label follows the cited facts, not the model's choice: without a
        # screening result the sentence is checked, and shown, as a data-quality reading.
        has_signal = any(
            fact_id in context.facts
            and context.facts[fact_id].interpretation_role == "screening_signal"
            for fact_id in fact_ids
        )
        kind = item.kind if has_signal else "data_quality"
        # A link to a passage is kept only when the sentence actually draws on it.
        evidence_ids = [
            evidence_id
            for evidence_id in evidence_ids
            if evidence_id not in context.passages
            or _shares_wording(item.text, context.passages[evidence_id])
        ]
        problems = context.interpretation(item.text, kind, fact_ids, evidence_ids)
        if accept("interpretations", item.text, problems):
            result.interpretations.append(
                Interpretation(
                    id="",
                    text=item.text.strip(),
                    origin="model",
                    fact_ids=fact_ids,
                    evidence_ids=evidence_ids,
                    kind=kind,
                    confidence=item.confidence,
                )
            )

    for item in draft.uncertainties:
        fact_ids = list(dict.fromkeys(item.fact_ids))
        problems = context.crew_statement(
            item.text, fact_ids, [], need_fact=False, ground_in_all_facts_if_uncited=True
        )
        if accept("uncertainties", item.text, problems):
            result.uncertainties.append(
                Statement(id="", text=item.text.strip(), origin="model", fact_ids=fact_ids)
            )
    return result


def _check(name: str, problems: list[str], ok_detail: str) -> VerificationCheck:
    return VerificationCheck(
        name=name,
        passed=not problems,
        detail=ok_detail if not problems else "; ".join(problems[:6]),
    )


def audit_response(response: AgentResponse, store: EvidenceStore) -> list[VerificationCheck]:
    """Re-check a finished response against its own facts and the evidence corpus."""
    facts = {fact.id: fact for fact in response.facts}
    cited_passages = {
        citation.evidence_id: passage
        for citation in response.citations
        if (passage := store.get(citation.evidence_id)) is not None
    }
    context = _Context(facts=facts, passages=cited_passages, crew_member_id=response.crew_member_id)

    grounding: list[str] = []
    language: list[str] = []
    references: list[str] = []
    scope: list[str] = []
    insufficient: list[str] = []
    statuses: list[str] = []
    attribution: list[str] = []
    checked = 0

    def record(label: str, problems: list[str]) -> None:
        for problem in problems:
            target = (
                attribution
                if problem.startswith("source attribution")
                else references
                if problem.startswith(("unknown", "no fact", "no passage"))
                else grounding
                if problem.startswith("value not found")
                else statuses
                if problem.startswith("status mismatch")
                else scope
                if problem.startswith("general evidence")
                else insufficient
                if problem.startswith(("a physiological reading", "claim of change"))
                else language
            )
            target.append(f"{label}: {problem}")

    record("headline", context.headline_problems(response.headline))
    record(
        "status_summary",
        context.crew_statement(
            response.status_summary, [], [], need_fact=False, ground_in_all_facts_if_uncited=True
        ),
    )
    checked += 2
    for item in response.observations:
        checked += 1
        if item.evidence_ids:
            scope.append(f"{item.id}: an observation must not cite general evidence")
        record(item.id, context.crew_statement(item.text, item.fact_ids, [], need_fact=True))
    for item in response.evidence_context:
        checked += 1
        record(item.id, context.evidence_statement(item.text, item.fact_ids, item.evidence_ids))
    for item in response.interpretations:
        checked += 1
        record(
            item.id,
            context.interpretation(item.text, item.kind, item.fact_ids, item.evidence_ids),
        )
    for item in response.uncertainties:
        checked += 1
        record(
            item.id,
            context.crew_statement(
                item.text,
                item.fact_ids,
                [],
                need_fact=False,
                ground_in_all_facts_if_uncited=True,
            ),
        )
    for item in response.suggested_checks:
        checked += 1
        record(item.id, context.crew_statement(item.rationale, item.fact_ids, [], need_fact=False))
        record(item.id, language_problems(item.text))

    citation_problems: list[str] = []
    for citation in response.citations:
        passage = store.get(citation.evidence_id)
        if passage is None:
            citation_problems.append(f"{citation.evidence_id}: not in the evidence corpus")
        elif (
            citation.summary != passage.text
            or citation.sha256 != passage.sha256
            or sha256_text(citation.summary) != citation.sha256
            or citation.url != passage.url
            or citation.source_paragraph_sha256 != passage.source_paragraph_sha256
        ):
            citation_problems.append(f"{citation.evidence_id}: differs from the stored entry")
    cited = {citation.evidence_id for citation in response.citations}
    for item in [*response.evidence_context, *response.interpretations]:
        citation_problems += [
            f"{item.id}: cites {i}, which is not listed in citations"
            for i in item.evidence_ids
            if i not in cited
        ]

    uncertain_facts = {i for item in response.uncertainties for i in item.fact_ids}
    for fact in facts.values():
        if (
            fact.kind == "finding"
            and fact.data.get("status") == "insufficient_data"
            and fact.id not in uncertain_facts
            and _is_latest_finding(fact, facts)
        ):
            insufficient.append(f"{fact.id}: insufficient data is not stated as an uncertainty")

    sources = set(response.data_provenance.measurement_sources)
    expected_kind = (
        "no_measurements"
        if not sources
        else "simulated"
        if sources == {"simulated"}
        else "not_simulated"
        if "simulated" not in sources
        else "mixed"
    )
    provenance_problems = (
        []
        if response.data_provenance.crew_data_kind == expected_kind
        else [f"crew data is labelled {response.data_provenance.crew_data_kind}"]
    )
    write_requests = [
        f"{request.method} {request.path}"
        for request in response.data_access.requests
        if request.method != "GET"
    ]
    statements = [
        *response.observations,
        *response.evidence_context,
        *response.interpretations,
        *response.uncertainties,
    ]
    model_text = response.headline_origin == "model" or any(
        item.origin == "model" for item in statements
    )
    disclosure_problems = (
        ["model-written text is present in a response declared non-generative"]
        if model_text and not response.generation.generative
        else []
    )

    return [
        _check(
            "numeric_grounding",
            grounding,
            f"All numbers and dates in {checked} sentences appear in the cited sources.",
        ),
        _check(
            "status_consistency",
            statuses,
            "Every status named in a sentence is the status of the facts it cites.",
        ),
        _check("references", references, "Every cited fact and passage exists."),
        _check(
            "citation_authenticity",
            citation_problems,
            f"{len(response.citations)} citations match the stored corpus summary, digests "
            "and source URL.",
        ),
        _check(
            "source_attribution",
            attribution,
            "No sentence presents NASA as the speaker; sources are disclosed in citations.",
        ),
        _check(
            "evidence_scope_separation",
            scope,
            "Crew observations and general evidence are in separate lists.",
        ),
        _check(
            "insufficient_data_handling",
            insufficient,
            "No physiological reading rests on insufficient data.",
        ),
        _check("medical_language", language, "No diagnostic or treatment wording was found."),
        _check(
            "synthetic_data_labelling",
            provenance_problems,
            f"Crew data is labelled '{expected_kind}'.",
        ),
        _check("read_only_access", write_requests, "Only GET requests were sent to the backend."),
        _check(
            "generation_disclosure",
            disclosure_problems,
            f"Generation mode is declared as '{response.generation.mode}'.",
        ),
    ]


def _is_latest_finding(fact: Fact, facts: dict[str, Fact]) -> bool:
    sheet = FactSheet(crew_member_id="", domains=[], facts=list(facts.values()))
    return any(latest.id == fact.id for latest in latest_findings(sheet))
