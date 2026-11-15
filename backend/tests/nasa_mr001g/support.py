"""SYNTHETIC UNIT TEST DATA: no authentic participant observations or derivatives."""

import csv
import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from app.nasa_mr001g.source import (
    DATASET_CATALOG,
    DATASET_RECORD_ID,
    EXPERIMENT_RECORD_ID,
    MISSION_RECORD_ID,
    Mr001gBundle,
    load_manifest,
)

NOTICE = "SYNTHETIC UNIT TEST DATA. Not NASA observations."
HEADERS = [
    "ID",
    "Campaign",
    "Subject",
    "Test_Phase",
    "BR_Day",
    "Date",
    "Min",
    "Stage",
    "SBP",
    "DBP",
    "HR",
    "AVE HR",
    "Comments",
]
SECOND_HEADERS = [
    "ID",
    "Campaign",
    "Subject",
    "Date",
    "Test_Phase",
    "BR_Day",
    "Minute",
    "Stage",
    "HR (Dinamap)",
    "SBP",
]


def invented_rows() -> list[dict[str, str]]:
    """Invent reversed pressures, zeros, missing context, invalid numbers and padding."""
    cells = [
        (
            "1",
            "SYNTHETIC_A",
            "TEST_PERSON_A",
            "PRE_TEST",
            "2",
            "1/2/2050",
            "1",
            "Supine",
            "68",
            "92",
            "49.25",
            "44.5",
            NOTICE,
        ),
        (
            "",
            "SYNTHETIC_A",
            "TEST_PERSON_A",
            "PRE_TEST",
            "2",
            "1/2/2050",
            "2",
            "Tilt ",
            "0",
            "0",
            "0",
            "NA",
            NOTICE,
        ),
        ("1", "", "", "", "", "", "1/2", "Tilt", "NA", "", "not_a_number", "50", NOTICE),
        tuple("" for _ in HEADERS),
        (
            "4",
            "SYNTHETIC_A",
            "TEST_PERSON_A",
            "PRE_TEST",
            "2",
            "1/2/2050",
            "3",
            "Supine",
            "112",
            "75",
            "65.5",
            "63.5",
            NOTICE,
        ),
    ]
    return [dict(zip(HEADERS, row, strict=True)) for row in cells]


def second_rows() -> list[dict[str, str]]:
    """Invent a distinct header layout with structurally absent channels."""
    cells = [
        (
            "1",
            "SYNTHETIC_B",
            "TEST_PERSON_B",
            "1/5/2050",
            "POST_TEST",
            "0",
            "1",
            "Recovery",
            "55.5",
            "99.5",
        ),
        (
            "2",
            "SYNTHETIC_B",
            "TEST_PERSON_B",
            "2/30/2050",
            "POST_TEST",
            "1",
            "2",
            "Recovery",
            "1e999",
            "NaN",
        ),
    ]
    return [dict(zip(SECOND_HEADERS, row, strict=True)) for row in cells]


def csv_bytes(rows: list[dict[str, str]], headers: list[str] = HEADERS) -> bytes:
    """Encode only invented fixture values, with no source CSV stored in the repo."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def fingerprint(entry: dict[str, Any], body: bytes) -> None:
    """Compute fixture digests without reusing any authentic scientific file digest."""
    entry.update(
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        md5=hashlib.md5(body, usedforsecurity=False).hexdigest(),
    )
    entry["nasa_metadata_md5"] = entry["md5"] if entry["role"] == "observations" else None


def synthetic_bundle() -> Mr001gBundle:
    """Build a visibly synthetic protocol fixture, rejected by production loading."""
    public, _ = load_manifest()
    manifest = deepcopy(public)
    manifest.update(
        dataset_id="synthetic-mr001g-fixture",
        is_synthetic=True,
        study_context="synthetic_unit_test",
        fixture_notice=NOTICE,
        expected_observation_files=2,
        catalog_narrative_end_date="2050-01-04",
        title=NOTICE,
    )
    entries = [deepcopy(item) for item in public["files"] if item["role"] != "observations"]
    files = {}
    source_info = []
    for ordinal, body in enumerate(
        [csv_bytes(invented_rows()), csv_bytes(second_rows(), SECOND_HEADERS)], start=1
    ):
        fid = f"00000000-0000-0000-0000-{ordinal:012d}"
        filename = f"SYNTHETIC_TABLE_{ordinal}.csv"
        entry = {
            "role": "observations",
            "path": f"raw/{fid}.csv",
            "url": f"https://nlsp.nasa.gov/api/v1/files/{fid}/download",
            "file_record_id": fid,
            "original_filename_sha256": hashlib.sha256(filename.encode()).hexdigest(),
            "fixture_notice": NOTICE,
        }
        fingerprint(entry, body)
        entries.append(entry)
        files[entry["path"]] = body
        source_info.append(
            {
                "id": fid,
                "__file_md5sum": entry["md5"],
                "file_size": len(body),
                "__original_file_name": filename,
            }
        )
    metadata = {
        "dataset_metadata": {
            "fixture_notice": NOTICE,
            "record": {"id": DATASET_RECORD_ID, "dataset_catalog": DATASET_CATALOG},
            "related": {"data_files": {"total": 2, "items": source_info}},
        },
        "experiment_metadata": {
            "fixture_notice": NOTICE,
            "record": {"id": EXPERIMENT_RECORD_ID, "experiment_id": "MR001G", "Program": "Ground"},
        },
        "mission_metadata": {
            "fixture_notice": NOTICE,
            "record": {
                "id": MISSION_RECORD_ID,
                "mission_id": "UTMB Campaign 3",
                "program_name": "Ground",
            },
        },
    }
    for entry in entries:
        if entry["role"] == "observations":
            continue
        body = json.dumps(metadata[entry["role"]]).encode()
        fingerprint(entry, body)
        files[entry["path"]] = body
    manifest["files"] = entries
    return Mr001gBundle(manifest, json.dumps(manifest).encode(), files)


def materialize(bundle: Mr001gBundle, directory: Path) -> None:
    """Write synthetic test bytes only into pytest's temporary cache."""
    for entry in bundle.manifest["files"]:
        path = directory / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bundle.files[entry["path"]])
