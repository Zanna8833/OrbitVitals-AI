"""Health-check endpoint used by the frontend and by deployment probes."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import AwareDatetime, BaseModel, Field

from app import __version__
from app.core.config import SERVICE_NAME

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness information about the API process."""

    status: Literal["ok"] = Field(description="Always 'ok' when the service can answer.")
    service: str = Field(description="Service identifier.")
    version: str = Field(description="Backend version.")
    timestamp: AwareDatetime = Field(description="Server time in UTC.")


@router.get("/health", response_model=HealthResponse, summary="Service health check")
def read_health() -> HealthResponse:
    """Report that the API process is up. Downstream dependencies are not checked."""
    return HealthResponse(
        status="ok",
        service=SERVICE_NAME,
        version=__version__,
        timestamp=datetime.now(UTC),
    )
