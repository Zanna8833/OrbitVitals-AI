"""Evidence Explorer: verified NASA passages, retrieved locally."""

from orbit_agent.evidence.store import (
    CorpusIntegrityError,
    EvidenceStore,
    Passage,
    ScoredPassage,
)

__all__ = ["CorpusIntegrityError", "EvidenceStore", "Passage", "ScoredPassage"]
