"""Live validation of the integrated assistant: Qwen, MedGemma, rag/ and NASA evidence.

Runs against a real backend and a real Ollama. Nothing here is mocked: a scenario counts
as a MedGemma review only if the response records a specialist model run with token
counts returned by Ollama.

Usage, from `ai_agent/` (backend seeded with the Mission Demo Seeder; the NASA evidence
endpoint is optional and reported when absent):

    python -m scripts.validate_integration --backend-url http://127.0.0.1:8000/api/v1 \
        --runs 3 --out integration-report.json

Measures, per scenario: end-to-end time, the model runs (load, prompt and output time
reported by Ollama), routing decisions, the specialist's rag/ evidence, dataset evidence
status and the audit result. Latency is summarised as cold start (models unloaded first),
then median and 95th percentile of the warm runs per class: Qwen answers by answer
profile (conversation, general, brief, full) and Qwen + MedGemma answers. The percentile
uses the nearest-rank method; with a few runs per class it is close to the maximum, and
is reported as such.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from orbit_agent import medgemma  # noqa: F401 - registers the adapter
from orbit_agent.config import Settings, load_settings
from orbit_agent.evidence.store import EvidenceStore
from orbit_agent.http import HttpResponse, urllib_transport
from orbit_agent.medgemma import MedGemmaSpecialist
from orbit_agent.models import AgentResponse, ExplanationRequest, Interpretation
from orbit_agent.pipeline import Agent
from orbit_agent.specialist import SpecialistError, SpecialistRequest
from orbit_agent.specialist_evidence import SpecialistKnowledge

VEGA, NOOR, CHEN = "sim-mission-v1-01", "sim-mission-v1-02", "sim-mission-v1-03"
UNKNOWN_CREW = "sim-mission-v1-09"


@dataclass(frozen=True)
class Scenario:
    name: str
    crew: str
    domain: str | None
    question: str | None
    # What routing should decide. Checked, and reported when it differs.
    expect_profile: str
    expect_specialist: str | tuple[str, ...]
    expect_dataset: str = "not_requested"
    # Expected `generation.specialist.evidence_status`, when the scenario tests it.
    expect_specialist_evidence: str | None = None


SCENARIOS = [
    Scenario("greeting", NOOR, None, "Hello!", "conversation", "conversational_question"),
    Scenario(
        "dashboard_question",
        NOOR,
        None,
        "What does the attention status mean on the dashboard?",
        "general",
        "general_question",
    ),
    Scenario(
        "mission_question", VEGA, None, "How long is the mission?", "general", "general_question"
    ),
    Scenario(
        "general_science",
        NOOR,
        None,
        "How does microgravity affect bones in general?",
        "general",
        "general_question",
    ),
    Scenario(
        "activity_deconditioning_review",
        NOOR,
        "physical_activity",
        "Why is Noor's physical activity flagged, and could it lead to deconditioning?",
        "full",
        "consulted",
    ),
    # The admitted rag/ sections include bone and muscle loss in flight, so this review
    # should receive background evidence from Marco's retrieval.
    Scenario(
        "bone_muscle_review",
        NOOR,
        "physical_activity",
        "Is the drop in Noor's exercise a concern for muscle and bone loss in flight?",
        "full",
        "consulted",
        expect_specialist_evidence="used",
    ),
    Scenario(
        "simple_measurement",
        NOOR,
        "sleep",
        "What was Noor's latest sleep duration?",
        "brief",
        "factual_question",
    ),
    Scenario(
        "crew_b_declining_sleep",
        NOOR,
        "sleep",
        "Why is Crew B's sleep declining compared with the baseline?",
        "full",
        "consulted",
    ),
    Scenario(
        "physiological_review",
        NOOR,
        "sleep",
        "What could this sleep reduction mean physiologically?",
        "full",
        "consulted",
    ),
    Scenario(
        "unreliable_sensor_data",
        CHEN,
        None,
        "Can we trust Chen's readings, and is anything wrong with Chen?",
        "full",
        ("no_physiological_reading", "no_flagged_result"),
    ),
    Scenario(
        "missing_backend_measurements",
        UNKNOWN_CREW,
        None,
        "Why is this crew member's sleep flagged?",
        "full",
        ("no_physiological_reading", "no_flagged_result"),
    ),
    Scenario(
        "nasa_research_question",
        NOOR,
        "sleep",
        "What does NASA bed rest research say about sleep?",
        "general",
        "general_question",
        "ok",
    ),
    Scenario(
        "nasa_unresolved_units",
        VEGA,
        None,
        "Is there NASA research data on heart rate in bed rest tilt tests?",
        "general",
        "general_question",
        "ok",
    ),
    Scenario(
        "unsupported_clinical_question",
        NOOR,
        "sleep",
        "Which medication and dose should Noor take to sleep better?",
        "full",
        "clinical_advice_question",
    ),
    Scenario(
        "crew_identity_vega",
        VEGA,
        "sleep",
        "Is Vega's sleep okay?",
        "full",
        "no_flagged_result",
    ),
]


def _ollama(settings: Settings, method: str, path: str, body: Any = None) -> Any:
    response = urllib_transport(method, settings.ollama_base_url + path, body, 120.0)
    return response.json()


def unload_models(settings: Settings) -> None:
    """Unload both models, so the next request measures a cold start."""
    for model in (settings.primary_model, settings.specialist_model):
        # A model that is not installed is fine here.
        with contextlib.suppress(Exception):
            _ollama(settings, "POST", "/api/generate", {"model": model, "keep_alive": 0})
    time.sleep(2)


def loaded_models(settings: Settings) -> list[dict[str, Any]]:
    """Which models Ollama holds, and how much of each is in GPU memory."""
    try:
        payload = _ollama(settings, "GET", "/api/ps")
    except Exception:  # noqa: BLE001
        return []
    return [
        {
            "name": item.get("name"),
            "size_mb": round((item.get("size") or 0) / 2**20),
            "gpu_mb": round((item.get("size_vram") or 0) / 2**20),
        }
        for item in payload.get("models", [])
    ]


def summarise(scenario: Scenario, response: AgentResponse, wall_ms: float) -> dict[str, Any]:
    info = response.generation.specialist
    runs = [run.model_dump() for run in response.generation.model_runs]
    specialist_runs = [run for run in runs if run["role"] == "specialist"]
    checks = {
        "profile": response.generation.answer_profile == scenario.expect_profile,
        "specialist": info.decision
        in (
            scenario.expect_specialist
            if isinstance(scenario.expect_specialist, tuple)
            else (scenario.expect_specialist,)
        ),
        "dataset": response.dataset_evidence.status == scenario.expect_dataset,
        "crew_identity": response.crew_member_id == scenario.crew,
    }
    if scenario.expect_specialist_evidence is not None:
        checks["specialist_evidence"] = info.evidence_status == scenario.expect_specialist_evidence
    return {
        "scenario": scenario.name,
        "crew": scenario.crew,
        "question": scenario.question,
        "mode": response.generation.mode,
        "fallback_reason": response.generation.fallback_reason,
        "question_kind": response.generation.question_kind,
        "answer_profile": response.generation.answer_profile,
        "specialist_decision": info.decision,
        "specialist_reason": info.reason,
        # A live review is counted only when Ollama reported token counts for it.
        "medgemma_invoked_live": bool(specialist_runs and specialist_runs[0].get("output_tokens")),
        "specialist_findings": [finding.model_dump() for finding in info.findings],
        "specialist_evidence_status": info.evidence_status,
        "specialist_evidence": [
            {"document_id": ref.document_id, "section": ref.section, "similarity": ref.similarity}
            for ref in info.evidence
        ],
        "citations": [citation.evidence_id for citation in response.citations],
        "dataset_status": response.dataset_evidence.status,
        "dataset_items": [
            {
                "dataset_id": item.dataset_id,
                "units": {v.source_column: v.canonical_unit for v in item.variables},
            }
            for item in response.dataset_evidence.items
        ],
        "audit_passed": response.verification.passed,
        "failed_checks": [c.name for c in response.verification.checks if not c.passed],
        "rejected_sentences": len(response.verification.rejected_statements),
        "routing_as_expected": checks,
        "wall_ms": round(wall_ms, 1),
        "timings_ms": response.generation.timings_ms,
        "model_runs": runs,
        "headline": response.headline,
        "interpretations": [
            {"text": i.text, "confidence": i.confidence} for i in response.interpretations
        ],
    }


def run_scenario(agent: Agent, scenario: Scenario) -> dict[str, Any]:
    request = ExplanationRequest(
        crew_member_id=scenario.crew, domain=scenario.domain, question=scenario.question
    )
    started = time.perf_counter()
    response = agent.explain(request)
    result = summarise(scenario, response, (time.perf_counter() - started) * 1000)
    result["models_loaded_after"] = loaded_models(agent.settings)
    return result


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(fraction * len(ordered)) - 1)]


def latency_class(result: dict[str, Any]) -> str | None:
    if result["mode"] != "generative":
        return None
    if result["medgemma_invoked_live"]:
        return "qwen_plus_medgemma"
    return f"qwen_{result['answer_profile']}"


def contradiction_probe(settings: Settings) -> dict[str, Any]:
    """Ask MedGemma directly about one fair and one overstated reading of real facts."""
    agent = Agent(settings=replace(settings, specialist="none"), store=EvidenceStore.load())
    response = agent.explain(
        ExplanationRequest(crew_member_id=NOOR, domain="sleep", mode="deterministic")
    )
    flagged = next(
        fact
        for fact in response.facts
        if fact.kind == "finding"
        and fact.metric == "sleep_duration"
        and fact.data.get("status") == "attention"
    )
    readings = (
        Interpretation(
            id="I1",
            text=(
                "The screen returned 'attention' because it detected a configured pattern of "
                "progressive reduction; a person should review it."
            ),
            origin="model",
            fact_ids=[flagged.id],
            kind="screening_signal",
            confidence="moderate",
        ),
        Interpretation(
            id="I2",
            text=(
                "This proves severe chronic sleep deprivation that is damaging the crew "
                "member's health."
            ),
            origin="model",
            fact_ids=[flagged.id],
            kind="screening_signal",
            confidence="moderate",
        ),
    )
    adapter = MedGemmaSpecialist(settings=settings)
    started = time.perf_counter()
    report = adapter.review(
        SpecialistRequest(
            crew_member_id=NOOR,
            question=None,
            facts=tuple(response.facts),
            interpretations=readings,
        )
    )
    return {
        "readings": {item.id: item.text for item in readings},
        "verdicts": {o.statement_id: [o.verdict, o.comment] for o in report.opinions},
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        "ollama": {k: v for k, v in (report.raw or {}).items() if k != "content"},
    }


def failure_scenarios(settings: Settings) -> dict[str, Any]:
    question = "Why is Crew B's sleep declining compared with the baseline?"
    request = ExplanationRequest(crew_member_id=NOOR, domain="sleep", question=question)
    store = EvidenceStore.load()
    results = {}
    for name, changed in (
        ("medgemma_not_installed", {"specialist_model": "medgemma-not-installed:4b"}),
        ("medgemma_timeout", {"specialist_timeout_seconds": 0.05}),
        ("qwen_unavailable", {"ollama_base_url": "http://127.0.0.1:9"}),
    ):
        agent = Agent(settings=replace(settings, **changed), store=store)
        started = time.perf_counter()
        response = agent.explain(request)
        results[name] = {
            "mode": response.generation.mode,
            "fallback_reason": response.generation.fallback_reason,
            "specialist_decision": response.generation.specialist.decision,
            "specialist_reason": response.generation.specialist.reason,
            "stated_to_operator": [
                u.text for u in response.uncertainties if "specialist review" in u.text
            ],
            "audit_passed": response.verification.passed,
            "wall_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    # Specialist retrieval unavailable: MedGemma still reviews, on the facts alone.
    broken = SpecialistKnowledge(rag_root=Path("rag-not-present"))
    agent = Agent(
        settings=settings,
        store=store,
        specialist=MedGemmaSpecialist(settings=settings, knowledge=broken),
    )
    started = time.perf_counter()
    response = agent.explain(request)
    results["specialist_retrieval_unavailable"] = {
        "mode": response.generation.mode,
        "specialist_decision": response.generation.specialist.decision,
        "specialist_evidence_status": response.generation.specialist.evidence_status,
        "audit_passed": response.verification.passed,
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
    }

    # NASA dataset evidence service failing: the live backend, with every request to
    # /nasa-evidence answered 503 by an injected transport (the endpoint itself is up).
    def failing_evidence(method: str, url: str, body: Any, timeout: float) -> HttpResponse:
        if "/nasa-evidence" in url:
            return HttpResponse(status=503, body=b'{"detail": "unavailable"}')
        return urllib_transport(method, url, body, timeout)

    agent = Agent(settings=settings, store=store, backend_transport=failing_evidence)
    started = time.perf_counter()
    response = agent.explain(
        ExplanationRequest(
            crew_member_id=VEGA,
            question="Is there NASA research data on heart rate in bed rest tilt tests?",
        )
    )
    results["nasa_evidence_unavailable"] = {
        "mode": response.generation.mode,
        "dataset_status": response.dataset_evidence.status,
        "dataset_reason": response.dataset_evidence.reason,
        "audit_passed": response.verification.passed,
        "wall_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backend-url")
    parser.add_argument("--runs", type=int, default=3, help="warm runs per scenario")
    parser.add_argument("--specialist-gpu-layers", type=int)
    parser.add_argument("--scenarios", nargs="+", choices=[s.name for s in SCENARIOS])
    parser.add_argument("--skip-failures", action="store_true")
    parser.add_argument("--out")
    arguments = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    settings = replace(load_settings(), specialist="medgemma", warm_up_on_start=False)
    if arguments.backend_url:
        settings = replace(settings, backend_base_url=arguments.backend_url)
    if arguments.specialist_gpu_layers is not None:
        settings = replace(settings, specialist_gpu_layers=arguments.specialist_gpu_layers)
    scenarios = [s for s in SCENARIOS if not arguments.scenarios or s.name in arguments.scenarios]
    agent = Agent(settings=settings, store=EvidenceStore.load())
    report: dict[str, Any] = {
        "notice": "Software behaviour on SIMULATED crew data. Not a clinical validation.",
        "settings": {
            "primary_model": settings.primary_model,
            "specialist_model": settings.specialist_model,
            "specialist_gpu_layers": settings.specialist_gpu_layers,
        },
        "status": agent.status(),
    }

    # Cold start: both models unloaded, then the first scenario of each latency class.
    unload_models(settings)
    report["cold_start"] = []
    for scenario in (
        scenarios[0],
        *[s for s in scenarios if s.expect_specialist == "consulted"][:1],
    ):
        unload_models(settings)
        result = run_scenario(agent, scenario)
        report["cold_start"].append(result)
        print(f"[cold] {scenario.name}: {result['wall_ms'] / 1000:.1f}s", flush=True)

    report["runs"] = []
    for repetition in range(1, arguments.runs + 1):
        for scenario in scenarios:
            result = run_scenario(agent, scenario)
            result["repetition"] = repetition
            report["runs"].append(result)
            print(
                f"[{repetition}] {scenario.name}: {result['mode']} profile="
                f"{result['answer_profile']} specialist={result['specialist_decision']} "
                f"live={result['medgemma_invoked_live']} "
                f"rag={result['specialist_evidence_status']} dataset={result['dataset_status']} "
                f"audit={result['audit_passed']} routing_ok="
                f"{all(result['routing_as_expected'].values())} {result['wall_ms'] / 1000:.1f}s",
                flush=True,
            )

    latency: dict[str, list[float]] = {}
    for result in report["runs"]:
        category = latency_class(result)
        if category:
            latency.setdefault(category, []).append(result["wall_ms"])
    report["latency_ms"] = {
        category: {
            "runs": len(values),
            "median": round(statistics.median(values), 1),
            "p95_nearest_rank": round(percentile(values, 0.95), 1),
            "min": round(min(values), 1),
            "max": round(max(values), 1),
        }
        for category, values in sorted(latency.items())
    }
    try:
        report["contradiction_probe"] = contradiction_probe(settings)
        print("[probe] verdicts:", report["contradiction_probe"]["verdicts"], flush=True)
    except SpecialistError as error:
        report["contradiction_probe"] = {"error": str(error)}
        print(f"[probe] MedGemma could not be called: {error}", flush=True)
    if not arguments.skip_failures:
        report["failures"] = failure_scenarios(settings)
        for name, result in report["failures"].items():
            print(f"[failure] {name}: {result}", flush=True)

    print("\nLatency (warm runs):")
    for category, row in report["latency_ms"].items():
        print(
            f"  {category:<20} n={row['runs']:<3} median {row['median'] / 1000:.1f}s  "
            f"p95 {row['p95_nearest_rank'] / 1000:.1f}s  range {row['min'] / 1000:.1f}-"
            f"{row['max'] / 1000:.1f}s"
        )
    if arguments.out:
        with open(arguments.out, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"Full report: {arguments.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
