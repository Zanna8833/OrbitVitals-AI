"""Audit every reachable Git tree and blob for excluded NASA source material.

This is read-only. It checks source digests, historical file paths, and recognizable
authentic-data JSON exports. It does not inspect unrelated private branch objects.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from app.nasa_data.source import REPO_ROOT, load_manifest

NASA_DIRECTORY = "data/nasa/utmb_campaign_1_actigraphy/"
ALLOWED_NASA_FILES = {"manifest.json", ".gitattributes", "notice.md"}
EXCLUDED_EXPORTS = {"computed-summary.json", "source-investigation.json"}
# Reviewed simulated evidence and invented frontend import examples, exact Git bytes.
# Noor is pinned to its capture manifest; frontend examples originated in 13660fa.
# Manifest edits, matching basenames and other CSVs do not grant approval.
APPROVED_SYNTHETIC_CSV_SHA256 = {
    "docs/submission-2026/evidence/noor-nine-night-observations.csv": (
        "24ff8e481f3bd676e27971d72c2d5a4b3d65f74df7b86c5b7e1e887007a5a271"
    ),
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


def git(repo: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    """Read Git objects without a shell or working-tree mutations."""
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], input=input_bytes, stderr=subprocess.PIPE
    )


def forbidden_path(name: str, source_names: set[str], *, content_sha256: str | None = None) -> bool:
    """Reject excluded paths; only exact approved synthetic CSV bytes may pass."""
    normalized = name.lower()
    path = PurePosixPath(normalized)
    return (
        normalized.startswith((".nasa-private/", ".nasa-cache/"))
        or (
            path.suffix == ".csv"
            and not (
                name in APPROVED_SYNTHETIC_CSV_SHA256
                and content_sha256 == APPROVED_SYNTHETIC_CSV_SHA256[name]
            )
        )
        or path.name in source_names | EXCLUDED_EXPORTS
        or (
            normalized.startswith(NASA_DIRECTORY)
            and normalized[len(NASA_DIRECTORY) :] not in ALLOWED_NASA_FILES
        )
    )


def authentic_data_json(value: Any) -> bool:
    """Recognize local authentic-data reports and individual observation excerpts."""
    if isinstance(value, dict):
        return (
            value.get("data_kind") == "authentic_nasa_ground_analog"
            or value.get("report_kind") == "authentic_nasa_import_with_descriptive_statistics"
            or "first_record_review_excerpt" in value
            or (
                isinstance(value.get("record"), dict)
                and "related" in value
                and value["record"].get("dataset_catalog") == "BRSMACT_Campaign_1_Actigraphy"
            )
            or any(authentic_data_json(item) for item in value.values())
        )
    return isinstance(value, list) and any(authentic_data_json(item) for item in value)


def audit_history(
    manifest: dict[str, Any], *, repo: Path = REPO_ROOT, ref: str = "HEAD"
) -> dict[str, Any]:
    """Inspect all reachable commits, unique root trees and unique file blobs.

    Path inspection uses every historical tree, rather than the first path assigned
    to an object by rev-list. Thus a forbidden historical path is still detected
    when the same blob also appears under an allowed name or disappears at HEAD.
    Every historical blob at an approved synthetic CSV path must match its
    pinned digest; a later restoration or deletion cannot hide modified content.
    """
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Full history audit requires a repository with complete history")
    commit = (
        git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}").decode().strip()
    )
    commits = git(repo, "rev-list", commit).splitlines()
    trees = set(git(repo, "log", "--format=%T", commit).splitlines())
    source_names = {PurePosixPath(item["path"]).name.lower() for item in manifest["files"]}
    source_hashes = {item["sha256"] for item in manifest["files"]}
    blob_ids: set[bytes] = set()
    synthetic_candidates: dict[bytes, list[dict[str, str]]] = {}
    violations = []
    for tree in sorted(trees):
        for entry in git(repo, "ls-tree", "-r", "-z", tree.decode()).split(b"\0"):
            if not entry:
                continue
            fields, name_bytes = entry.split(b"\t", 1)
            _, kind, oid = fields.split()
            name = name_bytes.decode("utf-8")
            if forbidden_path(name, source_names):
                violation = {"kind": "excluded_path", "path": name, "tree": tree.decode()}
                if name in APPROVED_SYNTHETIC_CSV_SHA256 and kind == b"blob":
                    synthetic_candidates.setdefault(oid, []).append(violation)
                else:
                    violations.append(violation)
            if kind == b"blob":
                blob_ids.add(oid)
    request = b"\n".join(sorted(blob_ids)) + b"\n"
    batch = git(repo, "cat-file", "--batch", input_bytes=request) if blob_ids else b""
    cursor = 0
    for expected_oid in sorted(blob_ids):
        end = batch.index(b"\n", cursor)
        oid, kind, size = batch[cursor:end].split()
        if oid != expected_oid or kind != b"blob":
            raise ValueError("Unexpected Git batch response")
        cursor = end + 1
        body = batch[cursor : cursor + int(size)]
        cursor += int(size) + 1
        digest = hashlib.sha256(body).hexdigest()
        for candidate in synthetic_candidates.get(oid, []):
            if forbidden_path(candidate["path"], source_names, content_sha256=digest):
                violations.append(candidate)
        # Synthetic path approval never bypasses original-source or JSON checks.
        if digest in source_hashes:
            violations.append({"kind": "original_source_blob", "object": oid.decode()})
        try:
            document = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            continue
        if authentic_data_json(document):
            violations.append({"kind": "authentic_data_json", "object": oid.decode()})
    return {
        "commit": commit,
        "commits_checked": len(commits),
        "unique_root_trees_checked": len(trees),
        "unique_file_blobs_checked": len(blob_ids),
        "violations": violations,
        "passed": not violations,
    }


def main(argv: list[str] | None = None) -> int:
    """Print metadata-only audit results for a single explicitly selected history."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args(argv)
    try:
        manifest, _ = load_manifest()
        report = audit_history(manifest, ref=args.ref)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"NASA history audit failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
