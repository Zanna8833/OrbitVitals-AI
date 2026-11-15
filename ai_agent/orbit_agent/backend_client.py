"""Read-only client of the OrbitVitals backend API.

The backend is the authority on measurements, baselines and evaluations. This client
can only issue GET requests: it has no method that writes, and its request helper
refuses every other HTTP verb. Stored evaluations are read as they are; the agent never
asks the backend to compute a new baseline or evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode

from orbit_agent.http import Transport, TransportError, urllib_transport


class BackendUnavailable(Exception):
    """The backend did not answer, or answered with an unexpected status or shape."""


class ReadOnlyViolation(Exception):
    """A non-GET request was attempted through the read-only client."""


@dataclass(frozen=True)
class AccessRecord:
    """One request made to the backend, kept for the audit trail of a response."""

    method: str
    path: str
    status: int
    item_count: int | None


@dataclass
class ReadOnlyBackendClient:
    base_url: str
    transport: Transport = urllib_transport
    timeout_seconds: float = 10.0
    access_log: list[AccessRecord] = field(default_factory=list)

    def _request(self, method: str, path: str, query: dict[str, str] | None = None) -> Any:
        if method != "GET":
            raise ReadOnlyViolation(f"The agent may only read from the backend, not {method}")
        suffix = f"?{urlencode(query)}" if query else ""
        url = f"{self.base_url.rstrip('/')}{path}{suffix}"
        try:
            response = self.transport(method, url, None, self.timeout_seconds)
        except TransportError as error:
            raise BackendUnavailable(str(error)) from error
        if response.status != 200:
            self.access_log.append(AccessRecord(method, path + suffix, response.status, None))
            raise BackendUnavailable(f"GET {path} returned status {response.status}")
        try:
            payload = response.json()
        except TransportError as error:
            raise BackendUnavailable(str(error)) from error
        items = payload.get("items") if isinstance(payload, dict) else None
        self.access_log.append(
            AccessRecord(
                method, path + suffix, response.status, len(items) if items is not None else None
            )
        )
        return payload

    def _items(self, path: str, query: dict[str, str] | None = None) -> list[dict[str, Any]]:
        payload = self._request("GET", path, query)
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise BackendUnavailable(f"GET {path} did not return an 'items' list")
        return items

    @staticmethod
    def _crew_path(crew_member_id: str, resource: str) -> str:
        return f"/crew-members/{quote(crew_member_id, safe='')}/{resource}"

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def metrics(self) -> list[dict[str, Any]]:
        return self._items("/metrics")

    def evaluations(self, crew_member_id: str, domain: str | None = None) -> list[dict[str, Any]]:
        query = {"domain": domain} if domain else None
        return self._items(self._crew_path(crew_member_id, "evaluations"), query)

    def baselines(self, crew_member_id: str) -> list[dict[str, Any]]:
        return self._items(self._crew_path(crew_member_id, "baselines"))

    def measurements(self, crew_member_id: str) -> list[dict[str, Any]]:
        return self._items(self._crew_path(crew_member_id, "measurements"))
