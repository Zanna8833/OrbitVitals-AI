"""Server-owned explanation jobs, so an answer is not lost when the browser goes away.

The browser creates a job with its own request ID and polls for the result. The agent
runs the job on a worker thread, independent of the HTTP connection, and stores the
result as a JSON file. Closing the Assistant, navigating, refreshing or closing the tab
therefore does not cancel the work; the client reads the stored result later.

- Submitting the same request ID again returns the existing job: no duplicate run.
- One worker runs the jobs in submission order (the local model answers one at a time).
- A job found "running" when the service starts was interrupted by a restart; it is
  reported as failed rather than left pending forever.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from orbit_agent.backend_client import BackendUnavailable
from orbit_agent.models import AgentResponse, ExplanationRequest

JobStatus = Literal["running", "done", "error"]
REQUEST_ID_PATTERN = r"^[A-Za-z0-9_-]{8,80}$"


class JobSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(pattern=REQUEST_ID_PATTERN)
    request: ExplanationRequest


class Job(BaseModel):
    request_id: str
    crew_member_id: str
    status: JobStatus
    created_at: str
    finished_at: str | None = None
    response: AgentResponse | None = None
    error: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class JobStore:
    """Jobs kept in memory and mirrored to one JSON file each in `directory`."""

    def __init__(self, directory: Path, run: Callable[[ExplanationRequest], AgentResponse]):
        self._directory = directory
        self._run = run
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-job")
        self._directory.mkdir(parents=True, exist_ok=True)
        for path in self._directory.glob("*.json"):
            try:
                job = Job.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if job.status == "running":
                job = job.model_copy(
                    update={
                        "status": "error",
                        "finished_at": _now(),
                        "error": "The assistant service restarted before this answer was ready.",
                    }
                )
                self._write(job)
            self._jobs[job.request_id] = job

    def _path(self, request_id: str) -> Path:
        if not re.fullmatch(REQUEST_ID_PATTERN, request_id):
            raise ValueError("invalid request id")
        return self._directory / f"{request_id}.json"

    def _write(self, job: Job) -> None:
        path = self._path(job.request_id)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(job.model_dump_json(), encoding="utf-8")
        temporary.replace(path)

    def get(self, request_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(request_id)

    def submit(self, submission: JobSubmission) -> Job:
        with self._lock:
            existing = self._jobs.get(submission.request_id)
            if existing is not None:
                if existing.crew_member_id != submission.request.crew_member_id:
                    raise ValueError("request id already used for another crew member")
                return existing
            job = Job(
                request_id=submission.request_id,
                crew_member_id=submission.request.crew_member_id,
                status="running",
                created_at=_now(),
            )
            self._jobs[job.request_id] = job
            self._write(job)
        self._executor.submit(self._execute, job.request_id, submission.request)
        return job

    def _execute(self, request_id: str, request: ExplanationRequest) -> None:
        update: dict[str, Any]
        try:
            response = self._run(request)
            update = {"status": "done", "response": response}
        except BackendUnavailable:
            update = {
                "status": "error",
                "error": "The assistant cannot read the OrbitVitals server right now.",
            }
        except Exception:  # noqa: BLE001 - a failed job is reported, never left running
            update = {"status": "error", "error": "The assistant could not answer."}
        with self._lock:
            job = self._jobs[request_id].model_copy(update={**update, "finished_at": _now()})
            self._jobs[request_id] = job
            self._write(job)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


def dump(job: Job) -> dict[str, Any]:
    return json.loads(job.model_dump_json())
