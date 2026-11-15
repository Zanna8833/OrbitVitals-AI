"""Specialist evidence: Marco's `rag/` retrieval, restricted to reviewed sections.

Only the specialist model (MedGemma) receives this evidence. See `knowledge.py`.
"""

from orbit_agent.specialist_evidence.knowledge import (
    SpecialistEvidenceUnavailable,
    SpecialistKnowledge,
    SpecialistPassage,
)

__all__ = ["SpecialistEvidenceUnavailable", "SpecialistKnowledge", "SpecialistPassage"]
