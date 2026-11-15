"""Knowledge base: markdown documents → chunks with a context line → hierarchical hybrid search (BM25 + embeddings)."""

import hashlib
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

PROJECT_FOLDER = Path(__file__).resolve().parents[2]
DOCUMENTS_FOLDER = PROJECT_FOLDER / "knowledge_base"
CACHE_FOLDER = PROJECT_FOLDER / "index_cache"
# bge-small-en-v1.5 instead of multilingual-e5-small (everything is in English): same cost, and on the evaluation
# the right protocol from the best chunk went from 17 to 24 out of 33
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge wants the prefix on queries only
PASSAGE_PREFIX = ""
CHUNKS_FOR_PROTOCOL = 3  # the protocol given in full is looked for among the 3 closest chunks by embedding...
CHUNKS_TO_CONFIRM_PROTOCOL = 5  # ...and must also appear among the top 5 chunks of the hybrid ranking

WORDS_PER_CHUNK = 350
MAX_DOCUMENT_CHARACTERS = 24000  # cap on a whole document passed to the model (READ_DOCUMENT)
RRF_CONSTANT = 60  # standard value for Reciprocal Rank Fusion
GLOBAL_SAFETY_CHUNKS = 2  # chunks taken from the whole base, in case the document level got it wrong
MAX_CHUNKS_PER_DOCUMENT = 2  # so that one big document (e.g. a FAQ) does not fill every slot
# A cause suggested by the model brings its protocol only if the closest chunk is similar enough
# (tested on hand-written causes: 'seizure' 0.77, 'decompression sickness' 0.83; 'hypoglycemia' 0.65 and
# 'peripheral nerve compression' 0.67 have no protocol in the base and landed on wrong documents)
MIN_CAUSE_SIMILARITY = 0.7
# The sections of a protocol that help compare causes (how to recognize it, what to do right away)
KEY_SECTION_WORDS = ["recognition", "immediate", "management", "memorized"]


def read_header(text: str) -> tuple[dict, str]:
    """Splits the header between the two '---' lines from the body. Without a header it returns an empty dict."""
    lines = text.split("\n")
    if len(lines) == 0 or lines[0].strip() != "---":
        return {}, text
    header = {}
    for line_number in range(1, len(lines)):
        line = lines[line_number]
        if line.strip() == "---":
            body = "\n".join(lines[line_number + 1:])
            return header, body
        if ":" not in line:
            continue
        position = line.index(":")
        key = line[:position].strip()
        value = line[position + 1:].strip()
        header[key] = value
    # Header never closed: the file is not a valid document
    return {}, text


def split_sections(body: str) -> list[tuple[str, str]]:
    """Splits the body at '## ' headings. Text before the first heading becomes the 'Overview' section."""
    sections = []
    current_title = "Overview"
    current_lines = []
    for line in body.split("\n"):
        if line.startswith("## "):
            text = "\n".join(current_lines).strip()
            if text != "":
                sections.append((current_title, text))
            current_title = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    text = "\n".join(current_lines).strip()
    if text != "":
        sections.append((current_title, text))
    return sections


def load_documents(folder: Path = DOCUMENTS_FOLDER) -> list[dict]:
    """Reads every .md file with a valid header (files without an 'id' are skipped)."""
    documents = []
    for path in sorted(folder.glob("*.md")):
        header, body = read_header(path.read_text(encoding="utf-8"))
        if "id" not in header:
            continue
        sources = []
        sources_text = header.get("sources", "").strip("[] ")
        for source in sources_text.split(","):
            if source.strip() != "":
                sources.append(source.strip())
        document = {
            "id": header["id"],
            "title": header.get("title", header["id"]),
            "category": header.get("category", ""),
            "summary": header.get("summary", ""),
            "sources": sources,
            "body": body.strip(),
            "sections": split_sections(body),
        }
        documents.append(document)
    return documents


def context_line(document: dict, section: str) -> str:
    """The line put above every chunk, built only from the document metadata (contextual RAG)."""
    return "[" + document["title"] + " › " + section + "] " + document["summary"]


def make_chunks(document: dict) -> list[dict]:
    """One chunk per section; long sections are split at whole lines (~WORDS_PER_CHUNK words),
    repeating the last line of the previous piece as a small overlap."""
    chunks = []
    for section, text in document["sections"]:
        pieces = []
        piece_lines = []
        piece_words = 0
        for line in text.split("\n"):
            line_words = len(line.split())
            if piece_words + line_words > WORDS_PER_CHUNK and piece_words > 0:
                pieces.append("\n".join(piece_lines).strip())
                last_line = piece_lines[-1]
                piece_lines = [last_line]
                piece_words = len(last_line.split())
            piece_lines.append(line)
            piece_words = piece_words + line_words
        pieces.append("\n".join(piece_lines).strip())

        for piece in pieces:
            context = context_line(document, section)
            chunks.append({
                "document_id": document["id"],
                "document_title": document["title"],
                "section": section,
                "sources": document["sources"],
                "text": piece,
                "text_with_context": context + "\n" + piece,
            })
    return chunks


def document_level_text(document: dict) -> str:
    """What represents the document at the first level of the search."""
    titles = []
    for section, _text in document["sections"]:
        titles.append(section)
    return document["title"] + ". " + document["summary"] + " Sections: " + "; ".join(titles)


def words(text: str) -> list[str]:
    """Lowercase words for BM25 (letters, digits; 'ppCO2' and 'mmHg' stay whole)."""
    return re.findall(r"[a-z0-9]+", text.lower())


def rrf_fusion(rankings: list[np.ndarray]) -> list[int]:
    """Reciprocal Rank Fusion: merges several rankings of indices into one, best first."""
    scores = {}
    for ranking in rankings:
        for position in range(len(ranking)):
            index = int(ranking[position])
            score = 1.0 / (RRF_CONSTANT + position + 1)
            scores[index] = scores.get(index, 0.0) + score
    pairs = []
    for index in scores:
        pairs.append((scores[index], index))
    pairs.sort(reverse=True)
    ordered = []
    for _score, index in pairs:
        ordered.append(index)
    return ordered


def rank(scores: np.ndarray, candidates: np.ndarray) -> np.ndarray:
    """The candidates sorted by decreasing score."""
    order = np.argsort(-scores[candidates], kind="stable")
    return candidates[order]


def document_header(document: dict) -> str:
    """Title, id and sources numbered like the [n] references in the document text."""
    numbered_sources = []
    for number in range(len(document["sources"])):
        numbered_sources.append("[" + str(number + 1) + "] " + document["sources"][number])
    text = "# " + document["title"] + " (document id: " + document["id"] + ")\n"
    return text + "Sources: " + " ".join(numbered_sources) + "\n\n"


class Index:
    """BM25 and embedding indexes at two levels (documents and chunks) over the documents folder."""

    def __init__(self, folder: Path = DOCUMENTS_FOLDER, embedding_model=None):
        self.documents = load_documents(folder)
        if len(self.documents) == 0:
            raise ValueError("No document with a header in " + str(folder))
        self.embedding_model = embedding_model

        self.document_texts = []
        self.chunks = []
        for document in self.documents:
            self.document_texts.append(document_level_text(document))
            for chunk in make_chunks(document):
                self.chunks.append(chunk)
        self.chunk_texts = []
        self.chunk_document = []
        for chunk in self.chunks:
            self.chunk_texts.append(chunk["text_with_context"])
            self.chunk_document.append(chunk["document_id"])
        self.chunk_document = np.array(self.chunk_document)

        document_words = []
        for text in self.document_texts:
            document_words.append(words(text))
        chunk_words = []
        for text in self.chunk_texts:
            chunk_words.append(words(text))
        self.bm25_documents = BM25Okapi(document_words)
        self.bm25_chunks = BM25Okapi(chunk_words)

        self.document_vectors, self.chunk_vectors = self.compute_vectors()

    def encode(self, texts: list[str], prefix: str) -> np.ndarray:
        """Normalized embeddings, with the prefix the model wants for queries or passages."""
        if self.embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        prefixed_texts = []
        for text in texts:
            prefixed_texts.append(prefix + text)
        vectors = self.embedding_model.encode(prefixed_texts, normalize_embeddings=True, batch_size=32)
        return np.asarray(vectors, dtype=np.float32)

    def compute_vectors(self) -> tuple[np.ndarray, np.ndarray]:
        """Embeddings of documents and chunks, saved in index_cache/ with a hash of the texts so they are not redone."""
        fingerprint = hashlib.sha256()
        fingerprint.update(EMBEDDING_MODEL.encode("utf-8"))
        for text in self.document_texts + self.chunk_texts:
            fingerprint.update(text.encode("utf-8"))
        cache_path = CACHE_FOLDER / (fingerprint.hexdigest()[:16] + ".npz")
        if cache_path.exists():
            saved = np.load(cache_path)
            return saved["documents"], saved["chunks"]
        document_vectors = self.encode(self.document_texts, PASSAGE_PREFIX)
        chunk_vectors = self.encode(self.chunk_texts, PASSAGE_PREFIX)
        CACHE_FOLDER.mkdir(exist_ok=True)
        np.savez(cache_path, documents=document_vectors, chunks=chunk_vectors)
        return document_vectors, chunk_vectors

    def search(self, query: str, n_documents: int = 3, n_chunks: int = 5) -> dict:
        """Hierarchical search: 1) best documents, 2) best chunks inside those documents,
        3) a few of the best chunks over the whole base as a safety net.
        Returns {"chunks": chosen chunks, "documents": ids chosen at level 1, "protocol": id or None}."""
        query_vector = self.encode([query], QUERY_PREFIX)[0]
        query_words = words(query)

        # Ranking of all chunks (BM25 over the whole base for stable IDF): used by both levels
        bm25_chunks = self.bm25_chunks.get_scores(query_words)
        cosine_chunks = self.chunk_vectors @ query_vector
        all_chunks = np.arange(len(self.chunks))
        global_ranking = rrf_fusion([rank(bm25_chunks, all_chunks), rank(cosine_chunks, all_chunks)])

        # Documents ordered by their best chunk: one very relevant section lifts the document
        # even when title and summary are generic (e.g. "pressure dropping" → rapid-depressurization)
        document_position = {}
        for number in range(len(self.documents)):
            document_position[self.documents[number]["id"]] = number
        documents_by_best_chunk = []
        for index in global_ranking:
            number = document_position[self.chunks[index]["document_id"]]
            if number not in documents_by_best_chunk:
                documents_by_best_chunk.append(number)

        # Level 1: documents
        all_documents = np.arange(len(self.documents))
        bm25_documents = self.bm25_documents.get_scores(query_words)
        cosine_documents = self.document_vectors @ query_vector
        document_ranking = rrf_fusion([
            rank(bm25_documents, all_documents),
            rank(cosine_documents, all_documents),
            np.array(documents_by_best_chunk),
        ])
        chosen_ids = []
        for index in document_ranking[:n_documents]:
            chosen_ids.append(self.documents[index]["id"])

        # Level 2: chunks of the chosen documents, at most MAX_CHUNKS_PER_DOCUMENT each
        candidates = np.flatnonzero(np.isin(self.chunk_document, chosen_ids))
        chunk_ranking = rrf_fusion([rank(bm25_chunks, candidates), rank(cosine_chunks, candidates)])
        chosen = []
        taken_per_document = {}
        for index in chunk_ranking:
            if len(chosen) == n_chunks:
                break
            document_id = self.chunks[index]["document_id"]
            taken = taken_per_document.get(document_id, 0)
            if taken < MAX_CHUNKS_PER_DOCUMENT:
                chosen.append(index)
                taken_per_document[document_id] = taken + 1

        # Safety net: the best global chunks not already taken
        added = 0
        for index in global_ranking:
            if added == GLOBAL_SAFETY_CHUNKS:
                break
            if index not in chosen:
                chosen.append(index)
                added = added + 1

        results = []
        for index in chosen:
            results.append(self.chunks[index])

        # Candidate protocol = the first 'protocol' document among the closest chunks by embedding, confirmed by the
        # hybrid ranking. On the evaluation: 28 right, 1 wrong; with the embedding alone 30 right but 4 wrong,
        # and a wrong protocol given in full is worse than none (the right document stays in the excerpts)
        hybrid_protocols = []
        for index in global_ranking[:CHUNKS_TO_CONFIRM_PROTOCOL]:
            hybrid_protocols.append(self.chunks[index]["document_id"])
        protocol = None
        for index in rank(cosine_chunks, all_chunks)[:CHUNKS_FOR_PROTOCOL]:
            document_id = self.chunks[index]["document_id"]
            if self.document(document_id)["category"] == "protocol" and document_id in hybrid_protocols:
                protocol = document_id
                break
        return {"chunks": results, "documents": chosen_ids, "protocol": protocol}

    def document_similarity(self, sentences: list[str], document_ids: list[str]) -> dict:
        """For each document, the highest similarity between one of the sentences and one of its chunks."""
        similarities = {}
        if len(sentences) == 0:
            return similarities
        sentence_vectors = self.encode(sentences, PASSAGE_PREFIX)
        for document_id in document_ids:
            rows = np.flatnonzero(self.chunk_document == document_id)
            if len(rows) > 0:
                similarities[document_id] = float((sentence_vectors @ self.chunk_vectors[rows].T).max())
        return similarities

    def document(self, document_id: str) -> dict | None:
        for document in self.documents:
            if document["id"] == document_id:
                return document
        return None

    def whole_document(self, document_id: str) -> str | None:
        """The complete document for READ_DOCUMENT (cut at MAX_DOCUMENT_CHARACTERS); None if the id does not exist."""
        document = self.document(document_id)
        if document is None:
            return None
        text = document_header(document) + document["body"]
        if len(text) > MAX_DOCUMENT_CHARACTERS:
            text = text[:MAX_DOCUMENT_CHARACTERS] + "\n[... document truncated ...]"
        return text

    def protocol_for_cause(self, cause: str) -> str | None:
        """The protocol of the chunk most similar to a suggested cause (e.g. 'decompression sickness');
        None if that chunk is not from a protocol or is not similar enough."""
        cause_vector = self.encode([cause], QUERY_PREFIX)[0]
        cosine_chunks = self.chunk_vectors @ cause_vector
        best = int(np.argmax(cosine_chunks))
        if cosine_chunks[best] < MIN_CAUSE_SIMILARITY:
            return None
        document_id = self.chunks[best]["document_id"]
        if self.document(document_id)["category"] != "protocol":
            return None
        return document_id

    def key_sections(self, document_id: str) -> str:
        """Recognition and immediate actions of a protocol: enough to compare several causes without giving
        the 4B model many whole documents. If no title matches, the first two sections."""
        document = self.document(document_id)
        chosen = []
        for title, text in document["sections"]:
            for word in KEY_SECTION_WORDS:
                if word in title.lower():
                    chosen.append("## " + title + "\n" + text)
                    break
        if len(chosen) == 0:
            for title, text in document["sections"][:2]:
                chosen.append("## " + title + "\n" + text)
        return document_header(document) + "\n\n".join(chosen)
