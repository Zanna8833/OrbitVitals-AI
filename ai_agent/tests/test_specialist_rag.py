"""MedGemma's specialist retrieval: Marco's rag/ index over reviewed sections only.

Uses the real `rag/knowledge_base` and `rag/src/assistant/knowledge.py`, with a fake
embedding model so that no model is downloaded and nothing touches the network.
Requires the optional dependencies of `requirements-specialist.txt`.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("rank_bm25")

from orbit_agent.config import Settings  # noqa: E402
from orbit_agent.evidence.store import EvidenceStore  # noqa: E402
from orbit_agent.medgemma import MedGemmaSpecialist, build_user_prompt  # noqa: E402
from orbit_agent.models import ExplanationRequest  # noqa: E402
from orbit_agent.pipeline import Agent  # noqa: E402
from orbit_agent.specialist_evidence import SpecialistKnowledge  # noqa: E402
from orbit_agent.specialist_evidence.knowledge import (  # noqa: E402
    ADMISSION_PATH,
    RAG_ROOT,
    admitted_documents,
)
from tests.support import BACKEND_URL, NOOR, OLLAMA_URL, fact_sheet, noor_draft  # noqa: E402
from tests.test_integration import (  # noqa: E402
    SPECIALIST_MODEL,
    TwoModelOllama,
    verdicts,
)

ADMISSION = json.loads(ADMISSION_PATH.read_text(encoding="utf-8"))
_DOSE = re.compile(r"\b\d+(\.\d+)?\s?(mg|mcg|ug|ml)\b|\bwhat to do\b", re.IGNORECASE)


class FakeEmbedding:
    """Deterministic bag-of-words vectors: similar wording gives similar vectors."""

    def encode(self, texts, normalize_embeddings=True, batch_size=32):  # noqa: ARG002
        vectors = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z]{4,}", text.lower()):
                digest = int(hashlib.md5(word.encode()).hexdigest()[:8], 16)  # noqa: S324
                vectors[row, digest % 256] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


def knowledge(tmp_path: Path, **options) -> SpecialistKnowledge:
    return SpecialistKnowledge(
        cache_root=tmp_path / "cache", embedding_model=FakeEmbedding(), **options
    )


def test_admission_quarantines_protocols_medication_and_unverified_sources() -> None:
    documents = {doc["id"]: doc for doc in ADMISSION["documents"]}
    admitted = [doc for doc in ADMISSION["documents"] if doc["decision"] == "admitted"]

    assert ADMISSION["summary"]["documents"] == len(documents) >= 50
    assert all(doc["category"] in {"knowledge", "faq"} for doc in admitted)
    for doc in documents.values():
        if doc["category"] in {"protocol", "reference-values"}:
            assert doc["decision"] == "quarantined", doc["id"]
    # No admitted section cites the third-party copy of the ISS emergency manual.
    for doc in admitted:
        for section in doc["sections"]:
            if section["decision"] == "admitted":
                assert section["reasons"] == []
    assert documents["iss-medical-kit-medications"]["decision"] == "quarantined"
    assert documents["insomnia-circadian-fatigue"]["decision"] == "quarantined"


def test_admitted_sections_contain_no_dose_or_advice() -> None:
    documents, problems = admitted_documents()

    assert problems == []
    assert (
        sum(len(doc["sections"]) for doc in documents) == ADMISSION["summary"]["admitted_sections"]
    )
    for doc in documents:
        for title, text in doc["sections"]:
            assert not _DOSE.search(f"{title}\n{text}"), (doc["id"], title)


def test_index_holds_only_admitted_material_and_writes_nothing_in_rag(tmp_path: Path) -> None:
    existed = (RAG_ROOT / "index_cache").exists()
    index = knowledge(tmp_path).index()
    admitted = {
        (doc["id"], section["title"])
        for doc in ADMISSION["documents"]
        for section in doc["sections"]
        if section["decision"] == "admitted"
    }

    assert index.chunks
    assert {(chunk["document_id"], chunk["section"]) for chunk in index.chunks} <= admitted
    assert not any(_DOSE.search(chunk["text"]) for chunk in index.chunks)
    assert (RAG_ROOT / "index_cache").exists() == existed
    assert any((tmp_path / "cache").rglob("*.npz"))


def test_changed_document_is_left_out(tmp_path: Path) -> None:
    copy = tmp_path / "rag"
    shutil.copytree(RAG_ROOT / "knowledge_base", copy / "knowledge_base")
    admitted = next(doc for doc in ADMISSION["documents"] if doc["decision"] == "admitted")
    path = copy / "knowledge_base" / admitted["file"]
    path.write_text(path.read_text(encoding="utf-8") + "\nTake 10 mg daily.\n", encoding="utf-8")

    documents, problems = admitted_documents(rag_root=copy)

    assert admitted["id"] not in {doc["id"] for doc in documents}
    assert any("changed after the review" in problem for problem in problems)


def test_unrelated_query_retrieves_no_specialist_evidence(tmp_path: Path) -> None:
    store = knowledge(tmp_path, min_similarity=0.99)
    assert store.search("quarterly revenue forecast spreadsheet") == []

    relaxed = knowledge(tmp_path, min_similarity=0.0)
    found = relaxed.search("landing deconditioning spine balance after landing", top_k=2)
    assert 1 <= len(found) <= 2
    assert [passage.evidence_id for passage in found] == [f"S{n + 1}" for n in range(len(found))]
    assert all(len(passage.text.split()) <= 161 for passage in found)


def test_missing_rag_module_is_reported_not_fatal(tmp_path: Path) -> None:
    broken = SpecialistKnowledge(rag_root=tmp_path / "missing", cache_root=tmp_path / "cache")
    settings = Settings(specialist="medgemma", specialist_model=SPECIALIST_MODEL)
    adapter = MedGemmaSpecialist(settings=settings, transport=TwoModelOllama(), knowledge=broken)

    assert adapter.warm_up()["specialist_knowledge"].startswith("unavailable")


def _agent_with_rag(tmp_path: Path, ollama: TwoModelOllama) -> Agent:
    settings = Settings(
        backend_base_url=BACKEND_URL,
        ollama_base_url=OLLAMA_URL,
        specialist="medgemma",
        specialist_model=SPECIALIST_MODEL,
    )
    from tests.support import FakeBackend

    specialist = MedGemmaSpecialist(
        settings=settings,
        transport=ollama,
        knowledge=knowledge(tmp_path, min_similarity=0.0),
    )
    return Agent(
        settings=settings,
        store=EvidenceStore.load(),
        backend_transport=FakeBackend(),
        model_transport=ollama,
        specialist=specialist,
    )


def test_medgemma_gets_backend_facts_plus_admitted_evidence_only(tmp_path: Path) -> None:
    ollama = TwoModelOllama(
        drafts=[noor_draft(fact_sheet(NOOR, "sleep"))],
        specialist_replies=[verdicts(("I1", "supported", None))],
    )
    response = _agent_with_rag(tmp_path, ollama).explain(
        ExplanationRequest(
            crew_member_id=NOOR, domain="sleep", question="Why is Noor's sleep flagged?"
        )
    )

    info = response.generation.specialist
    assert info.consulted and info.evidence_status == "used"
    assert 1 <= len(info.evidence) <= 2
    admitted_ids = {doc["id"] for doc in ADMISSION["documents"] if doc["decision"] == "admitted"}
    assert {ref.document_id for ref in info.evidence} <= admitted_ids
    assert all(ref.knowledge_base == "rag/knowledge_base" and ref.sources for ref in info.evidence)
    prompt = json.loads(ollama.specialist_requests[0]["messages"][1]["content"])
    assert len(prompt["specialist_background"]) == len(info.evidence)
    # Same backend facts as Qwen: every fact MedGemma sees is a fact of the response,
    # with the identical statement Qwen was given.
    qwen_prompt = ollama.chat_requests[0]["messages"][1]["content"]
    by_id = {fact.id: fact for fact in response.facts}
    for fact in prompt["facts"]:
        assert by_id[fact["id"]].statement == fact["statement"]
        assert fact["statement"] in qwen_prompt
    # The background text is never part of the answer shown to the operator.
    shown = json.dumps(
        [response.headline, *(s.text for s in response.uncertainties + response.observations)]
    )
    for item in prompt["specialist_background"]:
        assert item["text"][:60] not in shown
    assert response.verification.passed


def test_review_prompt_without_background_is_unchanged() -> None:
    from orbit_agent.specialist import SpecialistRequest

    sheet = fact_sheet(NOOR, "sleep")
    request = SpecialistRequest(
        crew_member_id=NOOR, question=None, facts=tuple(sheet.facts), interpretations=()
    )
    assert json.loads(build_user_prompt(request))["specialist_background"] == []
