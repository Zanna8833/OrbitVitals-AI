"""FastAPI application entry point.

Run locally from the `backend/` directory with:

    uvicorn app.main:app --reload
"""

import json
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.router import api_router
from app.core.config import API_V1_PREFIX, Settings, get_settings
from app.repositories.memory import InMemoryRepository
from app.services.integration import Clock, IntegrationError, IntegrationService


def create_app(
    settings: Settings | None = None,
    *,
    repository: InMemoryRepository | None = None,
    clock: Clock | None = None,
) -> FastAPI:
    """Build the application.

    Tests pass explicit settings so they do not depend on the local environment.
    """
    settings = settings or get_settings()

    app = FastAPI(
        title="OrbitVitals AI API",
        version=__version__,
        description=(
            "Explainable health monitoring for long-duration space missions. "
            "Research prototype, not a medical device."
        ),
    )
    app.state.repository = repository if repository is not None else InMemoryRepository()
    app.state.integration_service = IntegrationService(
        app.state.repository, settings, clock or (lambda: datetime.now(UTC))
    )

    @app.exception_handler(RequestValidationError)
    async def request_error_handler(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # A rejected NaN/Infinity must not break serialization of the 422 response.
        # Keep the standard error shape and render non-JSON input values as strings.
        detail = json.loads(json.dumps(error.errors(), default=str), parse_constant=str)
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.exception_handler(IntegrationError)
    async def integration_error_handler(_request: Request, error: IntegrationError) -> JSONResponse:
        detail = str(error)
        if error.status_code == 422:
            detail = [{"type": "value_error", "loc": list(error.location), "msg": str(error)}]
        return JSONResponse(status_code=error.status_code, content={"detail": detail})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_origin_regex=settings.cors_allow_origin_regex,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=API_V1_PREFIX)
    return app


app = create_app()
