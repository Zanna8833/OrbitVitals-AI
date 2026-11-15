"""CLI failures and an actual Uvicorn-to-urllib HTTP end-to-end presentation smoke test."""

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest
from fastapi.testclient import TestClient

from app.demo_seed import cli
from app.demo_seed import client as client_module
from app.demo_seed.client import HttpApi, SeedError
from app.demo_seed.dataset import DASHBOARD_METRICS, build_manifest, build_plan
from tests.demo_seed.support import TestApi

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_offline_manifest_does_not_connect_to_an_api(monkeypatch, capsys) -> None:
    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Manifest generation must remain offline")

    monkeypatch.setattr(cli, "HttpApi", unexpected_connection)
    assert cli.main(["manifest"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out) == build_manifest()
    assert output.err == ""


@pytest.mark.parametrize("arguments", [[], ["unknown"], ["seed", "--batch-size", "not-an-integer"]])
def test_invalid_cli_usage_has_exit_code_two(arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(arguments)
    assert error.value.code == 2


def test_cli_help_is_discoverable(capsys) -> None:
    with pytest.raises(SystemExit) as error:
        cli.main(["--help"])
    assert error.value.code == 0
    assert "SYNTHETIC" in capsys.readouterr().out


@pytest.mark.parametrize(
    "url",
    [
        "https://outside.example/api/v1",
        "file:///api/v1",
        "http://localhost:8000",
        "http://user:password@localhost:8000/api/v1",
        "http://localhost:8000/api/v1?extra=1",
        "http://localhost:8000/api/v1#fragment",
    ],
)
def test_invalid_or_nonlocal_targets_are_rejected(url: str) -> None:
    with pytest.raises(SeedError, match="loopback"):
        HttpApi(url)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_nonfinite_or_nonpositive_timeouts_are_rejected(timeout: float) -> None:
    with pytest.raises(SeedError, match="timeout"):
        HttpApi("http://localhost:8000/api/v1", timeout)


def test_connection_failure_has_stderr_and_no_misleading_json(monkeypatch, capsys) -> None:
    def fail(*args, **kwargs):
        raise URLError("simulated unavailable local server")

    monkeypatch.setattr(client_module, "urlopen", fail)
    assert cli.main(["seed", "--json"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "unavailable local server" in output.err


def test_http_conflict_preserves_server_error_details(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise HTTPError(
            "http://localhost/api/v1",
            409,
            "Conflict",
            None,
            io.BytesIO(b'{"detail":"synthetic ID conflict"}'),
        )

    monkeypatch.setattr(client_module, "urlopen", fail)
    with pytest.raises(SeedError, match="HTTP 409.*synthetic ID conflict"):
        HttpApi("http://localhost:8000/api/v1").request("POST", "/measurements", {})


@pytest.mark.parametrize("payload", [b"not json", b"[]"])
def test_invalid_server_json_is_an_actionable_error(payload: bytes, monkeypatch) -> None:
    monkeypatch.setattr(client_module, "urlopen", lambda *args, **kwargs: io.BytesIO(payload))
    with pytest.raises(SeedError):
        HttpApi("http://localhost:8000/api/v1").request("GET", "/health")


def test_cli_report_contains_actual_computed_resources(
    api_client: TestClient, monkeypatch, capsys, tmp_path
) -> None:
    api = TestApi(api_client)
    monkeypatch.setattr(cli, "HttpApi", lambda *args: api)
    path = tmp_path / "mission-demo-report.json"
    assert cli.main(["seed", "--json", "--report", str(path)]) == 0
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert path.read_text(encoding="utf-8") == output.out
    assert report["all_checks_passed"] is True
    assert output.err == ""


def test_cli_human_output_is_concise_and_labeled(
    api_client: TestClient, monkeypatch, capsys
) -> None:
    monkeypatch.setattr(cli, "HttpApi", lambda *args: TestApi(api_client))
    assert cli.main(["seed"]) == 0
    output = capsys.readouterr()
    assert "SIMULATED DATA" in output.out
    assert "sim-mission-v1-03" in output.out
    assert "sleep-day-14=insufficient_data" in output.out
    assert len(output.out.splitlines()) < 15
    assert output.err == ""


def test_cli_mismatch_retains_real_outputs_and_returns_one(
    api_client: TestClient, monkeypatch, capsys
) -> None:
    from app.scenarios import fixtures

    monkeypatch.setattr(
        fixtures,
        "restriction_records",
        lambda: fixtures.sleep_records(
            "flat-cli-counterexample", (490,) * 9, (92,) * 9, missing_nights=frozenset({2, 6})
        ),
    )
    monkeypatch.setattr(cli, "HttpApi", lambda *args: TestApi(api_client))
    assert cli.main(["seed", "--json"]) == 1
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["all_checks_passed"] is False
    assert "no result was replaced" in output.err
    final = next(
        item for item in report["crews"][1]["evaluations"] if item["checkpoint"] == "sleep-day-09"
    )
    assert final["result"]["status"] == "nominal"


def test_real_http_cli_smoke_seed_twice_and_retrieve(free_tcp_port: int, tmp_path) -> None:
    """Exercise the user-facing CLI against a real, isolated server process and socket."""
    base_url = f"http://127.0.0.1:{free_tcp_port}/api/v1"
    log_path = tmp_path / "uvicorn.log"
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("ORBITVITALS_")
    }
    # Ignore local .env/config for this test server while retaining the real routes,
    # scientific engines, repository, JSON parsing and urllib transport.
    server_code = (
        "import uvicorn; from app.main import create_app; from app.core.config import Settings; "
        f"uvicorn.run(create_app(Settings(_env_file=None)), host='127.0.0.1', port={free_tcp_port})"
    )
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-c", server_code],
            cwd=BACKEND_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            ready_by = time.monotonic() + 10
            while True:
                if process.poll() is not None:
                    pytest.fail(log_path.read_text(encoding="utf-8"))
                try:
                    with urlopen(base_url + "/health", timeout=0.5) as response:
                        assert json.load(response)["status"] == "ok"
                    break
                except OSError:
                    if time.monotonic() >= ready_by:
                        pytest.fail("The isolated HTTP smoke-test server did not become ready")
                    time.sleep(0.05)
            commands = [
                sys.executable,
                "-m",
                "app.demo_seed",
                "seed",
                "--base-url",
                base_url,
                "--json",
            ]
            results = []
            for _ in range(2):
                completed = subprocess.run(
                    commands,
                    cwd=BACKEND_ROOT,
                    capture_output=True,
                    check=False,
                    timeout=45,
                    env=environment,
                )
                assert completed.returncode == 0, completed.stderr.decode("utf-8")
                results.append(completed.stdout)
            assert results[0] == results[1]
            report = json.loads(results[0])
            assert report["all_checks_passed"] is True
            for crew in report["crews"]:
                root = f"{base_url}/crew-members/{crew['crew_member_id']}"
                for resource, count in (
                    ("measurements", crew["stored_measurement_count"]),
                    ("baselines", 12),
                    ("evaluations", len(crew["evaluations"])),
                ):
                    with urlopen(root + "/" + resource, timeout=5) as response:
                        assert len(json.load(response)["items"]) == count
                expected = next(
                    item for item in build_plan() if item.crew_member_id == crew["crew_member_id"]
                )
                for metric in DASHBOARD_METRICS:
                    with urlopen(
                        root + "/measurements?metric=" + metric.value, timeout=5
                    ) as response:
                        items = json.load(response)["items"]
                    desired = [
                        item.model_dump(mode="json")
                        for item in expected.measurements
                        if item.metric == metric
                    ]
                    actual = {item["measurement_id"]: item for item in items}
                    assert (
                        len(items)
                        == len(desired)
                        == (23 if crew["crew_member_id"].endswith("03") else 28)
                    )
                    for item in desired:
                        stored = actual[item["measurement_id"]]
                        assert {
                            key: value for key, value in stored.items() if key != "data_quality"
                        } == {key: value for key, value in item.items() if key != "data_quality"}
                        assert stored["source"] == "simulated"
                        assert stored["data_quality"]["algorithm"]["name"] == "data_quality"
                        assert stored["data_quality"]["status"] == "acceptable"
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
