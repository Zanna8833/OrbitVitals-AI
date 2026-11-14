"""CLI discovery, complete replay JSON, diagnostics and reproducibility across processes."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.scenarios import cli as cli_module
from app.scenarios import fixtures, replay_scenario
from app.scenarios.cli import main
from tests.scenarios.test_replay import SCENARIO_IDS

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_human_catalog_lists_every_simulated_case(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list"]) == 0
    output = capsys.readouterr()
    assert "SIMULATED DATA" in output.out
    assert all(scenario_id in output.out for scenario_id in SCENARIO_IDS)
    assert output.err == ""


def test_json_catalog_is_machine_readable_and_explicitly_simulated(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["list", "--json"]) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["data_kind"] == "simulated"
    assert [item["scenario_id"] for item in payload["scenarios"]] == list(SCENARIO_IDS)
    assert output.err == ""


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
@pytest.mark.parametrize("validate", [False, True])
def test_every_individual_cli_replay_prints_real_json_and_passes(
    scenario_id: str,
    validate: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = ["replay", scenario_id, "--json"] + (["--validate"] if validate else [])
    assert main(arguments) == 0
    output = capsys.readouterr()
    payload = json.loads(output.out)
    assert payload["scenario"]["scenario_id"] == scenario_id
    assert payload["all_checks_passed"] is True
    assert payload["data_kind"] == "simulated"
    assert output.err == ""


def test_human_replay_explains_expected_actual_behavior_and_validation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["replay", "progressive_sleep_restriction", "--validate"]) == 0
    output = capsys.readouterr()
    assert "SIMULATED DATA" in output.out
    assert "PASS actual_slope: expected=-15.0; actual=-15.0" in output.out
    assert "Missing duration nights: 2026-11-03, 2026-11-07" in output.out
    assert "Schema validation passed:" in output.out
    assert "None" not in output.out
    assert output.err == ""


def test_all_command_contains_all_five_replays(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["replay", "all", "--json", "--validate"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_kind"] == "simulated"
    assert [item["scenario"]["scenario_id"] for item in payload["replays"]] == list(SCENARIO_IDS)
    assert all(item["all_checks_passed"] for item in payload["replays"])


@pytest.mark.parametrize("arguments", [[], ["unknown"], ["replay", "unknown-scenario"]])
def test_invalid_cli_commands_fail_with_usage_error(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2


def test_help_is_discoverable(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--help"])
    assert error.value.code == 0
    assert "python -m app.scenarios" in capsys.readouterr().out


def test_behavioral_mismatch_is_preserved_in_json_and_returns_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        fixtures,
        "restriction_records",
        lambda: fixtures.sleep_records(
            "flat-cli-counterexample",
            (490,) * 9,
            (92,) * 9,
            missing_nights=frozenset({2, 6}),
        ),
    )
    assert main(["replay", "progressive_sleep_restriction", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["all_checks_passed"] is False
    assert payload["steps"][-1]["outputs"]["sleep_trends"][0]["slope_per_day"] == 0


def test_documented_blocker_is_printed_and_cannot_pass(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = replay_scenario("sensor_quality_failure")
    result.steps[0].blockers = ("An existing interface is unavailable in this test.",)
    result.all_checks_passed = False
    monkeypatch.setattr(cli_module, "replay_scenario", lambda scenario_id: result)
    assert main(["replay", "sensor_quality_failure"]) == 1
    assert "BLOCKER: An existing interface is unavailable" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error", [FileNotFoundError("Missing schema file"), ImportError("Missing jsonschema")]
)
def test_validation_failure_has_no_misleading_json_or_success_exit(
    error: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_validation(*args, **kwargs) -> int:
        raise error

    monkeypatch.setattr(cli_module, "validate_contracts", fail_validation)
    assert main(["replay", "sensor_quality_failure", "--json", "--validate"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "Scenario replay failed" in output.err


def test_module_entry_point_runs_in_a_fresh_python_process() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.scenarios", "replay", "all", "--json", "--validate"],
        cwd=BACKEND_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert len(payload["replays"]) == 5


def test_json_bytes_are_reproducible_across_hash_seeds_and_host_timezones() -> None:
    outputs = []
    for seed, timezone in (("7", "UTC"), ("731", "Pacific/Honolulu")):
        result = subprocess.run(
            [sys.executable, "-m", "app.scenarios", "replay", "all", "--json"],
            cwd=BACKEND_ROOT,
            check=False,
            capture_output=True,
            timeout=30,
            env={**os.environ, "PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONIOENCODING": "utf-8"},
        )
        assert result.returncode == 0, result.stderr
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
