"""Aggregates every versioned API route. Register new route modules here."""

from fastapi import APIRouter

from app.api.routes import health, monitoring

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(monitoring.router)
