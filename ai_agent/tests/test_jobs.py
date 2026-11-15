"""Server-owned explanation jobs: idempotent, persisted, independent of the client."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from orbit_agent.api import create_app
from orbit_agent.config import API_PREFIX
from orbit_agent.jobs import JobStore
from tests.support import CHEN, NOOR, make_agent


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(make_agent(jobs_dir=str(tmp_path))))


def _wait(client: TestClient, request_id: str) -> dict:
    for _ in range(200):
        body = client.get(f"{API_PREFIX}/jobs/{request_id}").json()
        if body["status"] != "running":
            return body
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_runs_to_completion_and_is_stored(tmp_path: Path) -> None:
    client = _client(tmp_path)
    submitted = client.post(
        f"{API_PREFIX}/jobs",
        json={
            "request_id": "req-crew-c-0001",
            "request": {"crew_member_id": CHEN, "mode": "deterministic"},
        },
    )
    assert submitted.status_code == 202
    body = _wait(client, "req-crew-c-0001")

    assert body["status"] == "done"
    assert body["crew_member_id"] == CHEN
    assert body["response"]["crew_member_id"] == CHEN
    assert (tmp_path / "req-crew-c-0001.json").exists()


def test_same_request_id_is_not_run_twice(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = {
        "request_id": "req-dup-0001",
        "request": {"crew_member_id": NOOR, "mode": "deterministic"},
    }
    first = client.post(f"{API_PREFIX}/jobs", json=payload).json()
    second = client.post(f"{API_PREFIX}/jobs", json=payload).json()

    assert first["created_at"] == second["created_at"]
    other_crew = {
        "request_id": "req-dup-0001",
        "request": {"crew_member_id": CHEN, "mode": "deterministic"},
    }
    assert client.post(f"{API_PREFIX}/jobs", json=other_crew).status_code == 409


def test_unknown_and_invalid_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)

    assert client.get(f"{API_PREFIX}/jobs/req-missing-0001").status_code == 404
    bad = {"request_id": "../../etc", "request": {"crew_member_id": NOOR, "mode": "deterministic"}}
    assert client.post(f"{API_PREFIX}/jobs", json=bad).status_code == 422


def test_a_job_interrupted_by_a_restart_is_reported(tmp_path: Path) -> None:
    (tmp_path / "req-lost-0001.json").write_text(
        '{"request_id":"req-lost-0001","crew_member_id":"x","status":"running",'
        '"created_at":"2026-11-15T22:00:00Z"}',
        encoding="utf-8",
    )
    store = JobStore(tmp_path, run=lambda request: None)  # type: ignore[arg-type,return-value]
    job = store.get("req-lost-0001")

    assert job is not None and job.status == "error"
    store.shutdown()
