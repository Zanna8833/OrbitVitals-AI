"""Acquire and verify authentic NASA files without distributing their contents.

Only the factual provenance manifest is shipped. Scientific files are downloaded
directly from NASA into an external local cache and never normalized or repaired.
Public access is established; redistribution rights remain unconfirmed.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen

DATASET_ID = "nasa-lsda-brsmact-utmb-campaign-1"
DATASET_RECORD_ID = "e26501eb-7d7a-5012-8c8e-c5bdb3eecaf6"
DATASET_CATALOG = "BRSMACT_Campaign_1_Actigraphy"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST_PATH = REPO_ROOT / "data/nasa/utmb_campaign_1_actigraphy/manifest.json"
DEFAULT_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    / "OrbitVitals"
    / "nasa"
    / "utmb_campaign_1_actigraphy"
)
EXPECTED_ROLES = {"primary_table", "query_export", "readme", "catalog_metadata"}


class NasaImportError(ValueError):
    """An unverified source, unsafe output path, or unsupported representation."""


@dataclass(frozen=True)
class VerifiedBundle:
    """Verified local source bytes and the separately shipped provenance manifest."""

    manifest: dict[str, Any]
    manifest_bytes: bytes
    files: dict[str, bytes]

    def entry(self, role: str) -> dict[str, Any]:
        """Return the single acquisition entry for a known file role."""
        return next(item for item in self.manifest["files"] if item["role"] == role)


def require_external_destination(path: Path) -> None:
    """Keep newly downloaded data and generated reports outside this checkout."""
    if path.resolve().is_relative_to(REPO_ROOT.resolve()):
        raise NasaImportError("Choose a local data/report destination outside the repository")


def source_path(directory: Path, name: str) -> Path:
    """Resolve a manifest file strictly inside the local cache's raw directory."""
    relative = PurePosixPath(name)
    if (
        len(relative.parts) != 2
        or relative.parts[0] != "raw"
        or "\\" in name
        or ":" in name
        or relative.parts[1] in {".", ".."}
    ):
        raise NasaImportError(f"Unsupported source path: {name}")
    path = directory / Path(*relative.parts)
    if not path.resolve().is_relative_to(directory.resolve()):
        raise NasaImportError(f"Source path escapes the local cache: {name}")
    return path


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> tuple[dict[str, Any], bytes]:
    """Read trusted provenance from the checkout, without requiring NASA data."""
    content = path.read_bytes()
    try:
        manifest = json.loads(content)
        if (
            manifest["format_version"] != 2
            or manifest["dataset_id"] != DATASET_ID
            or manifest["dataset_record_id"] != DATASET_RECORD_ID
            or manifest["dataset_catalog"] != DATASET_CATALOG
            or manifest["is_synthetic"] is not False
            or manifest["source_files_distributed"] is not False
            or manifest["study_context"] != "terrestrial_bed_rest_analog"
        ):
            raise NasaImportError(
                "The manifest does not identify the reviewed ground-study dataset"
            )
        entries = manifest["files"]
        if len(entries) != 4 or {item["role"] for item in entries} != EXPECTED_ROLES:
            raise NasaImportError("The manifest must identify exactly four reviewed source files")
        if len({item["path"] for item in entries}) != len(entries):
            raise NasaImportError("Duplicate source paths in the manifest")
        for item in entries:
            source_path(path.parent, item["path"])
            for field, width in (("sha256", 64), ("md5", 32)):
                if not isinstance(item[field], str) or not re.fullmatch(
                    rf"[0-9a-f]{{{width}}}", item[field]
                ):
                    raise NasaImportError(f"Invalid {field} digest in the manifest")
            if item["nasa_metadata_md5"] is not None and item["nasa_metadata_md5"] != item["md5"]:
                raise NasaImportError("NASA MD5 disagrees with the acquisition digest")
            parts = urlsplit(item["url"])
            expected_path = (
                f"/api/v1/data/datasets/{DATASET_RECORD_ID}/full"
                if item["role"] == "catalog_metadata"
                else f"/api/v1/files/{item['file_record_id']}/download"
            )
            if (
                parts.scheme != "https"
                or parts.netloc != "nlsp.nasa.gov"
                or parts.path != expected_path
                or parts.query
                or parts.fragment
            ):
                raise NasaImportError(
                    "Source URLs must identify the reviewed public NASA endpoints"
                )
            if type(item["byte_count"]) is not int or not 0 < item["byte_count"] <= 2_000_000:
                raise NasaImportError("Unsupported source file size")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise NasaImportError("Invalid provenance manifest") from error
    return manifest, content


def verify_content(content: bytes, entry: dict[str, Any]) -> None:
    """Reject truncation, revisions and corruption, preserving original bytes."""
    if len(content) != entry["byte_count"]:
        raise NasaImportError(f"Byte count mismatch: {entry['path']}")
    if hashlib.sha256(content).hexdigest() != entry["sha256"]:
        raise NasaImportError(f"SHA-256 mismatch: {entry['path']}")
    md5 = hashlib.md5(content, usedforsecurity=False).hexdigest()
    if md5 != entry["md5"] or entry["nasa_metadata_md5"] not in {None, md5}:
        raise NasaImportError(f"MD5 mismatch: {entry['path']}")


def verify_metadata(bundle: VerifiedBundle) -> None:
    """Cross-check the downloaded catalog, file identities and ground-study context."""
    try:
        metadata = json.loads(bundle.files["catalog_metadata"])
        record = metadata["record"]
        if record["id"] != DATASET_RECORD_ID or record["dataset_catalog"] != DATASET_CATALOG:
            raise NasaImportError("Catalog response does not identify the reviewed dataset")
        nasa_files = {item["id"]: item for item in metadata["related"]["data_files"]["items"]}
        for entry in bundle.manifest["files"]:
            if entry["role"] == "catalog_metadata":
                continue
            nasa_file = nasa_files[entry["file_record_id"]]
            if (
                nasa_file["__file_md5sum"] != entry["nasa_metadata_md5"]
                or nasa_file["file_size"] != entry["byte_count"]
                or nasa_file["__original_file_name"] != PurePosixPath(entry["path"]).name
            ):
                raise NasaImportError("Provenance manifest disagrees with NASA file metadata")
        missions = metadata["related"]["missions"]["items"]
        if len(missions) != 1 or missions[0]["program_name"] != "Ground":
            raise NasaImportError("Source metadata does not establish the ground-study context")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise NasaImportError("Incomplete NASA provenance metadata") from error


def verify_bundle(directory: Path = DEFAULT_DATA_DIR) -> VerifiedBundle:
    """Verify a separately acquired cache against the trusted public manifest."""
    manifest, manifest_bytes = load_manifest()
    files = {}
    for entry in manifest["files"]:
        path = source_path(directory, entry["path"])
        if not path.is_file():
            raise NasaImportError("Local source files are missing; run the download command first")
        content = path.read_bytes()
        verify_content(content, entry)
        files[entry["role"]] = content
    bundle = VerifiedBundle(manifest, manifest_bytes, files)
    verify_metadata(bundle)
    return bundle


def download_bundle(destination: Path) -> VerifiedBundle:
    """Acquire pinned files directly from NASA into an external local directory.

    Every response and its catalog linkage are checked before any file is written.
    Existing identical files are reused; different files are never replaced. The
    copied manifest retains the original snapshot dates, not a new acquisition date.
    """
    require_external_destination(destination)
    manifest, manifest_bytes = load_manifest()
    files = {}
    pending = []
    for entry in manifest["files"]:
        path = source_path(destination, entry["path"])
        if path.exists():
            content = path.read_bytes()
        else:
            with urlopen(entry["url"], timeout=30) as response:
                final_url = urlsplit(response.url)
                if (
                    response.status != 200
                    or final_url.scheme != "https"
                    or final_url.netloc != "nlsp.nasa.gov"
                ):
                    raise NasaImportError("Unexpected public NASA download response")
                content = response.read(entry["byte_count"] + 1)
        verify_content(content, entry)
        files[entry["role"]] = content
        pending.append((path, content))
    bundle = VerifiedBundle(manifest, manifest_bytes, files)
    verify_metadata(bundle)
    manifest_path = destination / "manifest.json"
    if manifest_path.exists() and manifest_path.read_bytes() != manifest_bytes:
        raise NasaImportError("Refusing to replace a different local manifest")
    for path, content in [*pending, (manifest_path, manifest_bytes)]:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
    return bundle
