"""Test transport that still exercises real JSON endpoints and integrated algorithms."""

from fastapi.testclient import TestClient

from app.demo_seed.client import SeedError


class TestApi:
    __test__ = False

    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.calls: list[tuple[str, str]] = []

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        self.calls.append((method, path))
        response = self.client.request(method, "/api/v1" + path, json=payload)
        if response.status_code >= 400:
            raise SeedError(f"HTTP {response.status_code}: {response.text}")
        return response.json()
