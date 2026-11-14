"""Fresh deterministic snapshots and independence from web or random/time defaults."""

import ast
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.domains.physical_activity import models as activity_models
from app.scenarios import canonical_json, list_scenarios, replay_scenario
from tests.scenarios.test_replay import SCENARIO_IDS


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_identical_replays_have_identical_json_bytes(scenario_id: str) -> None:
    first = replay_scenario(scenario_id)
    second = replay_scenario(scenario_id)
    assert first is not second
    assert first.steps[0] is not second.steps[0]
    assert canonical_json(first) == canonical_json(second)


def test_catalog_mutation_cannot_change_a_later_replay() -> None:
    first = list_scenarios()
    original = first[0].title
    first[0].title = "Changed by caller"
    assert list_scenarios()[0].title == original
    assert replay_scenario(first[0].scenario_id).scenario.title == original


def test_mutating_a_snapshot_cannot_modify_engine_constants_or_later_results() -> None:
    first = replay_scenario("personalized_baseline")
    original = canonical_json(first)
    first.steps[0].outputs.baselines[0].algorithm.name = "caller-mutated-copy"
    first.steps[0].inputs.measurements[0].value = 999
    assert canonical_json(replay_scenario("personalized_baseline")) == original


def test_activity_requests_never_use_random_identifiers_or_wall_clock_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_randomness(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("Replay must explicitly supply evaluation identifiers")

    class NoClock(datetime):
        @classmethod
        def now(cls, tz=None) -> datetime:
            raise AssertionError("Replay must explicitly supply evaluation times")

    monkeypatch.setattr(activity_models, "uuid4", no_randomness)
    monkeypatch.setattr(activity_models, "datetime", NoClock)
    assert replay_scenario("exercise_adherence_change").all_checks_passed
    assert replay_scenario("insufficient_data").all_checks_passed


def test_scenarios_import_only_existing_scientific_interfaces_and_no_http_layer() -> None:
    root = Path(__file__).resolve().parents[2] / "app" / "scenarios"
    forbidden = (
        "fastapi",
        "starlette",
        "uvicorn",
        "app.api",
        "app.main",
        "app.core",
        "app.domains.vitals",
        "app.domains.cognition",
    )
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(
                name == prefix or name.startswith(prefix + ".")
                for name in names
                for prefix in forbidden
            ), path
