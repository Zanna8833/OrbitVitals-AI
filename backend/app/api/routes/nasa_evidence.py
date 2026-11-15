"""GET-only scientific context; this route has no crew repository dependency."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.nasa_evidence import DatasetId, EvidenceResponse, EvidenceTopic, NasaEvidenceAdapter

router = APIRouter(prefix="/nasa-evidence", tags=["NASA dataset evidence"])


def get_evidence_adapter(request: Request) -> NasaEvidenceAdapter:
    return request.app.state.nasa_evidence_adapter


@router.get("", response_model=EvidenceResponse)
def evidence(
    topic: EvidenceTopic,
    response: Response,
    adapter: Annotated[NasaEvidenceAdapter, Depends(get_evidence_adapter)],
    dataset_id: DatasetId | None = None,
) -> EvidenceResponse:
    # Integrity is rechecked per request; do not let intermediary caches hide changes.
    response.headers["Cache-Control"] = "no-store"
    return adapter.retrieve(topic, dataset_id)
