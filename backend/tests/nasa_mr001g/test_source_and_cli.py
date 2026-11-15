"""Use synthetic protocol fixtures to test complete acquisition and private output."""

import io
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

from app.nasa_data.source import REPO_ROOT, NasaImportError
from app.nasa_mr001g import source
from app.nasa_mr001g.cli import main
from app.nasa_mr001g.source import (
    DEFAULT_DATA_DIR,
    DEFAULT_MANIFEST,
    Mr001gBundle,
    download_bundle,
    load_manifest,
    verify_bundle,
    verify_metadata,
)
from tests.nasa_mr001g.support import materialize


def fixture_transport(monkeypatch: pytest.MonkeyPatch, bundle: Mr001gBundle) -> list[str]:
    """Serve invented file bytes; no source request or real observation is involved."""
    responses = {entry["url"]: bundle.files[entry["path"]] for entry in bundle.manifest["files"]}
    calls = []

    class Response(io.BytesIO):
        status = 200

        def __init__(self, url: str) -> None:
            super().__init__(responses[url])
            self.url = url

    def open_fixture(url: str, *, timeout: int) -> Response:
        assert timeout == 30
        calls.append(url)
        return Response(url)

    monkeypatch.setattr(source, "urlopen", open_fixture)
    return calls


def test_only_factual_provenance_is_distributed() -> None:
    manifest, content = load_manifest()
    assert json.loads(content) == manifest
    assert len(manifest["files"]) == 83
    assert sum(entry["role"] == "observations" for entry in manifest["files"]) == 80
    assert manifest["is_synthetic"] is False
    assert manifest["source_files_distributed"] is False
    assert manifest["license"]["redistribution_status"] == "unconfirmed"
    assert all(
        definition["source_unit"] is None
        for definition in manifest["variable_definitions"].values()
    )
    assert not DEFAULT_DATA_DIR.resolve().is_relative_to(REPO_ROOT.resolve())
    assert not (DEFAULT_MANIFEST.parent / "raw").exists()
    assert list(DEFAULT_MANIFEST.parent.glob("*.json")) == [DEFAULT_MANIFEST]
    for entry in manifest["files"]:
        if entry["role"] == "observations":
            assert Path(entry["path"]).stem == entry["file_record_id"]
            assert "original_filename" not in entry
            assert len(entry["original_filename_sha256"]) == 64


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("dataset_id", "wrong"),
        ("experiment_id", "BRSMCF"),
        ("is_synthetic", True),
        ("source_files_distributed", True),
        ("expected_observation_files", 79),
        ("study_context", "in_flight"),
    ],
)
def test_source_identity_and_scope_cannot_silently_change(
    tmp_path: Path, key: str, value: Any
) -> None:
    manifest, _ = load_manifest()
    manifest[key] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError, match="identity or scope"):
        load_manifest(path)


def test_units_cannot_be_promoted_to_verified_without_a_new_review(tmp_path: Path) -> None:
    manifest, _ = load_manifest()
    manifest["variable_definitions"]["SBP"]["source_unit"] = "mmHg"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError, match="scientific review"):
        load_manifest(path)


@pytest.mark.parametrize(
    "change",
    [
        "digest",
        "size",
        "endpoint",
        "filename_hash",
        "duplicate_id",
        "missing_file",
        "missing_metadata",
        "path_escape",
        "md5_disagreement",
    ],
)
def test_manifest_integrity_fields_are_validated(tmp_path: Path, change: str) -> None:
    manifest, _ = load_manifest()
    entries = manifest["files"]
    observation = next(entry for entry in entries if entry["role"] == "observations")
    if change == "digest":
        observation["sha256"] = "bad"
    elif change == "size":
        observation["byte_count"] = 3_000_000
    elif change == "endpoint":
        observation["url"] = "https://example.com/file"
    elif change == "filename_hash":
        observation["original_filename_sha256"] = "bad"
    elif change == "duplicate_id":
        entries[-1] = deepcopy(entries[-2])
    elif change == "missing_file":
        entries.pop()
    elif change == "missing_metadata":
        entries.pop(0)
    elif change == "path_escape":
        observation["path"] = "../outside.csv"
    else:
        observation["nasa_metadata_md5"] = "0" * 32
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError):
        load_manifest(path)


@pytest.mark.parametrize("body", ["{", "{}", "[]"])
def test_malformed_manifest_is_rejected(tmp_path: Path, body: str) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(NasaImportError):
        load_manifest(path)


def test_synthetic_fixture_is_rejected_by_the_production_trust_boundary(
    bundle: Mr001gBundle, tmp_path: Path
) -> None:
    path = tmp_path / "manifest.json"
    path.write_bytes(bundle.manifest_bytes)
    with pytest.raises(NasaImportError, match="identity or scope"):
        load_manifest(path)


def test_verified_cache_does_not_trust_a_replacement_local_manifest(
    trusted_fixture: Mr001gBundle, tmp_path: Path
) -> None:
    materialize(trusted_fixture, tmp_path)
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    assert verify_bundle(tmp_path) == trusted_fixture


def test_missing_cache_is_an_explicit_error(tmp_path: Path) -> None:
    with pytest.raises(NasaImportError, match="run download"):
        verify_bundle(tmp_path)


@pytest.mark.parametrize("change", ["truncate", "edit", "newlines"])
def test_original_byte_changes_are_detected(
    trusted_fixture: Mr001gBundle, tmp_path: Path, change: str
) -> None:
    materialize(trusted_fixture, tmp_path)
    entry = next(
        item for item in trusted_fixture.manifest["files"] if item["role"] == "observations"
    )
    path = tmp_path / entry["path"]
    body = path.read_bytes()
    if change == "truncate":
        changed = body[:-1]
    elif change == "edit":
        changed = body.replace(b"49.25", b"49.26", 1)
    else:
        changed = body.replace(b"\r\n", b"\n")
    path.write_bytes(changed)
    with pytest.raises(NasaImportError, match="mismatch"):
        verify_bundle(tmp_path)
    assert path.read_bytes() == changed


@pytest.mark.parametrize(
    "change",
    [
        "dataset",
        "experiment",
        "mission",
        "ground",
        "coverage",
        "file_id",
        "file_md5",
        "filename",
        "size",
    ],
)
def test_catalog_identity_coverage_units_and_provenance_are_not_inferred(
    bundle: Mr001gBundle, change: str
) -> None:
    files = dict(bundle.files)
    entry = next(item for item in bundle.manifest["files"] if item["role"] == "dataset_metadata")
    doc = json.loads(files[entry["path"]])
    if change == "dataset":
        doc["record"]["dataset_catalog"] = "BRSMCF"
    elif change in ["experiment", "ground", "mission"]:
        role = "mission_metadata" if change == "mission" else "experiment_metadata"
        target = next(item for item in bundle.manifest["files"] if item["role"] == role)
        other = json.loads(files[target["path"]])
        other["record"]["Program" if change == "ground" else "id"] = "wrong"
        files[target["path"]] = json.dumps(other).encode()
    elif change == "coverage":
        doc["related"]["data_files"]["total"] += 1
    else:
        key = {
            "file_id": "id",
            "file_md5": "__file_md5sum",
            "filename": "__original_file_name",
            "size": "file_size",
        }[change]
        doc["related"]["data_files"]["items"][0][key] = "wrong"
    files[entry["path"]] = json.dumps(doc).encode()
    with pytest.raises(NasaImportError):
        verify_metadata(Mr001gBundle(bundle.manifest, bundle.manifest_bytes, files))


def test_download_is_complete_byte_exact_and_idempotent(
    trusted_fixture: Mr001gBundle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fixture_transport(monkeypatch, trusted_fixture)
    assert download_bundle(tmp_path) == trusted_fixture
    assert len(calls) == 5
    assert verify_bundle(tmp_path) == trusted_fixture
    assert (tmp_path / "manifest.json").read_bytes() == trusted_fixture.manifest_bytes
    download_bundle(tmp_path)
    assert len(calls) == 5


@pytest.mark.parametrize(
    "failure", ["connection", "timeout", "revision", "oversize", "status", "redirect", "scheme"]
)
def test_acquisition_stops_on_first_failure_without_partial_files(
    trusted_fixture: Mr001gBundle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    entry = trusted_fixture.manifest["files"][0]
    calls = []

    class Response(io.BytesIO):
        status = 206 if failure == "status" else 200
        url = (
            "https://example.com/"
            if failure == "redirect"
            else "http://nlsp.nasa.gov/"
            if failure == "scheme"
            else entry["url"]
        )

    def fail(url: str, **kwargs) -> Response:
        calls.append(url)
        if failure == "connection":
            raise URLError("Synthetic connection failure")
        if failure == "timeout":
            raise TimeoutError("Synthetic timeout")
        body = trusted_fixture.files[entry["path"]]
        if failure == "revision":
            body = b"x" * len(body)
        if failure == "oversize":
            body += b"oversized"
        return Response(body)

    monkeypatch.setattr(source, "urlopen", fail)
    with pytest.raises((NasaImportError, URLError, TimeoutError)):
        download_bundle(tmp_path)
    assert len(calls) == 1
    assert list(tmp_path.iterdir()) == []


def test_existing_different_manifest_or_file_is_never_replaced(
    trusted_fixture: Mr001gBundle, tmp_path: Path
) -> None:
    materialize(trusted_fixture, tmp_path)
    path = tmp_path / "manifest.json"
    path.write_bytes(b"different synthetic local manifest")
    with pytest.raises(NasaImportError, match="different local"):
        download_bundle(tmp_path)
    assert path.read_bytes() == b"different synthetic local manifest"
    entry = trusted_fixture.manifest["files"][0]
    file = tmp_path / entry["path"]
    file.write_bytes(b"different synthetic source")
    with pytest.raises(NasaImportError, match="mismatch"):
        download_bundle(tmp_path)
    assert file.read_bytes() == b"different synthetic source"


def test_repo_download_destination_is_rejected_before_network_access() -> None:
    with pytest.raises(NasaImportError, match="outside the repository"):
        download_bundle(REPO_ROOT / "data/nasa/not-a-test-cache")


@pytest.mark.parametrize("summary", [False, True])
def test_cli_reports_are_private_and_stdout_has_no_measurements(
    trusted_fixture: Mr001gBundle, tmp_path: Path, capsys: pytest.CaptureFixture[str], summary: bool
) -> None:
    cache = tmp_path / "cache"
    materialize(trusted_fixture, cache)
    output = tmp_path / "private.json"
    args = ["--data-dir", str(cache), "import", "--output", str(output)]
    assert main(args + (["--summary"] if summary else [])) == 0
    captured = capsys.readouterr()
    status = json.loads(captured.out)
    assert status["is_synthetic"] is True
    assert status["finite_reported_values"] == 14
    assert status["source_missing_cells"] == 7
    assert status["unit_status"] == "unverified_for_this_export"
    assert status["canonical_measurements_created"] == 0
    assert "TEST_PERSON" not in captured.out and "49.25" not in captured.out
    assert "statistics" not in captured.out
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["is_synthetic"] is True
    assert ("records" in report) is not summary
    assert main(args) == 2
    assert "Refusing to replace" in capsys.readouterr().err


def test_cli_download_then_verify_uses_only_fixture_transport(
    trusted_fixture: Mr001gBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls = fixture_transport(monkeypatch, trusted_fixture)
    args = ["--data-dir", str(tmp_path)]
    assert main(args + ["download"]) == 0
    assert json.loads(capsys.readouterr().out)["verified_source_files"] == 5
    assert main(args + ["verify"]) == 0
    assert json.loads(capsys.readouterr().out)["is_synthetic"] is True
    assert len(calls) == 5


def test_cli_missing_data_and_repository_output_fail_explicitly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--data-dir", str(tmp_path), "verify"]) == 2
    assert "operation stopped" in capsys.readouterr().err
    path = REPO_ROOT / "data/nasa/never-created.json"
    assert main(["import", "--output", str(path)]) == 2
    assert "outside the repository" in capsys.readouterr().err
    assert not path.exists()


def test_cli_requires_private_output_and_explains_unit_limit(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["import"])
    assert caught.value.code == 2
    assert "--output" in capsys.readouterr().err
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    assert "unverified" in capsys.readouterr().out
