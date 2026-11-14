"""List and replay scientific scenarios with deterministic human or JSON output."""

import argparse
import json
import sys
from collections.abc import Sequence

from app.scenarios.codec import canonical_json
from app.scenarios.models import SIMULATION_NOTICE, ReplayResult
from app.scenarios.replay import list_scenarios, replay_scenario
from app.scenarios.validation import validate_contracts


def _human_replay(result: ReplayResult) -> str:
    lines = [SIMULATION_NOTICE, result.scenario.title, result.scenario.scientific_purpose]
    for step in result.steps:
        lines.extend(("", f"{step.step_id} | {step.as_of.isoformat()}", step.explanation))
        for check in step.checks:
            expected = json.dumps(check.expected, sort_keys=True, allow_nan=False)
            actual = json.dumps(check.actual, sort_keys=True, allow_nan=False)
            lines.append(
                f"  {'PASS' if check.passed else 'FAIL'} {check.check_id}: "
                f"expected={expected}; actual={actual}. {check.description}"
            )
        lines.extend(f"  BLOCKER: {blocker}" for blocker in step.blockers)
    lines.append("")
    lines.append(f"All expected behaviors passed: {str(result.all_checks_passed).lower()}")
    lines.extend(f"Limitation: {limitation}" for limitation in result.scenario.limitations)
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI; exit 1 on behavioral mismatch and 2 on validation/execution errors."""
    catalog = list_scenarios()
    parser = argparse.ArgumentParser(
        prog="python -m app.scenarios",
        description="List or replay deterministic SIMULATED scientific mission scenarios.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list", help="List available simulated scenarios.")
    list_command.add_argument("--json", action="store_true", help="Print the catalog as JSON.")
    replay_command = commands.add_parser("replay", help="Run actual engines on simulated inputs.")
    replay_command.add_argument(
        "scenario", choices=(*[item.scenario_id for item in catalog], "all")
    )
    replay_command.add_argument("--json", action="store_true", help="Print complete replay JSON.")
    replay_command.add_argument(
        "--validate",
        action="store_true",
        help="Check committed contract schemas; requires the existing development dependencies.",
    )
    args = parser.parse_args(argv)
    if args.command == "list":
        if args.json:
            print(
                canonical_json(
                    {"data_kind": "simulated", "notice": SIMULATION_NOTICE, "scenarios": catalog}
                ),
                end="",
            )
        else:
            print(SIMULATION_NOTICE)
            for info in catalog:
                print(f"{info.scenario_id}: {info.title}\n  {info.scientific_purpose}")
        return 0

    names = [item.scenario_id for item in catalog] if args.scenario == "all" else [args.scenario]
    try:
        results = [replay_scenario(name) for name in names]
        counts = [validate_contracts(result) for result in results] if args.validate else []
    except (ValueError, TypeError, OSError, ImportError) as error:
        print(f"Scenario replay failed: {error}", file=sys.stderr)
        return 2
    if args.json:
        output = (
            results[0]
            if args.scenario != "all"
            else {
                "data_kind": "simulated",
                "notice": SIMULATION_NOTICE,
                "replays": results,
            }
        )
        print(canonical_json(output), end="")
    else:
        print("\n\n".join(_human_replay(result) for result in results))
        if args.validate:
            print(f"Schema validation passed: {sum(counts)} embedded shared contract payloads.")
    return 0 if all(result.all_checks_passed for result in results) else 1
