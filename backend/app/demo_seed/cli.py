"""Seed a running local API or print a reproducible offline presentation manifest."""

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from app.demo_seed.client import HttpApi, SeedError, seed_api
from app.demo_seed.dataset import build_manifest
from app.scenarios.codec import canonical_json
from app.scenarios.models import SIMULATION_NOTICE


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.demo_seed",
        description="Populate a local API with explicitly SYNTHETIC presentation histories.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("manifest", help="Print the deterministic offline crew/scenario manifest.")
    seed = commands.add_parser(
        "seed", help="Ingest synthetic data, compute real results, and verify retrieval."
    )
    seed.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    seed.add_argument("--batch-size", type=int, default=500)
    seed.add_argument("--timeout", type=float, default=30)
    seed.add_argument("--json", action="store_true", help="Print complete actual results as JSON.")
    seed.add_argument(
        "--report", type=Path, help="Also save complete actual results/checks as UTF-8 JSON."
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "manifest":
            print(canonical_json(build_manifest()), end="")
            return 0
        report = seed_api(HttpApi(args.base_url, args.timeout), batch_size=args.batch_size)
        serialized = canonical_json(report)
        if args.report is not None:
            args.report.write_text(serialized, encoding="utf-8")
        if args.json:
            print(serialized, end="")
        else:
            print(SIMULATION_NOTICE)
            print(f"Dataset: {report['manifest']['dataset_id']}")
            for crew in report["crews"]:
                print(
                    f"{crew['crew_member_id']}: {crew['stored_measurement_count']} measurements, "
                    f"{len(crew['baselines'])} baselines"
                )
                print(
                    "  "
                    + ", ".join(
                        f"{item['checkpoint']}={item['result']['status']}"
                        for item in crew["evaluations"]
                    )
                )
            print(f"All demonstration checks passed: {report['all_checks_passed']}")
            if args.report is not None:
                print(f"Full computed results: {args.report}")
        if not report["all_checks_passed"]:
            print(
                "Seeding completed, but computed demonstration behaviors differ. "
                "See actual results/checks; no result was replaced.",
                file=sys.stderr,
            )
            return 1
        return 0
    except (SeedError, ValidationError, OSError, ValueError) as error:
        print(f"Mission demo seeding failed: {error}", file=sys.stderr)
        return 2
