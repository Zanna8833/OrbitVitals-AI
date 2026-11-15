"""Use invented blobs in temporary bare repositories; create no extra worktrees."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from app.nasa_data.source import REPO_ROOT, load_manifest
from scripts import audit_nasa_history
from scripts.audit_nasa_history import audit_history, authentic_data_json, forbidden_path

SYNTHETIC_BLOB = b"SYNTHETIC UNIT TEST DATA. Not NASA observations.\n"
APPROVED_SYNTHETIC_PATH = "docs/submission-2026/evidence/noor-nine-night-observations.csv"
APPROVED_SYNTHETIC_SHA256 = "24ff8e481f3bd676e27971d72c2d5a4b3d65f74df7b86c5b7e1e887007a5a271"
FRONTEND_SAMPLE_SHA256 = {
    "frontend/docs/samples/measurements.sample.csv": (
        "da572991538502aa682bd075fe6bd5857733633f28f55b3568cba1352b833ec6"
    ),
    "frontend/docs/samples/measurements-long.sample.csv": (
        "dbad79029a53e441c6d6b7fca86744920866612757a09a35269f73db48be9455"
    ),
    "frontend/src/data/import/samples/measurements.sample.csv": (
        "da572991538502aa682bd075fe6bd5857733633f28f55b3568cba1352b833ec6"
    ),
    "frontend/src/data/import/samples/measurements-long.sample.csv": (
        "dbad79029a53e441c6d6b7fca86744920866612757a09a35269f73db48be9455"
    ),
}


def test_shallow_history_cannot_receive_a_complete_history_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(audit_nasa_history, "git", lambda *args, **kwargs: b"true\n")
    with pytest.raises(ValueError, match="complete history"):
        audit_history({"files": []})


def test_public_factual_manifest_notice_and_attributes_are_allowed() -> None:
    prefix = "data/nasa/utmb_campaign_1_actigraphy/"
    for name in ["manifest.json", "NOTICE.md", ".gitattributes"]:
        assert not forbidden_path(prefix + name, set())


def test_unknown_nasa_files_private_caches_and_exports_are_rejected() -> None:
    for name in [
        "data/nasa/utmb_campaign_1_actigraphy/raw/file.txt",
        ".nasa-private/archive/source.txt",
        ".nasa-cache/source.txt",
        "elsewhere/computed-summary.json",
    ]:
        assert forbidden_path(name, set())


def commit_tree(repo: Path, files: dict[str, bytes], parent: str | None = None) -> str:
    """Create invented history fixtures using Git plumbing in a bare test repo."""
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Synthetic Test Author",
        "GIT_AUTHOR_EMAIL": "synthetic@example.invalid",
        "GIT_COMMITTER_NAME": "Synthetic Test Author",
        "GIT_COMMITTER_EMAIL": "synthetic@example.invalid",
    }

    def command(*args: str, content: bytes | None = None) -> bytes:
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            input=content,
            env=environment,
            stderr=subprocess.PIPE,
        )

    def make_tree(contents: dict[str, bytes]) -> bytes:
        entries = []
        directories: dict[str, dict[str, bytes]] = {}
        for name, body in sorted(contents.items()):
            directory, separator, remainder = name.partition("/")
            if separator:
                directories.setdefault(directory, {})[remainder] = body
            else:
                oid = command("hash-object", "-w", "--stdin", content=body).strip()
                entries.append(b"100644 blob " + oid + b"\t" + name.encode() + b"\n")
        for name, children in sorted(directories.items()):
            oid = make_tree(children)
            entries.append(b"040000 tree " + oid + b"\t" + name.encode() + b"\n")
        return command("mktree", content=b"".join(entries)).strip()

    tree = make_tree(files).decode()
    args = ["commit-tree", tree, "-m", "Synthetic history test"]
    if parent is not None:
        args += ["-p", parent]
    return command(*args).decode().strip()


@pytest.fixture
def bare_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "--bare", str(tmp_path)], check=True, capture_output=True)
    return tmp_path


def test_current_reachable_history_has_no_excluded_source_files() -> None:
    manifest, _ = load_manifest()
    result = audit_history(manifest)
    assert result["passed"], result["violations"]
    assert result["commits_checked"] >= 1
    assert result["unique_file_blobs_checked"] >= 1


def test_deleted_historical_data_is_still_detected(bare_repo: Path) -> None:
    first = commit_tree(bare_repo, {"synthetic_source.csv": SYNTHETIC_BLOB})
    clean_tip = commit_tree(bare_repo, {"README.md": b"Synthetic history test\n"}, first)
    manifest = {"files": [{"path": "raw/source.csv", "sha256": "0" * 64}]}
    result = audit_history(manifest, repo=bare_repo, ref=clean_tip)
    assert result["commits_checked"] == 2
    assert not result["passed"]
    assert any(item["path"] == "synthetic_source.csv" for item in result["violations"])


def test_renamed_and_deleted_source_bytes_are_detected(bare_repo: Path) -> None:
    first = commit_tree(bare_repo, {"renamed.bin": SYNTHETIC_BLOB})
    tip = commit_tree(bare_repo, {}, first)
    manifest = {
        "files": [{"path": "raw/source.csv", "sha256": hashlib.sha256(SYNTHETIC_BLOB).hexdigest()}]
    }
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(item["kind"] == "original_source_blob" for item in result["violations"])


def test_same_blob_under_a_forbidden_historical_name_is_detected(bare_repo: Path) -> None:
    first = commit_tree(
        bare_repo, {"allowed.txt": SYNTHETIC_BLOB, "synthetic_source.csv": SYNTHETIC_BLOB}
    )
    tip = commit_tree(bare_repo, {"allowed.txt": SYNTHETIC_BLOB}, first)
    manifest = {"files": [{"path": "raw/source.csv", "sha256": "0" * 64}]}
    assert not audit_history(manifest, repo=bare_repo, ref=tip)["passed"]


def test_individual_json_export_marker_is_detected_even_after_deletion(bare_repo: Path) -> None:
    # Only a format marker is used; this test contains no real or invented person record.
    marker = json.dumps({"data_kind": "authentic_nasa_ground_analog"}).encode()
    first = commit_tree(bare_repo, {"renamed.json": marker})
    tip = commit_tree(bare_repo, {}, first)
    manifest = {"files": [{"path": "raw/source.csv", "sha256": "0" * 64}]}
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert any(item["kind"] == "authentic_data_json" for item in result["violations"])


def test_data_marker_inside_nested_json_is_detected() -> None:
    assert authentic_data_json({"nested": [{"first_record_review_excerpt": {}}]})
    assert not authentic_data_json({"is_synthetic": True, "fixture_notice": "SYNTHETIC TEST DATA"})


@pytest.fixture
def approved_synthetic_evidence() -> bytes:
    """Read existing simulated evidence as exact Git bytes, without CRLF conversion."""
    body = audit_nasa_history.git(REPO_ROOT, "show", f"HEAD:{APPROVED_SYNTHETIC_PATH}")
    capture = json.loads(
        audit_nasa_history.git(
            REPO_ROOT, "show", "HEAD:docs/submission-2026/evidence/capture-manifest.json"
        )
    )
    entry = capture["files"]["noor-nine-night-observations.csv"]
    assert capture["data_kind"] == "simulated"
    assert hashlib.sha256(body).hexdigest() == entry["sha256"] == APPROVED_SYNTHETIC_SHA256
    assert len(body) == entry["bytes"]
    return body


def test_synthetic_csv_requires_exact_approved_digest_and_retains_source_name_checks() -> None:
    assert audit_nasa_history.APPROVED_SYNTHETIC_CSV_SHA256 == {
        APPROVED_SYNTHETIC_PATH: APPROVED_SYNTHETIC_SHA256,
        **FRONTEND_SAMPLE_SHA256,
    }
    assert forbidden_path(APPROVED_SYNTHETIC_PATH, set())
    assert forbidden_path(APPROVED_SYNTHETIC_PATH, set(), content_sha256="0" * 64)
    assert not forbidden_path(
        APPROVED_SYNTHETIC_PATH, set(), content_sha256=APPROVED_SYNTHETIC_SHA256
    )
    assert forbidden_path(
        APPROVED_SYNTHETIC_PATH,
        {"noor-nine-night-observations.csv"},
        content_sha256=APPROVED_SYNTHETIC_SHA256,
    )


def test_approved_synthetic_evidence_passes_in_deleted_history(
    bare_repo: Path, approved_synthetic_evidence: bytes
) -> None:
    first = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence})
    tip = commit_tree(bare_repo, {}, first)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert result["passed"], result["violations"]
    assert result["commits_checked"] == 2


@pytest.mark.parametrize("tip_state", ["modified", "restored", "deleted"])
def test_modified_synthetic_evidence_fails_at_every_history_position(
    bare_repo: Path, approved_synthetic_evidence: bytes, tip_state: str
) -> None:
    first = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence})
    modified = commit_tree(
        bare_repo, {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence + b"\n"}, first
    )
    tip = modified
    if tip_state != "modified":
        files = (
            {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence}
            if tip_state == "restored"
            else {}
        )
        tip = commit_tree(bare_repo, files, modified)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == APPROVED_SYNTHETIC_PATH
        for item in result["violations"]
    )


@pytest.mark.parametrize(
    "name",
    [
        "unrelated.csv",
        "docs/submission-2026/evidence/other.csv",
        "elsewhere/noor-nine-night-observations.csv",
        "docs/submission-2026/evidence/NOOR-nine-night-observations.csv",
    ],
)
def test_approved_bytes_do_not_exempt_any_other_csv_path(
    bare_repo: Path, approved_synthetic_evidence: bytes, name: str
) -> None:
    tip = commit_tree(bare_repo, {name: approved_synthetic_evidence})
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == name for item in result["violations"]
    )


def test_approved_path_cannot_hide_original_source_material(bare_repo: Path) -> None:
    # Invented source bytes exercise the NASA hash protection without copying NASA data.
    tip = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: SYNTHETIC_BLOB})
    manifest = {
        "files": [{"path": "raw/source.csv", "sha256": hashlib.sha256(SYNTHETIC_BLOB).hexdigest()}]
    }
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert {item["kind"] for item in result["violations"]} == {
        "excluded_path",
        "original_source_blob",
    }


def test_approved_digest_never_disables_original_source_hash_protection(
    bare_repo: Path, approved_synthetic_evidence: bytes
) -> None:
    tip = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence})
    manifest = {"files": [{"path": "raw/source.csv", "sha256": APPROVED_SYNTHETIC_SHA256}]}
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(item["kind"] == "original_source_blob" for item in result["violations"])


def test_approved_path_never_disables_authentic_json_export_detection(bare_repo: Path) -> None:
    marker = json.dumps({"data_kind": "authentic_nasa_ground_analog"}).encode()
    tip = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: marker})
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert {item["kind"] for item in result["violations"]} == {
        "excluded_path",
        "authentic_data_json",
    }


def test_modified_capture_manifest_cannot_authorize_different_csv_content(
    bare_repo: Path, approved_synthetic_evidence: bytes
) -> None:
    changed = approved_synthetic_evidence + b"\n"
    capture = {
        "data_kind": "simulated",
        "files": {
            "noor-nine-night-observations.csv": {
                "sha256": hashlib.sha256(changed).hexdigest(),
                "bytes": len(changed),
            }
        },
    }
    tip = commit_tree(
        bare_repo,
        {
            APPROVED_SYNTHETIC_PATH: changed,
            "docs/submission-2026/evidence/capture-manifest.json": json.dumps(capture).encode(),
        },
    )
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(item["kind"] == "excluded_path" for item in result["violations"])


def test_shared_approved_blob_cannot_hide_a_deleted_forbidden_csv_alias(
    bare_repo: Path, approved_synthetic_evidence: bytes
) -> None:
    first = commit_tree(
        bare_repo,
        {
            APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence,
            "unrelated.csv": approved_synthetic_evidence,
        },
    )
    tip = commit_tree(bare_repo, {APPROVED_SYNTHETIC_PATH: approved_synthetic_evidence}, first)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == "unrelated.csv"
        for item in result["violations"]
    )


@pytest.fixture(params=tuple(FRONTEND_SAMPLE_SHA256))
def approved_frontend_sample(request: pytest.FixtureRequest) -> tuple[str, bytes]:
    """Read reviewed invented samples from Git, without working-copy normalization."""
    name = request.param
    body = audit_nasa_history.git(REPO_ROOT, "show", f"HEAD:{name}")
    assert hashlib.sha256(body).hexdigest() == FRONTEND_SAMPLE_SHA256[name]
    long_layout = "measurements-long.sample.csv" in name
    expected_notice = (
        b"# SAMPLE FILE: invented values. One row per reading (long layout)."
        if long_layout
        else b"# SAMPLE FILE: invented values, no real person. One row per day (wide layout)."
    )
    assert body.splitlines()[0] == expected_notice
    assert len(body) == (385 if long_layout else 1033)
    assert b"\r" not in body
    return name, body


def test_frontend_sample_path_requires_its_exact_digest_and_retains_source_name_checks(
    approved_frontend_sample: tuple[str, bytes],
) -> None:
    name, body = approved_frontend_sample
    digest = hashlib.sha256(body).hexdigest()
    assert forbidden_path(name, set())
    assert forbidden_path(name, set(), content_sha256="0" * 64)
    assert not forbidden_path(name, set(), content_sha256=digest)
    assert forbidden_path(name, {Path(name).name}, content_sha256=digest)


def test_approved_frontend_sample_passes_even_when_later_deleted(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes]
) -> None:
    name, body = approved_frontend_sample
    first = commit_tree(bare_repo, {name: body})
    tip = commit_tree(bare_repo, {}, first)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert result["passed"], result["violations"]
    assert result["commits_checked"] == 2


@pytest.mark.parametrize("tip_state", ["modified", "restored", "deleted"])
def test_changed_frontend_sample_fails_at_every_history_position(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes], tip_state: str
) -> None:
    name, body = approved_frontend_sample
    first = commit_tree(bare_repo, {name: body})
    modified = commit_tree(bare_repo, {name: body + b"\n"}, first)
    tip = modified
    if tip_state != "modified":
        tip = commit_tree(bare_repo, {name: body} if tip_state == "restored" else {}, modified)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == name for item in result["violations"]
    )


@pytest.mark.parametrize("replacement", ["crlf", "other_approved_layout"])
def test_frontend_sample_rejects_line_conversion_and_swapped_approved_content(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes], replacement: str
) -> None:
    name, body = approved_frontend_sample
    if replacement == "crlf":
        changed = body.replace(b"\n", b"\r\n")
    else:
        other_name = (
            "frontend/docs/samples/measurements.sample.csv"
            if "measurements-long.sample.csv" in name
            else "frontend/docs/samples/measurements-long.sample.csv"
        )
        changed = audit_nasa_history.git(REPO_ROOT, "show", f"HEAD:{other_name}")
        assert hashlib.sha256(changed).hexdigest() == FRONTEND_SAMPLE_SHA256[other_name]
    assert changed != body
    tip = commit_tree(bare_repo, {name: changed})
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == name for item in result["violations"]
    )


@pytest.mark.parametrize("alias_kind", ["unrelated_csv", "different_directory", "case_change"])
def test_shared_frontend_sample_bytes_do_not_approve_other_paths(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes], alias_kind: str
) -> None:
    name, body = approved_frontend_sample
    alias = {
        "unrelated_csv": "unrelated.csv",
        "different_directory": f"elsewhere/{Path(name).name}",
        "case_change": name.upper(),
    }[alias_kind]
    first = commit_tree(bare_repo, {name: body, alias: body})
    tip = commit_tree(bare_repo, {name: body}, first)
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(
        item["kind"] == "excluded_path" and item["path"] == alias for item in result["violations"]
    )


def test_frontend_sample_approval_never_bypasses_original_source_hash_protection(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes]
) -> None:
    name, body = approved_frontend_sample
    tip = commit_tree(bare_repo, {name: body})
    manifest = {"files": [{"path": "raw/source.csv", "sha256": FRONTEND_SAMPLE_SHA256[name]}]}
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert any(item["kind"] == "original_source_blob" for item in result["violations"])


def test_frontend_sample_path_rejects_original_source_material(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes]
) -> None:
    name, _ = approved_frontend_sample
    tip = commit_tree(bare_repo, {name: SYNTHETIC_BLOB})
    manifest = {
        "files": [{"path": "raw/source.csv", "sha256": hashlib.sha256(SYNTHETIC_BLOB).hexdigest()}]
    }
    result = audit_history(manifest, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert {item["kind"] for item in result["violations"]} == {
        "excluded_path",
        "original_source_blob",
    }


def test_frontend_sample_path_never_bypasses_authentic_json_export_detection(
    bare_repo: Path, approved_frontend_sample: tuple[str, bytes]
) -> None:
    name, _ = approved_frontend_sample
    marker = json.dumps({"data_kind": "authentic_nasa_ground_analog"}).encode()
    tip = commit_tree(bare_repo, {name: marker})
    result = audit_history({"files": []}, repo=bare_repo, ref=tip)
    assert not result["passed"]
    assert {item["kind"] for item in result["violations"]} == {
        "excluded_path",
        "authentic_data_json",
    }
