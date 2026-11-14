"""Verify the provenance protocol using synthetic bytes and an offline transport."""

import io
import json
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

from app.nasa_data import source
from app.nasa_data.source import (
    DEFAULT_DATA_DIR,
    DEFAULT_MANIFEST_PATH,
    REPO_ROOT,
    NasaImportError,
    VerifiedBundle,
    download_bundle,
    load_manifest,
    source_path,
    verify_bundle,
    verify_content,
    verify_metadata,
)
from tests.nasa_data.support import materialize


def attach_transport(monkeypatch: pytest.MonkeyPatch, bundle: VerifiedBundle) -> list[str]:
    """Return synthetic HTTP bodies; no NASA request or observation is used."""
    calls = []
    responses = {item["url"]: bundle.files[item["role"]] for item in bundle.manifest["files"]}

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


def test_public_manifest_is_available_without_any_original_files() -> None:
    manifest, content = load_manifest()
    assert json.loads(content) == manifest
    assert manifest["source_files_distributed"] is False
    assert manifest["is_synthetic"] is False
    assert manifest["license"]["redistribution_status"] == "unconfirmed"
    assert not DEFAULT_DATA_DIR.resolve().is_relative_to(REPO_ROOT.resolve())
    assert list(DEFAULT_MANIFEST_PATH.parent.glob("*.json")) == [DEFAULT_MANIFEST_PATH]
    assert not (DEFAULT_MANIFEST_PATH.parent / "raw").exists()
    assert {entry["role"] for entry in manifest["files"]} == source.EXPECTED_ROLES


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("is_synthetic", True),
        ("source_files_distributed", True),
        ("study_context", "in_flight"),
        ("dataset_id", "other"),
    ],
)
def test_unreviewed_manifest_identity_is_rejected(tmp_path: Path, key: str, value: Any) -> None:
    manifest, _ = load_manifest()
    manifest[key] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError, match="ground-study"):
        load_manifest(path)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", "invalid"),
        ("md5", "invalid"),
        ("nasa_metadata_md5", "0" * 32),
        ("byte_count", True),
        ("byte_count", 3_000_000),
        ("url", "https://example.com/file"),
    ],
)
def test_manifest_digests_sizes_and_endpoints_are_validated(
    tmp_path: Path, field: str, value: Any
) -> None:
    manifest, _ = load_manifest()
    manifest["files"][0][field] = value
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError):
        load_manifest(path)


@pytest.mark.parametrize(
    "kind", ["missing_roles", "duplicate_paths", "invalid_json", "missing_keys"]
)
def test_incomplete_or_duplicate_provenance_fails(tmp_path: Path, kind: str) -> None:
    manifest, _ = load_manifest()
    if kind == "missing_roles":
        manifest["files"][1]["role"] = manifest["files"][0]["role"]
    elif kind == "duplicate_paths":
        manifest["files"][1]["path"] = manifest["files"][0]["path"]
    elif kind == "missing_keys":
        manifest = {}
    path = tmp_path / "manifest.json"
    path.write_text("{" if kind == "invalid_json" else json.dumps(manifest), encoding="utf-8")
    with pytest.raises(NasaImportError):
        load_manifest(path)


def test_synthetic_manifest_cannot_enter_the_real_trust_boundary(
    bundle: VerifiedBundle, tmp_path: Path
) -> None:
    path = tmp_path / "manifest.json"
    path.write_bytes(bundle.manifest_bytes)
    with pytest.raises(NasaImportError, match="ground-study"):
        load_manifest(path)


@pytest.mark.parametrize(
    "name", ["../outside.csv", "raw/../outside.csv", "C:/outside.csv", "raw\\x", "raw/C:x"]
)
def test_paths_stay_inside_the_local_raw_cache(tmp_path: Path, name: str) -> None:
    with pytest.raises(NasaImportError, match="path"):
        source_path(tmp_path, name)


def test_missing_local_data_has_an_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(NasaImportError, match="download command"):
        verify_bundle(tmp_path)


def test_synthetic_bytes_and_catalog_linkage_are_verified(
    fixture_manifest: VerifiedBundle, tmp_path: Path
) -> None:
    materialize(fixture_manifest, tmp_path)
    verified = verify_bundle(tmp_path)
    assert verified == fixture_manifest
    assert verified.manifest["is_synthetic"] is True
    # A cache-local manifest never replaces the trusted checkout manifest.
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    assert verify_bundle(tmp_path) == fixture_manifest


@pytest.mark.parametrize("change", ["truncate", "same_size_edit", "newlines"])
def test_changed_source_bytes_are_never_repaired(
    fixture_manifest: VerifiedBundle, tmp_path: Path, change: str
) -> None:
    materialize(fixture_manifest, tmp_path)
    path = tmp_path / fixture_manifest.entry("primary_table")["path"]
    content = path.read_bytes()
    if change == "truncate":
        changed = content[:-1]
    elif change == "same_size_edit":
        changed = content.replace(b"1:17:30", b"1:18:30", 1)
    else:
        changed = content.replace(b"\r\n", b"\n")
    path.write_bytes(changed)
    with pytest.raises(NasaImportError, match="mismatch"):
        verify_bundle(tmp_path)
    assert path.read_bytes() == changed


def test_nasa_md5_disagreement_is_reported(bundle: VerifiedBundle) -> None:
    entry = {**bundle.entry("readme"), "nasa_metadata_md5": "0" * 32}
    with pytest.raises(NasaImportError, match="MD5 mismatch"):
        verify_content(bundle.files["readme"], entry)


@pytest.mark.parametrize(
    "change", ["dataset", "ground_context", "md5", "size", "filename", "missing_fields"]
)
def test_metadata_must_agree_with_file_identity(bundle: VerifiedBundle, change: str) -> None:
    metadata = json.loads(bundle.files["catalog_metadata"])
    if change == "dataset":
        metadata["record"]["id"] = "wrong"
    elif change == "ground_context":
        metadata["related"]["missions"]["items"][0]["program_name"] = "Space"
    elif change == "missing_fields":
        metadata = {}
    else:
        key = {"md5": "__file_md5sum", "size": "file_size", "filename": "__original_file_name"}[
            change
        ]
        metadata["related"]["data_files"]["items"][0][key] = "wrong"
    altered = VerifiedBundle(
        bundle.manifest,
        bundle.manifest_bytes,
        {**bundle.files, "catalog_metadata": json.dumps(metadata).encode()},
    )
    with pytest.raises(NasaImportError):
        verify_metadata(altered)


def test_download_is_byte_exact_and_idempotent(
    fixture_manifest: VerifiedBundle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = attach_transport(monkeypatch, fixture_manifest)
    assert download_bundle(tmp_path) == fixture_manifest
    assert len(calls) == 4
    assert (tmp_path / "manifest.json").read_bytes() == fixture_manifest.manifest_bytes
    assert verify_bundle(tmp_path) == fixture_manifest
    download_bundle(tmp_path)
    assert len(calls) == 4


@pytest.mark.parametrize(
    "failure", ["connection", "revision", "oversize", "redirect", "http_status", "http_scheme"]
)
def test_failed_transport_writes_no_partial_bundle(
    fixture_manifest: VerifiedBundle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    first = fixture_manifest.manifest["files"][0]

    class Response(io.BytesIO):
        status = 206 if failure == "http_status" else 200
        url = (
            "https://example.com/"
            if failure == "redirect"
            else "http://nlsp.nasa.gov/"
            if failure == "http_scheme"
            else first["url"]
        )

    def fail(*args: Any, **kwargs: Any) -> Response:
        if failure == "connection":
            raise URLError("Synthetic test connection failure")
        content = fixture_manifest.files[first["role"]]
        if failure == "revision":
            content = b"x" * len(content)
        elif failure == "oversize":
            content += b"oversize"
        return Response(content)

    monkeypatch.setattr(source, "urlopen", fail)
    with pytest.raises((NasaImportError, URLError)):
        download_bundle(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_metadata_failure_is_checked_before_writing(
    fixture_manifest: VerifiedBundle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = deepcopy(fixture_manifest.manifest)
    bad["files"][1]["file_record_id"] = "unknown-test-file"
    monkeypatch.setattr(source, "load_manifest", lambda: (bad, json.dumps(bad).encode()))
    attach_transport(
        monkeypatch, VerifiedBundle(bad, json.dumps(bad).encode(), fixture_manifest.files)
    )
    with pytest.raises(NasaImportError, match="provenance metadata"):
        download_bundle(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_download_refuses_repository_destinations_before_network_access() -> None:
    with pytest.raises(NasaImportError, match="outside the repository"):
        download_bundle(REPO_ROOT / "data/nasa/not-a-real-test-cache")


def test_existing_different_file_or_manifest_is_not_replaced(
    fixture_manifest: VerifiedBundle, tmp_path: Path
) -> None:
    materialize(fixture_manifest, tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(b"different local manifest")
    with pytest.raises(NasaImportError, match="different local manifest"):
        download_bundle(tmp_path)
    assert manifest_path.read_bytes() == b"different local manifest"
    path = tmp_path / fixture_manifest.entry("primary_table")["path"]
    path.write_bytes(b"different local content")
    with pytest.raises(NasaImportError, match="mismatch"):
        download_bundle(tmp_path)
    assert path.read_bytes() == b"different local content"
