"""Verify the complete MR001G Tilt snapshot without distributing source files.

Scientific files and metadata responses live in an external cache. The public
manifest contains only opaque file IDs, source URLs, digests and reviewed policies.
Acquisition stops on the first failed response or integrity check; there is no
retry, substitute observation, or automatic source-version update.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen

from app.nasa_data.source import (
    REPO_ROOT,
    NasaImportError,
    require_external_destination,
    source_path,
    verify_content,
)

DATASET_ID = "nasa-lsda-mr001g-utmb-campaign-3-tilt"
DATASET_RECORD_ID = "f4a134da-7131-55f8-a0a1-e67d56509432"
DATASET_CATALOG = "MR001G_Campaign_3_Tilt"
EXPERIMENT_RECORD_ID = "09bd2406-b323-5f7c-b0ac-d4585f0015ff"
MISSION_RECORD_ID = "593a6726-8650-551a-8d67-0f03468de92f"
DEFAULT_MANIFEST = REPO_ROOT / "data/nasa/utmb_campaign_3_mr001g_tilt/manifest.json"
DEFAULT_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / ".cache"))
    / "OrbitVitals/nasa/utmb_campaign_3_mr001g_tilt"
)
METADATA_URLS = {
    "dataset_metadata": f"https://nlsp.nasa.gov/api/v1/data/datasets/{DATASET_RECORD_ID}/full",
    "experiment_metadata": f"https://nlsp.nasa.gov/api/v1/data/experiments/{EXPERIMENT_RECORD_ID}/full",
    "mission_metadata": f"https://nlsp.nasa.gov/api/v1/data/missions/{MISSION_RECORD_ID}/full",
}
VARIABLES = ("SBP", "DBP", "HR", "HR (Dinamap)", "AVE HR")


@dataclass(frozen=True)
class Mr001gBundle:
    """Reviewed manifest and verified source bytes, keyed by local relative path."""

    manifest: dict[str, Any]
    manifest_bytes: bytes
    files: dict[str, bytes]


def load_manifest(path: Path = DEFAULT_MANIFEST) -> tuple[dict[str, Any], bytes]:
    """Read trusted provenance; a cached or synthetic manifest cannot replace it."""
    content = path.read_bytes()
    try:
        manifest = json.loads(content)
        if (
            manifest["format_version"] != 1
            or manifest["dataset_id"] != DATASET_ID
            or manifest["dataset_record_id"] != DATASET_RECORD_ID
            or manifest["dataset_catalog"] != DATASET_CATALOG
            or manifest["experiment_id"] != "MR001G"
            or manifest["study_context"] != "terrestrial_head_down_bed_rest_analog"
            or manifest["is_synthetic"] is not False
            or manifest["source_files_distributed"] is not False
            or manifest["expected_observation_files"] != 80
        ):
            raise NasaImportError("Unreviewed MR001G source identity or scope")
        definitions = manifest["variable_definitions"]
        if set(definitions) != set(VARIABLES) or any(
            definition["source_unit"] is not None
            or definition["unit_verification"] != "not_declared_in_reviewed_export"
            for definition in definitions.values()
        ):
            raise NasaImportError("Source unit verification requires a new scientific review")
        entries = manifest["files"]
        observations = [entry for entry in entries if entry["role"] == "observations"]
        metadata = [entry for entry in entries if entry["role"] != "observations"]
        if (
            len(observations) != 80
            or len(metadata) != 3
            or {entry["role"] for entry in metadata} != set(METADATA_URLS)
        ):
            raise NasaImportError(
                "MR001G snapshot must identify 80 CSV files and three metadata files"
            )
        if len({entry["path"] for entry in entries}) != len(entries):
            raise NasaImportError("Duplicate MR001G source paths")
        if len({entry["file_record_id"] for entry in observations}) != 80:
            raise NasaImportError("Duplicate MR001G file identities")
        for entry in entries:
            source_path(path.parent, entry["path"])
            for field, length in (("sha256", 64), ("md5", 32)):
                if not isinstance(entry[field], str) or not re.fullmatch(
                    rf"[0-9a-f]{{{length}}}", entry[field]
                ):
                    raise NasaImportError("Invalid source digest in the MR001G manifest")
            if type(entry["byte_count"]) is not int or not 0 < entry["byte_count"] <= 2_000_000:
                raise NasaImportError("Unsupported MR001G source file size")
            if entry["role"] == "observations":
                fid = entry["file_record_id"]
                if not isinstance(fid, str) or not re.fullmatch(r"[0-9a-f-]{36}", fid):
                    raise NasaImportError("Invalid MR001G file record ID")
                expected_url = f"https://nlsp.nasa.gov/api/v1/files/{fid}/download"
                expected_path = f"raw/{fid}.csv"
                if entry["nasa_metadata_md5"] != entry["md5"] or not re.fullmatch(
                    r"[0-9a-f]{64}", entry["original_filename_sha256"]
                ):
                    raise NasaImportError("Missing NASA file digest or filename provenance")
            else:
                expected_url = METADATA_URLS[entry["role"]]
                expected_path = f"raw/{entry['role']}.json"
                if entry["file_record_id"] is not None or entry["nasa_metadata_md5"] is not None:
                    raise NasaImportError("Unexpected metadata file identity")
            if entry["url"] != expected_url or entry["path"] != expected_path:
                raise NasaImportError("MR001G files must use the reviewed official NASA endpoints")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise NasaImportError("Invalid MR001G provenance manifest") from error
    return manifest, content


def metadata_document(bundle: Mr001gBundle, role: str) -> dict[str, Any]:
    """Decode one verified metadata response, retained only in the local cache."""
    entry = next(item for item in bundle.manifest["files"] if item["role"] == role)
    return json.loads(bundle.files[entry["path"]])


def verify_metadata(bundle: Mr001gBundle) -> None:
    """Check exact file coverage, NASA digests, filename hashes and experiment scope."""
    try:
        dataset = metadata_document(bundle, "dataset_metadata")
        experiment = metadata_document(bundle, "experiment_metadata")["record"]
        mission = metadata_document(bundle, "mission_metadata")["record"]
        if (
            dataset["record"]["id"] != DATASET_RECORD_ID
            or dataset["record"]["dataset_catalog"] != DATASET_CATALOG
            or experiment["id"] != EXPERIMENT_RECORD_ID
            or experiment["experiment_id"] != "MR001G"
            or experiment["Program"] != "Ground"
            or mission["id"] != MISSION_RECORD_ID
            or mission["mission_id"] != "UTMB Campaign 3"
            or mission["program_name"] != "Ground"
        ):
            raise NasaImportError("MR001G experiment or terrestrial campaign identity disagrees")
        collection = dataset["related"]["data_files"]
        records = collection["items"]
        by_id = {record["id"]: record for record in records}
        expected = [item for item in bundle.manifest["files"] if item["role"] == "observations"]
        if not len(records) == len(by_id) == collection["total"] == len(expected):
            raise NasaImportError("Incomplete or duplicated MR001G catalog file coverage")
        if set(by_id) != {item["file_record_id"] for item in expected}:
            raise NasaImportError("MR001G catalog contains a different set of source files")
        for entry in expected:
            record = by_id[entry["file_record_id"]]
            filename_digest = hashlib.sha256(record["__original_file_name"].encode()).hexdigest()
            if (
                record["__file_md5sum"] != entry["nasa_metadata_md5"]
                or record["file_size"] != entry["byte_count"]
                or filename_digest != entry["original_filename_sha256"]
            ):
                raise NasaImportError("MR001G file metadata disagrees with the pinned snapshot")
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise NasaImportError("Incomplete MR001G scientific provenance") from error


def verify_bundle(directory: Path = DEFAULT_DATA_DIR) -> Mr001gBundle:
    """Verify a complete external cache without inferring any missing source files."""
    manifest, content = load_manifest()
    files = {}
    for entry in manifest["files"]:
        path = source_path(directory, entry["path"])
        if not path.is_file():
            raise NasaImportError(
                "MR001G source files are missing; run download into a local cache"
            )
        body = path.read_bytes()
        verify_content(body, entry)
        files[entry["path"]] = body
    bundle = Mr001gBundle(manifest, content, files)
    verify_metadata(bundle)
    return bundle


def download_bundle(destination: Path) -> Mr001gBundle:
    """Download directly from NASA; stop at the first acquisition/integrity failure.

    All bytes and metadata links must pass verification before any new cache file
    is written. Existing differing files are never replaced or silently repaired.
    """
    require_external_destination(destination)
    manifest, content = load_manifest()
    files = {}
    pending = []
    for entry in manifest["files"]:
        path = source_path(destination, entry["path"])
        if path.exists():
            body = path.read_bytes()
        else:
            with urlopen(entry["url"], timeout=30) as response:
                final = urlsplit(response.url)
                if (
                    response.status != 200
                    or final.scheme != "https"
                    or final.netloc != "nlsp.nasa.gov"
                ):
                    raise NasaImportError("MR001G acquisition failed: unexpected NASA response")
                body = response.read(entry["byte_count"] + 1)
        verify_content(body, entry)
        files[entry["path"]] = body
        pending.append((path, body))
    bundle = Mr001gBundle(manifest, content, files)
    verify_metadata(bundle)
    manifest_path = destination / "manifest.json"
    if manifest_path.exists() and manifest_path.read_bytes() != content:
        raise NasaImportError("Refusing to replace a different local MR001G manifest")
    for path, body in [*pending, (manifest_path, content)]:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(body)
    return bundle
