"""Fixtures shared by the whole test suite."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """HTTP client bound to an app that ignores the developer's local `.env` file."""
    app = create_app(Settings(_env_file=None))
    with TestClient(app) as test_client:
        yield test_client
