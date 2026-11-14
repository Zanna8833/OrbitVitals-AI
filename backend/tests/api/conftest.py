"""Deterministic, isolated API integration clients; every test record is simulated."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(_env_file=None), clock=lambda: NOW)) as client:
        yield client
