"""SYNTHETIC UNIT TEST DATA: invented cells, not NASA-derived observations.

The public manifest supplies protocol identifiers only. Every scientific value,
subject, note, date, file body, and digest below belongs to this test fixture.
"""

import csv
import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path

from app.nasa_data.actigraphy import HEADERS
from app.nasa_data.source import (
    DATASET_CATALOG,
    DATASET_RECORD_ID,
    VerifiedBundle,
    load_manifest,
)

SYNTHETIC_NOTICE = "SYNTHETIC UNIT TEST DATA. Not NASA observations."


def synthetic_rows() -> list[dict[str, str]]:
    """Invent compact edge cases; do not reproduce any real subject's history."""
    cells = [
        ("1", "SYNTHETIC_A", "PRE_TEST", "2", "1/2/2042", "0:09", "1:17:30", "41.5"),
        ("2", "SYNTHETIC_A", "PRE_TEST", "1", "1/3/2042", "0:11", "2:03:00", "64"),
        ("3", "SYNTHETIC_A", "IN_TEST", "1", "1/4/2042", "NA", "NA", "NA"),
        ("4", "SYNTHETIC_A", "IN_TEST", "2", "NA", "0", "0:00", "0"),
        ("5", "SYNTHETIC_B", "POST_TEST", "0", "2/2/2042", "0:07", "3:21:30", "52.25"),
        ("6", "SYNTHETIC_B", "POST_TEST", "1", "2/3/2042", "", "", "63.75"),
    ]
    return [dict(zip(HEADERS, (*row, SYNTHETIC_NOTICE), strict=True)) for row in cells]


def table_bytes(rows: list[dict[str, str]]) -> bytes:
    """Encode invented CSV test cases entirely in memory."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def synthetic_bundle() -> VerifiedBundle:
    """Model a transport bundle with explicit synthetic provenance and fresh hashes.

    Tests inject this bundle at the trusted-manifest boundary. Production loading
    rejects its synthetic dataset identity, and no real HTTP request is made.
    """
    public, _ = load_manifest()
    manifest = deepcopy(public)
    manifest.update(
        dataset_id="synthetic-adapter-test-fixture",
        is_synthetic=True,
        study_context="synthetic_unit_test",
        title=SYNTHETIC_NOTICE,
        archive="Synthetic test protocol, not a scientific archive",
        population="Invented parser test cases",
        principal_investigator="Synthetic fixture author",
        experiment_doi=None,
        fixture_notice=SYNTHETIC_NOTICE,
    )
    files = {
        "primary_table": table_bytes(synthetic_rows()),
        "query_export": b"SYNTHETIC UNIT TEST DATA\nNot the primary table format\n",
        "readme": (
            SYNTHETIC_NOTICE + "\nSynthetic test unit notation: HH:mm[:ss], percent\n"
        ).encode(),
    }
    entries = []
    for original in public["files"]:
        role = original["role"]
        extension = {"primary_table": "csv", "query_export": "csv", "readme": "txt"}.get(
            role, "json"
        )
        entry = {
            **original,
            "path": f"raw/synthetic_{role}.{extension}",
            "retrieved_at": None,
            "fixture_notice": SYNTHETIC_NOTICE,
        }
        if role != "catalog_metadata":
            update_digests(entry, files[role])
        entries.append(entry)
    metadata = {
        "fixture_notice": SYNTHETIC_NOTICE,
        "record": {"id": DATASET_RECORD_ID, "dataset_catalog": DATASET_CATALOG},
        "related": {
            "data_files": {
                "items": [
                    {
                        "id": item["file_record_id"],
                        "__file_md5sum": item["md5"],
                        "file_size": item["byte_count"],
                        "__original_file_name": Path(item["path"]).name,
                    }
                    for item in entries
                    if item["role"] != "catalog_metadata"
                ]
            },
            "missions": {"items": [{"program_name": "Ground", "fixture_notice": SYNTHETIC_NOTICE}]},
        },
    }
    files["catalog_metadata"] = json.dumps(metadata).encode()
    for entry in entries:
        if entry["role"] == "catalog_metadata":
            update_digests(entry, files["catalog_metadata"])
            entry["nasa_metadata_md5"] = None
    manifest["files"] = entries
    return VerifiedBundle(manifest, json.dumps(manifest).encode(), files)


def update_digests(entry: dict, content: bytes) -> None:
    """Fingerprint invented test bytes, without using an authentic NASA digest."""
    entry["byte_count"] = len(content)
    entry["sha256"] = hashlib.sha256(content).hexdigest()
    entry["md5"] = hashlib.md5(content, usedforsecurity=False).hexdigest()
    entry["nasa_metadata_md5"] = entry["md5"]


def materialize(bundle: VerifiedBundle, directory: Path) -> None:
    """Write only synthetic fixture data into an isolated pytest temporary cache."""
    for entry in bundle.manifest["files"]:
        path = directory / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundle.files[entry["role"]])
