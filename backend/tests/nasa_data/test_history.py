"""Use invented blobs in temporary bare repositories; create no extra worktrees."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from app.nasa_data.source import load_manifest
from scripts import audit_nasa_history
from scripts.audit_nasa_history import audit_history, authentic_data_json, forbidden_path

SYNTHETIC_BLOB = b"SYNTHETIC UNIT TEST DATA. Not NASA observations.\n"


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

    entries = []
    for name, body in sorted(files.items()):
        oid = command("hash-object", "-w", "--stdin", content=body).strip()
        entries.append(b"100644 blob " + oid + b"\t" + name.encode() + b"\n")
    tree = command("mktree", content=b"".join(entries)).decode().strip()
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
