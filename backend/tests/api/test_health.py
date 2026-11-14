from datetime import datetime

from fastapi.testclient import TestClient

from app import __version__
from app.core.config import SERVICE_NAME


def test_health_reports_service_status(client: TestClient) -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == SERVICE_NAME
    assert body["version"] == __version__
    assert datetime.fromisoformat(body["timestamp"]).tzinfo is not None


def test_health_is_callable_from_a_local_flutter_web_dev_server(client: TestClient) -> None:
    origin = "http://localhost:53124"

    response = client.get("/api/v1/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin


def test_unknown_origins_are_not_granted_cross_origin_access(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://example.com"})

    assert "access-control-allow-origin" not in response.headers
