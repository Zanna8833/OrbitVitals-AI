"""Runtime configuration, read from `ORBITVITALS_AGENT_*` environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

ENV_PREFIX = "ORBITVITALS_AGENT_"
SERVICE_NAME = "orbitvitals-agent"
API_PREFIX = "/agent/v1"


@dataclass(frozen=True)
class Settings:
    """Agent settings. Every environment variable is prefixed with `ORBITVITALS_AGENT_`."""

    # Authoritative source of measurements, baselines and evaluations. Read only.
    backend_base_url: str = "http://127.0.0.1:8000/api/v1"
    backend_timeout_seconds: float = 10.0

    # Local model runtime. The agent degrades to a non-generative mode without it.
    ollama_base_url: str = "http://127.0.0.1:11434"
    primary_model: str = "qwen3.5:4b"
    model_timeout_seconds: float = 240.0
    model_context_tokens: int = 8192
    model_max_output_tokens: int = 1400
    model_temperature: float = 0.0
    model_seed: int = 7
    # qwen3.5:4b is packaged in Ollama with a presence penalty of 1.5, which discourages
    # repeating tokens and so works against copying values and identifiers exactly. On
    # the 14 validation scenarios 0 gave fewer rejected sentences than 1.5; the sample is
    # small and the numbers are in the README. This is a text-generation setting, not a
    # scientific parameter.
    model_presence_penalty: float = 0.0
    # Reasoning output ("thinking") is off. With the output budget above, the model
    # spent the whole budget on reasoning and returned no answer; see the README.
    model_think: bool = False
    model_keep_alive: str = "10m"
    # Number of drafts requested before falling back to the non-generative composer.
    max_generation_attempts: int = 2

    # Name of a registered specialist reviewer, or "none". See `orbit_agent.specialist`.
    specialist: str = "none"

    evidence_top_k: int = 3

    # Browsers enforce CORS; the default accepts any localhost port, like the backend.
    cors_allow_origin_regex: str = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build settings from the environment, keeping the default of every unset variable."""
    source = os.environ if environ is None else environ
    defaults = Settings()
    values: dict[str, object] = {}
    for name, default in vars(defaults).items():
        raw = source.get(ENV_PREFIX + name.upper())
        if raw is None or raw == "":
            continue
        try:
            if isinstance(default, bool):
                if raw.lower() not in {"true", "false"}:
                    raise ValueError("expected true or false")
                values[name] = raw.lower() == "true"
            else:
                values[name] = type(default)(raw)
        except ValueError as error:
            raise ValueError(f"{ENV_PREFIX}{name.upper()} has an invalid value: {raw!r}") from error
    return Settings(**values)
