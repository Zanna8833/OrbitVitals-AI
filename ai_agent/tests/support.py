"""In-memory stand-ins for the backend and for Ollama. No test opens a socket."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from orbit_agent.config import Settings
from orbit_agent.evidence.store import EvidenceStore
from orbit_agent.facts import BackendSnapshot, FactSheet, build_fact_sheet
from orbit_agent.http import HttpResponse, TransportError
from orbit_agent.pipeline import Agent

FIXTURES = Path(__file__).parent / "fixtures" / "backend"
NOOR = "sim-mission-v1-02"
CHEN = "sim-mission-v1-03"
BACKEND_URL = "http://backend.test/api/v1"
OLLAMA_URL = "http://ollama.test"
MODEL = "gemma3:4b"
# In a scripted draft, stands for the first evidence identifier this request offers, so
# that a draft does not depend on which corpus entries retrieval happens to rank first.
FIRST_RETRIEVED = "@first-retrieved"


def offered_evidence_ids(chat_body: dict[str, Any]) -> list[str]:
    """Evidence identifiers that the output schema of a chat request allows."""
    properties = (chat_body.get("format") or {}).get("properties", {})
    items = properties.get("evidence_context", {}).get("items", {})
    return items.get("properties", {}).get("evidence_ids", {}).get("items", {}).get("enum", [])


def load_fixture(*parts: str) -> list[dict[str, Any]]:
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))["items"]


def snapshot(crew: str, domain: str | None = None) -> BackendSnapshot:
    evaluations = load_fixture(crew, "evaluations.json")
    return BackendSnapshot(
        crew_member_id=crew,
        metric_catalog=load_fixture("metrics.json"),
        evaluations=[item for item in evaluations if domain is None or item["domain"] == domain],
        baselines=load_fixture(crew, "baselines.json"),
        measurements=load_fixture(crew, "measurements.json"),
    )


def fact_sheet(crew: str, domain: str | None = None) -> FactSheet:
    return build_fact_sheet(snapshot(crew, domain), domain)


def _json(status: int, payload: Any) -> HttpResponse:
    return HttpResponse(status=status, body=json.dumps(payload).encode("utf-8"))


@dataclass
class FakeBackend:
    """Serves the recorded fixtures and records every request it receives."""

    reachable: bool = True
    requests: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, method: str, url: str, body: Any, timeout: float) -> HttpResponse:
        self.requests.append((method, url))
        if not self.reachable:
            raise TransportError("connection refused")
        if method != "GET":
            return _json(405, {"detail": "Method Not Allowed"})
        parsed = urlparse(url)
        path = parsed.path.removeprefix("/api/v1")
        query = parse_qs(parsed.query)
        if path == "/health":
            return _json(200, {"status": "ok"})
        if path == "/metrics":
            return _json(200, {"items": load_fixture("metrics.json")})
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "crew-members":
            file = FIXTURES / parts[1] / f"{parts[2]}.json"
            items = load_fixture(parts[1], f"{parts[2]}.json") if file.exists() else []
            if "domain" in query:
                items = [item for item in items if item.get("domain") == query["domain"][0]]
            return _json(200, {"items": items})
        return _json(404, {"detail": "Not Found"})


@dataclass
class FakeOllama:
    """Returns scripted completions, one per chat request."""

    drafts: list[Any] = field(default_factory=list)
    models: list[str] = field(default_factory=lambda: [MODEL])
    reachable: bool = True
    chat_requests: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, method: str, url: str, body: Any, timeout: float) -> HttpResponse:
        if not self.reachable:
            raise TransportError("connection refused")
        path = urlparse(url).path
        if path == "/api/tags":
            return _json(200, {"models": [{"name": name} for name in self.models]})
        if path == "/api/chat":
            self.chat_requests.append(body)
            index = min(len(self.chat_requests), len(self.drafts)) - 1
            draft = self.drafts[index]
            content = draft if isinstance(draft, str) else json.dumps(draft)
            if FIRST_RETRIEVED in content:
                offered = offered_evidence_ids(body)
                content = content.replace(FIRST_RETRIEVED, offered[0] if offered else "NONE")
            return _json(
                200,
                {
                    "message": {"role": "assistant", "content": content},
                    "total_duration": 1_500_000_000,
                    "load_duration": 5_000_000,
                    "prompt_eval_count": 100,
                    "eval_count": 50,
                    "done_reason": "stop",
                },
            )
        return _json(404, {"error": "not found"})

    def prompt(self, index: int = 0) -> str:
        return self.chat_requests[index]["messages"][1]["content"]


def make_agent(
    *,
    backend: FakeBackend | None = None,
    ollama: FakeOllama | None = None,
    store: EvidenceStore | None = None,
    specialist: Any = None,
    **settings: Any,
) -> Agent:
    return Agent(
        settings=Settings(backend_base_url=BACKEND_URL, ollama_base_url=OLLAMA_URL, **settings),
        store=store or EvidenceStore.load(),
        backend_transport=backend or FakeBackend(),
        model_transport=ollama or FakeOllama(),
        specialist=specialist,
    )


def fact_id(sheet: FactSheet, **criteria: Any) -> str:
    """Identifier of the single fact whose fields and data match `criteria`."""
    matches = [
        fact
        for fact in sheet.facts
        if all(
            getattr(fact, key, None) == value or fact.data.get(key) == value
            for key, value in criteria.items()
        )
    ]
    assert len(matches) == 1, f"{len(matches)} facts match {criteria}"
    return matches[0].id


def noor_draft(sheet: FactSheet, evidence_id: str = FIRST_RETRIEVED) -> dict[str, Any]:
    """A correct model draft for Noor's sleep, citing real fact identifiers.

    The evidence sentence holds no number and no sensitive word, so it is acceptable for
    whichever sleep entry is retrieved first.
    """
    latest = fact_id(sheet, kind="finding", metric="sleep_duration", observed_value=430.0)
    baseline = fact_id(sheet, kind="baseline", metric="sleep_duration")
    series = fact_id(sheet, kind="measurement_series", metric="sleep_duration")
    return {
        "headline": "Sleep duration was flagged for review because it fell steadily.",
        "observations": [
            {
                "text": (
                    "The latest sleep duration finding has status 'attention': the observed "
                    "value is 430 min against a personal baseline value of 480 min."
                ),
                "fact_ids": [latest, baseline],
            },
            {
                "text": "Recorded nights went from 490 min on 2026-10-12 to 370 min on 2026-10-20.",
                "fact_ids": [series],
            },
        ],
        "evidence_context": [
            {
                "text": (
                    "Sleep in spaceflight is influenced by the mission schedule and by the "
                    "light environment."
                ),
                "evidence_ids": [evidence_id],
            }
        ],
        "interpretations": [
            {
                "text": (
                    "The screen returned 'attention' because it detected a progressive "
                    "reduction pattern. It asks for a review and does not establish a cause."
                ),
                "kind": "screening_signal",
                "confidence": "moderate",
                "fact_ids": [latest],
                "evidence_ids": [],
            }
        ],
        "uncertainties": [
            {"text": "Why the recorded values fell is unknown.", "fact_ids": [latest]}
        ],
    }
