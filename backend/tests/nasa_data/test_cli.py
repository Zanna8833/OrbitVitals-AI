"""CLI checks use only synthetic inputs and never print individual observations."""

import json
from pathlib import Path

import pytest

from app.nasa_data.cli import main
from app.nasa_data.source import REPO_ROOT, VerifiedBundle
from tests.nasa_data.support import materialize
from tests.nasa_data.test_source import attach_transport


@pytest.mark.parametrize("summary", [False, True])
def test_cli_writes_private_synthetic_reports_and_only_prints_counts(
    fixture_manifest: VerifiedBundle,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    summary: bool,
) -> None:
    cache = tmp_path / "cache"
    materialize(fixture_manifest, cache)
    report_path = tmp_path / "local-report.json"
    args = ["--data-dir", str(cache), "import", "--output", str(report_path)]
    assert main(args + (["--summary"] if summary else [])) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    status = json.loads(captured.out)
    assert status["is_synthetic"] is True
    assert status["source_record_count"] == 6
    assert status["observed_value_count"] == 9
    assert status["missing_value_count"] == 3
    assert status["statistical_group_count"] == 6
    assert "SYNTHETIC_A" not in captured.out
    assert "statistics" not in captured.out
    private = json.loads(report_path.read_text(encoding="utf-8"))
    assert private["is_synthetic"] is True
    assert "SYNTHETIC UNIT TEST DATA" in private["notice"]
    assert ("records" in private) is not summary
    if not summary:
        assert all(record["is_synthetic"] for record in private["records"])
    original = report_path.read_bytes()
    assert main(args) == 2
    assert report_path.read_bytes() == original


def test_cli_import_requires_an_explicit_report_destination(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["import"])
    assert caught.value.code == 2
    assert "--output" in capsys.readouterr().err


def test_cli_refuses_reports_in_the_checkout(capsys: pytest.CaptureFixture[str]) -> None:
    path = REPO_ROOT / "data/nasa/should-never-be-written.json"
    assert main(["import", "--output", str(path)]) == 2
    assert not path.exists()
    assert "outside the repository" in capsys.readouterr().err


def test_cli_missing_data_is_explicit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--data-dir", str(tmp_path), "verify"]) == 2
    output = capsys.readouterr()
    assert output.out == ""
    assert "download command first" in output.err


def test_cli_download_then_verify_has_no_individual_output(
    fixture_manifest: VerifiedBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = attach_transport(monkeypatch, fixture_manifest)
    assert main(["--data-dir", str(tmp_path), "download"]) == 0
    assert len(calls) == 4
    assert json.loads(capsys.readouterr().out)["is_synthetic"] is True
    assert main(["--data-dir", str(tmp_path), "verify"]) == 0
    verified = json.loads(capsys.readouterr().out)
    assert len(verified["verified_files"]) == 4
    assert verified["is_synthetic"] is True


def test_output_directory_override_is_supported(
    fixture_manifest: VerifiedBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = attach_transport(monkeypatch, fixture_manifest)
    assert main(["download", "--output-dir", str(tmp_path)]) == 0
    assert len(calls) == 4
    assert json.loads(capsys.readouterr().out)["is_synthetic"] is True


def test_help_describes_private_local_reports(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "private local report" in capsys.readouterr().out
