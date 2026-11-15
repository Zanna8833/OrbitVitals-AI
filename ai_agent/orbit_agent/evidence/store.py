"""Local evidence corpus: integrity checks and deterministic retrieval.

The corpus holds short factual summaries, written by the OrbitVitals team, of
paragraphs on public NASA web pages and in open-access peer-reviewed articles. It
stores no source text: each entry records the source URL, title and section, and the
SHA-256 digest of the summarised paragraph, so `scripts/verify_sources.py` can confirm
that the paragraph is still published without the repository redistributing it. A
citation returned by the agent is always one of these stored summaries, attached by the
program and never written by a language model.

Retrieval is lexical (Okapi BM25) with bonuses for curated topic tags, followed by a
selection step that limits how many results come from one source and skips entries that
repeat an already selected one. It is deterministic, needs no embedding model and is
easy to audit, which suits a corpus of about a hundred entries. It does not understand
paraphrase beyond a small keyword-to-topic list; see the README for limits and
`scripts/evaluate_retrieval.py` for measurements.
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

DEFAULT_CORPUS_PATH = Path(__file__).parent / "corpus" / "evidence_summaries.json"
# The only kind of text the corpus may contain: a summary written by the project team.
SUMMARY_KIND = "independent_summary"
NASA_WEB_PAGE = "nasa_web_page"
PEER_REVIEWED_ARTICLE = "peer_reviewed_article"
SOURCE_TYPES = frozenset({NASA_WEB_PAGE, PEER_REVIEWED_ARTICLE})
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")

# Okapi BM25 parameters. Manning, Raghavan and Schuetze, "Introduction to Information
# Retrieval" (Cambridge University Press, 2008), section 11.4.3, report k1 between 1.2
# and 2 and b = 0.75 as reasonable values. Not tuned on this corpus.
_BM25_K1 = 1.5
_BM25_B = 0.75
# Topic bonuses. Engineering choices with no external source: tags are curated by hand,
# so a focus-tag match is weighted like a strong term match. A topic named by the query
# itself counts a little less than a focus topic supplied by the caller, and a background
# topic adds one small bonus. They affect only which entries are shown, never a health
# result. `scripts/evaluate_retrieval.py` reports their effect on a labelled query set.
_FOCUS_TOPIC_BONUS = 2.0
_QUERY_TOPIC_BONUS = 1.5
_BACKGROUND_TOPIC_BONUS = 0.75
# Selection after scoring (engineering choices, measured by the same script): at most
# two results from one source, and no result whose content words overlap an already
# selected result by this Jaccard similarity or more.
_MAX_PER_SOURCE = 2
_REDUNDANCY_LIMIT = 0.5
# Without a topic match, an entry must share at least this many distinct, specific query
# terms (or the only term of a one-term query). One shared word is not evidence that an
# entry is about the question, and neither are words found in a large share of the corpus
# ("crew", "mission", "space"): a term is specific when at most this fraction of the
# entries contain it.
_MIN_SHARED_TERMS = 2
_SPECIFIC_TERM_MAX_SHARE = 0.15

_STOPWORDS = frozenset(
    {"a", "an", "and", "are", "as", "at", "be", "been", "by", "can", "could", "for", "from"}
    | {"has", "have", "how", "in", "into", "is", "it", "its", "may", "more", "most", "of"}
    | {"on", "or", "such", "than", "that", "the", "their", "them", "these", "they", "this"}
    | {"to", "was", "were", "what", "when", "which", "while", "who", "will", "with", "also"}
    | {"about", "during", "other", "would", "should", "do", "doe", "did", "why", "there"}
)
_TOKEN = re.compile(r"[a-z0-9]+")

# Words of a question that name a topic of the corpus, in the form `tokenize` produces.
# A curated list, so that everyday wording ("tired", "heart", "workout") reaches entries
# tagged with the corresponding topic even when the entry uses other words. Words with a
# second meaning in this project are left out on purpose: "dose" (radiation or
# medication), "simulated" (the crew data), "shift" (fluid or work), "rest".
_TOPIC_KEYWORDS: dict[str, frozenset[str]] = {
    "sleep": frozenset({"sleep", "slept", "asleep", "nap", "awake", "bedtime"}),
    "circadian": frozenset({"circadian", "clock", "rhythm", "sunrise", "sunset", "daylight"}),
    "fatigue": frozenset({"fatigue", "tired", "tiredness", "exhausted", "exhaustion", "sleepy"})
    | {"drowsy", "alertness"},
    "workload": frozenset({"workload", "schedule", "overload"}),
    "exercise": frozenset({"exercise", "workout", "training", "treadmill", "sport"}),
    "fitness": frozenset({"fitness", "aerobic", "endurance", "deconditioning"}),
    "cardiovascular": frozenset({"heart", "cardiac", "cardiovascular", "blood", "vascular"})
    | {"vein", "artery", "circulation", "pulse", "faint", "fainting", "orthostatic"},
    "radiation": frozenset({"radiation", "cosmic", "ray", "shielding", "dosimeter", "flare"}),
    "cognition": frozenset({"cognition", "cognitive", "memory", "attention", "brain", "mental"})
    | {"concentration", "thinking"},
    "behavioral": frozenset({"behavior", "behavioral", "behaviour", "behavioural", "mood"})
    | {"morale", "psychological", "conflict"},
    "isolation": frozenset({"isolation", "isolated", "confinement", "confined", "lonely"}),
    "microgravity": frozenset({"microgravity", "weightlessness", "weightless", "gravity"}),
    "bone": frozenset({"bone", "skeleton", "skeletal", "osteoporosis"}),
    "muscle": frozenset({"muscle", "muscular", "atrophy"}),
    "vision": frozenset({"vision", "eye", "eyesight", "sight", "visual", "ocular"}),
    "fluid_shift": frozenset({"fluid", "puffy", "puffiness", "swelling"}),
    "sensorimotor": frozenset({"balance", "dizziness", "dizzy", "coordination", "vestibular"})
    | {"nausea"},
    "monitoring": frozenset({"monitor", "monitoring", "sensor", "wearable", "actigraphy"}),
    "analog": frozenset({"analog", "analogue", "bedrest", "antarctic"}),
    "baseline": frozenset({"baseline"}),
    "individual_variability": frozenset({"individual", "variability", "variation"}),
}
_KEYWORD_TOPIC = {word: topic for topic, words in _TOPIC_KEYWORDS.items() for word in words}


class CorpusIntegrityError(Exception):
    """The corpus file is malformed or a passage does not match its recorded digest."""


@dataclass(frozen=True)
class Passage:
    """One corpus entry. `text` is an OrbitVitals summary, never a quotation of the source.

    `url` identifies the source for a reader (a NASA page, or the DOI of an article).
    `verification_url` is where the summarised paragraph can be fetched and hashed; it is
    the same as `url` unless stated.
    """

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
    source_type: str = NASA_WEB_PAGE
    verification_url: str | None = None
    authors: str | None = None
    year: int | None = None
    license: str | None = None

    @property
    def source_label(self) -> str:
        """How the source is named in fixed wording, without presenting it as a speaker."""
        if self.source_type == PEER_REVIEWED_ARTICLE:
            return (
                f'peer-reviewed article "{self.document_title}" ({self.authors}, '
                f'{self.publisher}, {self.year}; section "{self.section}")'
            )
        return f'{self.publisher} web page "{self.document_title}" (section "{self.section}")'


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


def topics_named_in(text: str) -> frozenset[str]:
    """Corpus topics that the words of `text` name, using the curated keyword list."""
    return frozenset(_KEYWORD_TOPIC[token] for token in tokenize(text) if token in _KEYWORD_TOPIC)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _allowed(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in allowed_hosts


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
        # Content words of the summary alone, for the redundancy filter.
        self._content = {
            passage.evidence_id: frozenset(
                token for token in tokenize(passage.text) if len(token) > 2
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
                    source_type=entry.get("source_type", NASA_WEB_PAGE),
                    verification_url=entry.get("verification_url"),
                    authors=entry.get("authors"),
                    year=entry.get("year"),
                    license=entry.get("license"),
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
            if passage.source_type not in SOURCE_TYPES:
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: unknown source type {passage.source_type!r}"
                )
            if passage.source_type == PEER_REVIEWED_ARTICLE and not (
                passage.authors and passage.year and passage.license
            ):
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: an article entry needs authors, year and license"
                )
            if not _SHA256_HEX.fullmatch(passage.source_paragraph_sha256):
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: the source paragraph digest is not a SHA-256 value"
                )
            if sha256_text(passage.text) != passage.sha256:
                raise CorpusIntegrityError(
                    f"{passage.evidence_id}: text does not match its recorded SHA-256 digest"
                )
            for url in (passage.url, passage.verification_url or passage.url):
                if not _allowed(url, allowed_hosts):
                    raise CorpusIntegrityError(
                        f"{passage.evidence_id}: source {url} is not on the allow-list"
                    )
            # Everything of an entry that can reach the model or the operator is screened:
            # the summary and the source details shown next to it.
            matched = screen_text(
                " ".join(
                    part
                    for part in (
                        passage.text,
                        passage.document_title,
                        passage.section,
                        passage.authors,
                        passage.publisher,
                    )
                    if part
                )
            )
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
        legacy: bool = False,
    ) -> list[ScoredPassage]:
        """Return the best-matching passages, most relevant first.

        An entry is returned only when it matches a topic or shares enough query terms,
        so an unrelated question yields an empty list instead of a forced citation.

        `legacy=True` reproduces the scoring used before the corpus was expanded (any
        shared term qualifies; no topics from the query; no selection step). It exists
        only so that `scripts/evaluate_retrieval.py` can compare the two.
        """
        query_terms = set(tokenize(query))
        query_topics = frozenset() if legacy else topics_named_in(query) - focus_topics
        needed_terms = 1 if legacy else min(_MIN_SHARED_TERMS, len(query_terms))
        total = len(self.passages)
        # In a one-term query, or with the first version's rules, every shared term counts.
        count_all_terms = legacy or len(query_terms) == 1
        specific_limit = _SPECIFIC_TERM_MAX_SHARE * total
        scored: list[ScoredPassage] = []
        for passage in self.passages:
            counter = self._tokens[passage.evidence_id]
            length = sum(counter.values())
            score = 0.0
            shared_terms = 0
            for term in query_terms:
                frequency = counter.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequency[term]
                if count_all_terms or document_frequency <= specific_limit:
                    shared_terms += 1
                inverse = math.log(
                    1 + (total - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                normaliser = frequency + _BM25_K1 * (
                    1 - _BM25_B + _BM25_B * length / self._average_length
                )
                score += inverse * frequency * (_BM25_K1 + 1) / normaliser
            topics = set(passage.topics)
            topic_bonus = _FOCUS_TOPIC_BONUS * len(topics & focus_topics)
            topic_bonus += _QUERY_TOPIC_BONUS * len(topics & query_topics)
            if topics & (background_topics - focus_topics - query_topics):
                topic_bonus += _BACKGROUND_TOPIC_BONUS
            if topic_bonus == 0 and shared_terms < needed_terms:
                continue
            score += topic_bonus
            if score > 0:
                scored.append(ScoredPassage(passage=passage, score=round(score, 4)))
        scored.sort(key=lambda item: (-item.score, item.passage.evidence_id))
        return scored[:top_k] if legacy else self._select(scored, top_k)

    def _select(self, ranked: list[ScoredPassage], top_k: int) -> list[ScoredPassage]:
        """Take results in rank order, skipping crowded sources and repeated content."""
        selected: list[ScoredPassage] = []
        per_source: Counter[str] = Counter()
        for item in ranked:
            if len(selected) == top_k:
                break
            passage = item.passage
            if per_source[passage.url] >= _MAX_PER_SOURCE:
                continue
            content = self._content[passage.evidence_id]
            if any(
                _jaccard(content, self._content[other.passage.evidence_id]) >= _REDUNDANCY_LIMIT
                for other in selected
            ):
                continue
            selected.append(item)
            per_source[passage.url] += 1
        return selected


def _jaccard(first: frozenset[str], second: frozenset[str]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 0.0
