"""Local evidence corpus: integrity checks and deterministic retrieval.

The corpus holds short factual summaries, written by the OrbitVitals team, of
paragraphs on public NASA web pages. It stores no NASA text: each entry records the
source URL, title and section, and the SHA-256 digest of the summarised paragraph, so
`scripts/verify_sources.py` can confirm that the paragraph is still published without
the repository redistributing it. A citation returned by the agent is always one of
these stored summaries, attached by the program and never written by a language model.

Retrieval is lexical (Okapi BM25) with a bonus for curated topic tags. It is
deterministic, needs no embedding model and is easy to audit, which suits a corpus of a
few dozen passages. It does not understand paraphrase; see the README for limits.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from orbit_agent.evidence.sanitizer import screen_text

DEFAULT_CORPUS_PATH = Path(__file__).parent / "corpus" / "nasa_summaries.json"
# The only kind of text the corpus may contain: a summary written by the project team.
SUMMARY_KIND = "independent_summary"
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# Okapi BM25 parameters. Manning, Raghavan and Schuetze, "Introduction to Information
# Retrieval" (Cambridge University Press, 2008), section 11.4.3, report k1 between 1.2
# and 2 and b = 0.75 as reasonable values. Not tuned on this corpus.
_BM25_K1 = 1.5
_BM25_B = 0.75
# Bonus per matching focus tag, and a single bonus for any background tag. Engineering
# choices with no external source: tags are curated by hand, so a focus-tag match is
# weighted like a strong term match. They affect only which passages are shown, never a
# health result.
_FOCUS_TOPIC_BONUS = 2.0
_BACKGROUND_TOPIC_BONUS = 0.75

_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "been", "by", "can", "could", "for", "from"}
    | {"has", "have", "how", "in", "into", "is", "it", "its", "may", "more", "most", "of"}
    | {"on", "or", "such", "than", "that", "the", "their", "them", "these", "they", "this"}
    | {"to", "was", "were", "what", "when", "which", "while", "who", "will", "with", "also"}
    | {"about", "during", "other", "would", "should"}
)
_TOKEN = re.compile(r"[a-z0-9]+")


class CorpusIntegrityError(Exception):
    """The corpus file is malformed or a passage does not match its recorded digest."""


@dataclass(frozen=True)
class Passage:
    """One corpus entry. `text` is an OrbitVitals summary, never a NASA quotation."""

    evidence_id: str
    publisher: str
    document_title: str
    section: str
    url: str
    topics: tuple[str, ...]
    text: str
    sha256: str
    source_paragraph_sha256: str
    source_checked_on: str
    text_kind: str = SUMMARY_KIND


@dataclass(frozen=True)
class ScoredPassage:
    passage: Passage
    score: float


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if token in _STOPWORDS:
            continue
        if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class EvidenceStore:
    corpus_id: str
    passages: list[Passage]
    # Passages excluded because they contain instruction-like text: id -> matched rules.
    quarantined: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._by_id = {passage.evidence_id: passage for passage in self.passages}
        self._tokens = {
            passage.evidence_id: Counter(
                tokenize(f"{passage.document_title} {passage.section} {passage.text}")
            )
            for passage in self.passages
        }
        lengths = [sum(counter.values()) for counter in self._tokens.values()]
        self._average_length = sum(lengths) / len(lengths) if lengths else 0.0
        self._document_frequency: Counter[str] = Counter()
        for counter in self._tokens.values():
            self._document_frequency.update(counter.keys())

    @classmethod
    def load(cls, path: Path = DEFAULT_CORPUS_PATH) -> EvidenceStore:
        """Load the corpus, refusing passages that fail an integrity check."""
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            allowed_hosts = set(raw["allowed_hosts"])
            entries = raw["passages"]
            corpus_id = raw["corpus_id"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
            raise CorpusIntegrityError(f"Cannot read the evidence corpus: {error}") from error
        passages: list[Passage] = []
        quarantined: dict[str, list[str]] = {}
        seen: set[str] = set()
        for entry in entries:
            try:
                passage = Passage(
                    evidence_id=entry["evidence_id"],
                    publisher=entry["publisher"],
                    document_title=entry["document_title"],
                    section=entry["section"],
                    url=entry["url"],
                    topics=tuple(entry["topics"]),
                    text=entry["text"],
                    sha256=entry["sha256"],
                    source_paragraph_sha256=entry["source_paragraph_sha256"],
                    source_checked_on=entry["source_checked_on"],
                    text_kind=entry["text_kind"],
                )
            except (KeyError, TypeError) as error:
                raise CorpusIntegrityError(f"Malformed corpus entry: {error}") from error
            if passage.evidence_id in seen:
                raise CorpusIntegrityError(f"Duplicate evidence id {passage.evidence_id}")
            seen.add(passage.evidence_id)
            if passage.text_kind != SUMMARY_KIND:
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: text kind {passage.text_kind!r} is not allowed; "
                    f"the corpus stores only {SUMMARY_KIND!r} entries"
                )
            if not _SHA256_HEX.fullmatch(passage.source_paragraph_sha256):
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: the source paragraph digest is not a SHA-256 value"
                )
            if sha256_text(passage.text) != passage.sha256:
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: text does not match its recorded SHA-256 digest"
                )
            parsed = urlparse(passage.url)
            if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: source {passage.url} is not on the allow-list"
                )
            matched = screen_text(passage.text)
            if matched:
                quarantined[passage.evidence_id] = matched
            else:
                passages.append(passage)
        return cls(corpus_id=corpus_id, passages=passages, quarantined=quarantined)

    def get(self, evidence_id: str) -> Passage | None:
        return self._by_id.get(evidence_id)

    def search(
        self,
        query: str,
        *,
        focus_topics: frozenset[str] = frozenset(),
        background_topics: frozenset[str] = frozenset(),
        top_k: int = 4,
    ) -> list[ScoredPassage]:
        """Return the best-matching passages, most relevant first.

        A passage is returned only when it shares a query term or a topic tag, so an
        unrelated question yields an empty list instead of a forced citation.
        """
        query_terms = set(tokenize(query))
        total = len(self.passages)
        scored: list[ScoredPassage] = []
        for passage in self.passages:
            counter = self._tokens[passage.evidence_id]
            length = sum(counter.values())
            score = 0.0
            for term in query_terms:
                frequency = counter.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequency[term]
                inverse = math.log(
                    1 + (total - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                normaliser = frequency + _BM25_K1 * (
                    1 - _BM25_B + _BM25_B * length / self._average_length
                )
                score += inverse * frequency * (_BM25_K1 + 1) / normaliser
            topics = set(passage.topics)
            score += _FOCUS_TOPIC_BONUS * len(topics & focus_topics)
            if topics & (background_topics - focus_topics):
                score += _BACKGROUND_TOPIC_BONUS
            if score > 0:
                scored.append(ScoredPassage(passage=passage, score=round(score, 4)))
        scored.sort(key=lambda item: (-item.score, item.passage.evidence_id))
        return scored[:top_k]
