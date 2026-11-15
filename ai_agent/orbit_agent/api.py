"""HTTP interface of the agent, served separately from the OrbitVitals backend.

Start it from `ai_agent/` with:

    uvicorn orbit_agent.api:app --port 8100

The service adds no endpoint to the backend and changes none of its contracts.
"""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Importing the adapter registers it, so `ORBITVITALS_AGENT_SPECIALIST=medgemma` works with
# `uvicorn orbit_agent.api:app`. Nothing is loaded or called until a review is needed.
from orbit_agent import __version__, medgemma  # noqa: F401
from orbit_agent.backend_client import BackendUnavailable
from orbit_agent.config import API_PREFIX, SERVICE_NAME, Settings, load_settings
from orbit_agent.evidence.store import EvidenceStore
from orbit_agent.jobs import Job, JobStore, JobSubmission
from orbit_agent.models import AgentResponse, Citation, ExplanationRequest
from orbit_agent.pipeline import Agent, citation_from


class EvidenceSearchResult(BaseModel):
    query: str
    items: list[Citation]


def create_app(agent: Agent | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or (agent.settings if agent else load_settings())
    agent = agent or Agent(settings=settings, store=EvidenceStore.load())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Load the primary model in the background while the service starts answering.
        if settings.warm_up_on_start:
            threading.Thread(target=agent.warm_up, name="warm-up", daemon=True).start()
        yield

    app = FastAPI(
        title="OrbitVitals AI agent (proof of concept)",
        version=__version__,
        description=(
            "Explains results already computed by the OrbitVitals backend. Research "
            "prototype, not a medical device."
        ),
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": __version__,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            **agent.status(),
        }

    @app.post(f"{API_PREFIX}/explanations", response_model=AgentResponse)
    def explain(request: ExplanationRequest) -> AgentResponse:
        try:
            return agent.explain(request)
        except BackendUnavailable as error:
            raise HTTPException(
                status_code=502,
                detail=f"The OrbitVitals backend could not be read: {error}",
            ) from error

    jobs = JobStore(Path(settings.jobs_dir), agent.explain)

    @app.post(f"{API_PREFIX}/jobs", response_model=Job, status_code=202)
    def submit_job(submission: JobSubmission) -> Job:
        try:
            return jobs.submit(submission)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get(f"{API_PREFIX}/jobs/{{request_id}}", response_model=Job)
    def read_job(request_id: str) -> Job:
        job = jobs.get(request_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown request id.")
        return job

    @app.get(f"{API_PREFIX}/evidence", response_model=EvidenceSearchResult)
    def search_evidence(
        query: Annotated[str, Query(min_length=2, max_length=300)],
        limit: Annotated[int, Query(ge=1, le=10)] = 5,
    ) -> EvidenceSearchResult:
        return EvidenceSearchResult(
            query=query,
            items=[citation_from(item) for item in agent.store.search(query, top_k=limit)],
        )

    return app


app = create_app()
