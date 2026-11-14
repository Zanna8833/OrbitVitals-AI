"""Client of a local Ollama server, used only to draft wording.

The model receives no tools and no network access: it gets one prompt and returns one
JSON document constrained by a JSON Schema. Any failure raises `ModelUnavailable`, which
the pipeline turns into the non-generative fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orbit_agent.http import Transport, TransportError, urllib_transport


class ModelUnavailable(Exception):
    """The model runtime cannot be used. `reason` is a stable machine-readable code."""

    def __init__(self, reason: str, detail: str) -> None:
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ChatResult:
    content: str
    duration_ms: float
    load_ms: float | None
    prompt_tokens: int | None
    output_tokens: int | None
    prompt_eval_ms: float | None
    output_eval_ms: float | None
    done_reason: str | None


def _milliseconds(nanoseconds: Any) -> float | None:
    return round(nanoseconds / 1_000_000, 1) if isinstance(nanoseconds, int | float) else None


@dataclass
class OllamaClient:
    base_url: str
    transport: Transport = urllib_transport
    timeout_seconds: float = 240.0
    probe_timeout_seconds: float = 3.0

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def installed_models(self) -> list[str]:
        try:
            response = self.transport(
                "GET", self._url("/api/tags"), None, self.probe_timeout_seconds
            )
            payload = response.json()
        except TransportError as error:
            raise ModelUnavailable("ollama_unreachable", str(error)) from error
        if response.status != 200 or not isinstance(payload, dict):
            raise ModelUnavailable("ollama_unreachable", f"/api/tags returned {response.status}")
        return [entry.get("name", "") for entry in payload.get("models", [])]

    def require_model(self, model: str) -> None:
        installed = self.installed_models()
        if model not in installed and f"{model}:latest" not in installed:
            raise ModelUnavailable("model_not_installed", f"{model} is not installed in Ollama")

    def chat(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        options: dict[str, Any],
        keep_alive: str,
        think: bool = False,
    ) -> ChatResult:
        """Request one schema-constrained completion."""
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": schema,
            "options": options,
            "keep_alive": keep_alive,
            "think": think,
        }
        try:
            response = self.transport("POST", self._url("/api/chat"), body, self.timeout_seconds)
            if response.status == 400 and b"think" in response.body:
                # Models without a reasoning mode reject the `think` field.
                del body["think"]
                response = self.transport(
                    "POST", self._url("/api/chat"), body, self.timeout_seconds
                )
            payload = response.json()
        except TransportError as error:
            raise ModelUnavailable("model_request_failed", str(error)) from error
        if response.status != 200 or not isinstance(payload, dict):
            detail = payload.get("error") if isinstance(payload, dict) else None
            raise ModelUnavailable(
                "model_request_failed", f"/api/chat returned {response.status}: {detail}"
            )
        content = (payload.get("message") or {}).get("content")
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailable("model_returned_no_content", "empty completion")
        return ChatResult(
            content=content,
            duration_ms=_milliseconds(payload.get("total_duration")) or 0.0,
            load_ms=_milliseconds(payload.get("load_duration")),
            prompt_tokens=payload.get("prompt_eval_count"),
            output_tokens=payload.get("eval_count"),
            prompt_eval_ms=_milliseconds(payload.get("prompt_eval_duration")),
            output_eval_ms=_milliseconds(payload.get("eval_duration")),
            done_reason=payload.get("done_reason"),
        )
