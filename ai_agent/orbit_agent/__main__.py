"""Command-line entry point: `python -m orbit_agent --help`."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace

from orbit_agent import medgemma  # noqa: F401 - registers the "medgemma" specialist
from orbit_agent.backend_client import BackendUnavailable
from orbit_agent.config import load_settings
from orbit_agent.evidence.store import EvidenceStore
from orbit_agent.models import ExplanationRequest
from orbit_agent.pipeline import Agent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m orbit_agent",
        description="OrbitVitals AI agent proof of concept. Not a medical device.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    explain = commands.add_parser("explain", help="explain the stored results of a crew member")
    explain.add_argument("--crew", required=True, help="crew member identifier")
    explain.add_argument(
        "--domain", choices=["sleep", "physical_activity", "vital_signs", "nutrition"]
    )
    explain.add_argument("--question", help="optional question from the operator")
    explain.add_argument(
        "--deterministic", action="store_true", help="never call a model (rule-based output)"
    )
    explain.add_argument("--backend-url", help="override ORBITVITALS_AGENT_BACKEND_BASE_URL")
    explain.add_argument("--out", help="write the JSON response to this file instead of stdout")

    explain.add_argument(
        "--specialist", help="override ORBITVITALS_AGENT_SPECIALIST (for example: medgemma)"
    )

    evidence = commands.add_parser("evidence", help="search the local evidence corpus")
    evidence.add_argument("query")
    evidence.add_argument("--limit", type=int, default=5)

    commands.add_parser("status", help="report which dependencies are reachable")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    settings = load_settings()
    if getattr(arguments, "backend_url", None):
        settings = replace(settings, backend_base_url=arguments.backend_url)
    if getattr(arguments, "specialist", None):
        settings = replace(settings, specialist=arguments.specialist)
    agent = Agent(settings=settings, store=EvidenceStore.load())

    if arguments.command == "status":
        print(json.dumps(agent.status(), indent=2))
        return 0
    if arguments.command == "evidence":
        results = agent.store.search(arguments.query, top_k=arguments.limit)
        for item in results:
            passage = item.passage
            print(f"[{passage.evidence_id}] score={item.score} {passage.document_title}")
            print(f"  Source: {passage.source_label}, {passage.url}")
            print(f"  OrbitVitals summary (not the source's text): {passage.text}\n")
        if not results:
            print("No passage in the local corpus matches this query.")
        return 0

    request = ExplanationRequest(
        crew_member_id=arguments.crew,
        domain=arguments.domain,
        question=arguments.question,
        mode="deterministic" if arguments.deterministic else "auto",
    )
    try:
        response = agent.explain(request)
    except BackendUnavailable as error:
        print(f"The OrbitVitals backend could not be read: {error}", file=sys.stderr)
        return 2
    rendered = response.model_dump_json(indent=2)
    if arguments.out:
        with open(arguments.out, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
        print(
            f"mode={response.generation.mode} verification_passed={response.verification.passed} "
            f"-> {arguments.out}"
        )
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
