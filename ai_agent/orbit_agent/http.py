"""Minimal JSON-over-HTTP transport built on the standard library.

Both the backend client and the Ollama client receive a `Transport`, so tests replace it
with an in-memory fake and never open a socket.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class TransportError(Exception):
    """The request could not be completed (connection refused, timeout, bad payload)."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TransportError("Response body is not valid JSON") from error


# (method, url, json_body, timeout_seconds) -> response
Transport = Callable[[str, str, Any | None, float], HttpResponse]


def urllib_transport(method: str, url: str, json_body: Any | None, timeout: float) -> HttpResponse:
    """Send one request. HTTP error statuses are returned, not raised."""
    data = None if json_body is None else json.dumps(json_body).encode("utf-8")
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return HttpResponse(status=response.status, body=response.read())
    except urllib.error.HTTPError as error:
        return HttpResponse(status=error.code, body=error.read())
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise TransportError(f"{method} {url} failed: {error}") from error
