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
    # Google Gemma 3 4B (Ollama tag `gemma3:4b`). Until the final release the primary model
    # was Alibaba Qwen 3.5 4B (`qwen3.5:4b`); it was replaced after the NASA Space Apps
    # organizers advised against open-source technology from Chinese companies. Any other
    # Ollama tag can still be selected with ORBITVITALS_AGENT_PRIMARY_MODEL.
    primary_model: str = "gemma3:4b"
    model_timeout_seconds: float = 240.0
    model_context_tokens: int = 8192
    model_max_output_tokens: int = 1400
    model_temperature: float = 0.0
    model_seed: int = 7
    # A presence penalty discourages repeating tokens and so works against copying values
    # and identifiers exactly. With the earlier primary model (qwen3.5:4b, packaged with
    # 1.5), 0 gave fewer rejected sentences on the 14 validation scenarios; the sample is
    # small and the numbers are in the README. This is a text-generation setting, not a
    # scientific parameter.
    model_presence_penalty: float = 0.0
    # Reasoning output ("thinking") is off. Gemma 3 has no reasoning mode; the Ollama
    # client drops the field when a model rejects it (`orbit_agent.llm`).
    model_think: bool = False
    model_keep_alive: str = "10m"
    # Number of drafts requested before falling back to the non-generative composer.
    max_generation_attempts: int = 2

    # Name of a registered specialist reviewer, or "none". See `orbit_agent.specialist`.
    # "medgemma" selects `orbit_agent.medgemma` (MedGemma 1.5 4B through Ollama).
    specialist: str = "none"
    specialist_model: str = "medgemma1.5:4b"
    specialist_timeout_seconds: float = 90.0
    # The review prompt holds only the readings and the facts they cite.
    specialist_context_tokens: int = 4096
    specialist_max_output_tokens: int = 400
    # "0" unloads the specialist right after each review. Measured on the 8 GB GPU
    # (INTEGRATION.md): with little free GPU memory, keeping it loaded ("10m") slowed every
    # Qwen answer 2-4x (Qwen-only 3.4-30.1 s, reviews median 34.5 s), while unloading
    # cost about 3-5 s per review (Qwen-only 5.0-7.7 s, reviews median 18.4 s). With ample
    # memory "10m" saves those seconds; reliability was preferred.
    specialist_keep_alive: str = "0"
    # Layers of the specialist placed on the GPU (Ollama `num_gpu`): -1 lets Ollama decide,
    # 0 runs it on the CPU so that the primary model keeps the GPU. Chosen from the
    # measurements in the README, not assumed.
    specialist_gpu_layers: int = -1
    # Specialist background evidence from rag/ (Marco's retrieval over reviewed sections).
    specialist_knowledge: bool = True
    specialist_knowledge_top_k: int = 2
    # Minimum embedding similarity of a section to the review query. Measured on the
    # admitted sections: unrelated queries scored at most 0.52 and loosely related ones
    # at most 0.60, relevant ones 0.75-0.80 (README). An engineering choice; it equals the
    # cause-matching threshold of rag/src/assistant/knowledge.py.
    specialist_knowledge_min_similarity: float = 0.70

    evidence_top_k: int = 3

    # Output budget of a brief draft (a question that asks for stored values). A brief draft
    # has fewer sentences, which is what makes it faster; see `orbit_agent.routing`.
    brief_max_output_tokens: int = 500
    # Output budgets of a conversational reply and of an evidence-led general answer.
    conversation_max_output_tokens: int = 200
    general_max_output_tokens: int = 800

    # Earlier chat turns sent by the client (`ExplanationRequest.conversation`) that are
    # used as context. The agent keeps no history of its own.
    conversation_max_turns: int = 8
    # Names used for each simulated crew member (dashboard label, seeder name). A history
    # turn or a model sentence naming another crew member than the requested one is not
    # used. Format: "id=Name|Name;id=Name". Empty disables the check (crew IDs are still
    # checked). Values of the Mission Demo Seeder and frontend/src/config.ts.
    crew_aliases: str = (
        "sim-mission-v1-01=Crew A|Astronaut A|Vega;"
        "sim-mission-v1-02=Crew B|Astronaut B|Noor;"
        "sim-mission-v1-03=Crew C|Astronaut C|Chen"
    )
    # Reply in Italian when the operator writes in Italian. When false, Italian is used
    # only when asked for explicitly (request `language`, or "rispondi in italiano").
    reply_language_detection: bool = True

    # NASA Dataset Evidence Adapter (`GET {backend}/nasa-evidence`), ground-analogue
    # research context. Off when false; absent endpoints are reported, never invented.
    nasa_dataset_evidence: bool = True

    # Load the primary model when the HTTP service starts, so the first request does not
    # pay the model loading time. Failures are ignored: the agent still starts.
    warm_up_on_start: bool = True

    # Directory of the server-owned explanation jobs (`orbit_agent.jobs`): one JSON file per
    # request, so an answer survives the browser closing. Relative to the working directory.
    jobs_dir: str = ".agent-jobs"

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
