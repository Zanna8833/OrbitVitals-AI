"""FastAPI application entry point.

Run locally from the `backend/` directory with:

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import API_V1_PREFIX, Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
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
