"""Isolated adapter around the specialist retrieval of `rag/` (Marco's MedGemma RAG).

What is reused, unchanged: `rag/src/assistant/knowledge.py`: document parsing, chunking
with a context line, and the hierarchical hybrid search (BM25 + `BAAI/bge-small-en-v1.5`
embeddings, Reciprocal Rank Fusion). The module is loaded from its file; nothing in
`rag/` is modified and `rag/` is not put on the import path.

What the adapter adds:

1. Admission. Only sections listed as admitted in `admission.json` (written by
   `scripts/review_specialist_kb.py`) are indexed. Each file and section must still have
   the SHA-256 recorded at review time; anything changed since is left out. Sections are
   screened again for instruction-like text. Quarantined material (emergency protocols,
   medication, doses, reference values, unverified sources, advice) never enters the
   index, so retrieval cannot return it.
2. Isolation. The admitted sections are written as temporary Markdown files outside the
   repository (system temporary folder), and Marco's index and its embedding cache are
   built there. `rag/index_cache` is not written.
3. Relevance. Marco's search always returns its top chunks; the adapter keeps only
   chunks whose embedding similarity to the query reaches a minimum, so an unrelated
   query yields no evidence.

The evidence goes only into the specialist's prompt, as background. It is not shown to
the operator; the response lists which document sections were given (provenance).
Optional dependencies: `numpy`, `rank_bm25`, `sentence-transformers` (and `torch`); see
`requirements-specialist.txt`. Without them, or without the embedding model, the
adapter reports itself unavailable and the review runs on the crew facts alone.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from orbit_agent.evidence.sanitizer import screen_text

PACKAGE_DIR = Path(__file__).resolve().parent
ADMISSION_PATH = PACKAGE_DIR / "admission.json"
REPOSITORY_ROOT = PACKAGE_DIR.parents[2]
RAG_ROOT = REPOSITORY_ROOT / "rag"


class SpecialistEvidenceUnavailable(Exception):
    """The specialist retrieval cannot run (missing files, dependencies or model)."""


@dataclass(frozen=True)
class SpecialistPassage:
    evidence_id: str
    document_id: str
    document_title: str
    section: str
    sources: tuple[str, ...]
    text: str
    similarity: float


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_rag_knowledge(rag_root: Path) -> ModuleType:
    """Load `rag/src/assistant/knowledge.py` by path, under a private module name."""
    path = rag_root / "src" / "assistant" / "knowledge.py"
    if not path.exists():
        raise SpecialistEvidenceUnavailable(f"{path} does not exist")
    spec = importlib.util.spec_from_file_location("orbit_agent_rag_knowledge", path)
    if spec is None or spec.loader is None:
        raise SpecialistEvidenceUnavailable(f"{path} cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except ImportError as error:
        raise SpecialistEvidenceUnavailable(
            f"rag retrieval dependencies are missing: {error}"
        ) from error
    return module


def admitted_documents(
    rag_root: Path = RAG_ROOT, admission_path: Path = ADMISSION_PATH
) -> tuple[list[dict[str, Any]], list[str]]:
    """Admitted documents with only their admitted, unchanged, screened sections.

    Returns (documents, problems). A document whose file changed after the review is
    left out entirely; a changed section is left out on its own.
    """
    admission = json.loads(admission_path.read_text(encoding="utf-8"))
    knowledge_base = rag_root / "knowledge_base"
    documents: list[dict[str, Any]] = []
    problems: list[str] = []
    for entry in admission["documents"]:
        if entry["decision"] != "admitted":
            continue
        path = knowledge_base / entry["file"]
        if not path.exists():
            problems.append(f"{entry['id']}: file is missing")
            continue
        raw = path.read_text(encoding="utf-8")
        if _sha256(raw) != entry["file_sha256"]:
            problems.append(f"{entry['id']}: file changed after the review; left out")
            continue
        header, body = _ParserOnly.read_header(raw)
        sections = dict(_ParserOnly.split_sections(body))
        kept = []
        for section in entry["sections"]:
            if section["decision"] != "admitted":
                continue
            text = sections.get(section["title"])
            if text is None or _sha256(text) != section["sha256"]:
                problems.append(f"{entry['id']} / {section['title']}: changed; left out")
                continue
            if screen_text(f"{section['title']}\n{text}"):
                problems.append(f"{entry['id']} / {section['title']}: instruction-like text")
                continue
            kept.append((section["title"], text))
        if kept:
            documents.append(
                {
                    "id": entry["id"],
                    "title": entry["title"],
                    "category": entry["category"],
                    "summary": header.get("summary", ""),
                    "sources": entry["sources"],
                    "sections": kept,
                }
            )
    return documents, problems


class _ParserOnly:
    """The two parsing functions of `rag/src/assistant/knowledge.py`, without its imports.

    Marco's module imports numpy and rank_bm25 at load time; admission must work without
    them, so the same parsing rules are applied here (header between `---` lines,
    sections at `## `). `scripts/review_specialist_kb.py` uses the same rules.
    """

    @staticmethod
    def read_header(text: str) -> tuple[dict[str, str], str]:
        lines = text.split("\n")
        if not lines or lines[0].strip() != "---":
            return {}, text
        header: dict[str, str] = {}
        for number in range(1, len(lines)):
            line = lines[number]
            if line.strip() == "---":
                return header, "\n".join(lines[number + 1 :])
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip()] = value.strip()
        return {}, text

    @staticmethod
    def split_sections(body: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        title, current = "Overview", []
        for line in body.split("\n"):
            if line.startswith("## "):
                if "\n".join(current).strip():
                    sections.append((title, "\n".join(current).strip()))
                title, current = line[3:].strip(), []
            else:
                current.append(line)
        if "\n".join(current).strip():
            sections.append((title, "\n".join(current).strip()))
        return sections


def _write_markdown(document: dict[str, Any]) -> str:
    """A document in the format Marco's loader reads, holding only admitted sections."""
    header = [
        "---",
        f"id: {document['id']}",
        f"title: {document['title']}",
        f"category: {document['category']}",
        f"summary: {document['summary']}",
        f"sources: [{', '.join(document['sources'])}]",
        "---",
        "",
    ]
    body = [f"## {title}\n{text}\n" for title, text in document["sections"]]
    return "\n".join(header) + "\n".join(body)


class SpecialistKnowledge:
    """Lazy, thread-safe wrapper around Marco's `Index` over the admitted sections."""

    def __init__(
        self,
        *,
        rag_root: Path = RAG_ROOT,
        admission_path: Path = ADMISSION_PATH,
        cache_root: Path | None = None,
        embedding_model: Any = None,
        min_similarity: float = 0.6,
        max_words: int = 160,
    ) -> None:
        self.rag_root = rag_root
        self.admission_path = admission_path
        self.cache_root = cache_root or Path(tempfile.gettempdir()) / "orbitvitals-specialist"
        self.embedding_model = embedding_model
        self.min_similarity = min_similarity
        self.max_words = max_words
        self._lock = threading.Lock()
        self._index: Any = None
        self._query_prefix = ""
        self._error: str | None = None
        self.load_problems: list[str] = []
        self.documents: list[dict[str, Any]] = []

    def _build(self) -> Any:
        documents, problems = admitted_documents(self.rag_root, self.admission_path)
        self.documents, self.load_problems = documents, problems
        if not documents:
            raise SpecialistEvidenceUnavailable("no admitted section is available")
        rag = _load_rag_knowledge(self.rag_root)
        digest = _sha256(json.dumps(documents, sort_keys=True))[:16]
        folder = self.cache_root / digest / "knowledge"
        folder.mkdir(parents=True, exist_ok=True)
        for document in documents:
            (folder / f"{document['id']}.md").write_text(
                _write_markdown(document), encoding="utf-8"
            )
        # Marco's module keeps its embedding cache in a module constant; point it at the
        # temporary folder so that `rag/` is never written.
        rag.CACHE_FOLDER = self.cache_root / digest / "index_cache"
        self._query_prefix = getattr(rag, "QUERY_PREFIX", "")
        try:
            return rag.Index(folder=folder, embedding_model=self.embedding_model)
        except Exception as error:  # noqa: BLE001 - model download or load failures
            raise SpecialistEvidenceUnavailable(
                f"the rag index could not be built: {type(error).__name__}: {error}"
            ) from error

    def index(self) -> Any:
        with self._lock:
            if self._index is None and self._error is None:
                try:
                    self._index = self._build()
                except SpecialistEvidenceUnavailable as error:
                    self._error = str(error)
            if self._index is None:
                raise SpecialistEvidenceUnavailable(self._error or "unavailable")
            return self._index

    def status(self) -> dict[str, Any]:
        return {
            "loaded": self._index is not None,
            "error": self._error,
            "admitted_documents": len(self.documents),
            "admitted_sections": sum(len(d["sections"]) for d in self.documents),
            "load_problems": self.load_problems,
        }

    def search(self, query: str, top_k: int = 2) -> list[SpecialistPassage]:
        """Relevant admitted chunks for `query`, most similar first. Never more than top_k."""
        index = self.index()
        found = index.search(query, n_documents=3, n_chunks=4)["chunks"]
        query_vector = index.encode([query], self._query_prefix)[0]
        positions = {id(chunk): number for number, chunk in enumerate(index.chunks)}
        scored = []
        for chunk in found:
            number = positions.get(id(chunk))
            if number is None:
                continue
            similarity = float(index.chunk_vectors[number] @ query_vector)
            if similarity >= self.min_similarity:
                scored.append((similarity, chunk))
        scored.sort(key=lambda pair: -pair[0])
        passages = []
        seen: set[tuple[str, str]] = set()
        for similarity, chunk in scored:
            key = (chunk["document_id"], chunk["section"])
            if key in seen:
                continue
            seen.add(key)
            words = chunk["text"].split()
            text = " ".join(words[: self.max_words]) + (
                " ..." if len(words) > self.max_words else ""
            )
            passages.append(
                SpecialistPassage(
                    evidence_id=f"S{len(passages) + 1}",
                    document_id=chunk["document_id"],
                    document_title=chunk["document_title"],
                    section=chunk["section"],
                    sources=tuple(chunk["sources"]),
                    text=text,
                    similarity=round(similarity, 3),
                )
            )
            if len(passages) == top_k:
                break
        return passages
