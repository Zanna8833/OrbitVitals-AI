"""Preserve MR001G source records and describe explicitly unverified source scales.

No units, subject identities, stages, timestamps, or absent measurements are
inferred. Candidate metric names do not imply a verified canonical mapping.
Pressure-pair checks annotate the original values and never swap or remove them.
"""

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from app.algorithms import robust_statistics
from app.nasa_data.actigraphy import calendar_date
from app.nasa_data.source import NasaImportError
from app.nasa_mr001g.source import (
    DEFAULT_DATA_DIR,
    VARIABLES,
    Mr001gBundle,
    metadata_document,
    verify_bundle,
)

VERSION = "1.0.0"
CONTEXT_COLUMNS = ("Campaign", "Subject", "Test_Phase", "BR_Day", "Date")
REQUIRED_COLUMNS = {"ID", *CONTEXT_COLUMNS, "Stage"}
ALLOWED_COLUMNS = (
    REQUIRED_COLUMNS
    | set(VARIABLES)
    | {"Min", "Minute", "AVE SV", "AVG CO", "TPR", "Comments", "Unnamed: 14"}
)
MISSING_TOKENS = {"", "NA"}


def numeric_cell(text: str) -> dict[str, Any]:
    """Decode one finite numeric cell without changing its original scale or string."""
    token = text.strip()
    if token in MISSING_TOKENS:
        return {"source_text": text, "value": None, "status": "source_missing"}
    try:
        number = Decimal(token)
        if not number.is_finite() or not re.fullmatch(
            r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", token
        ):
            raise ValueError("Not a finite source number")
        value = float(number)
        if not Decimal.from_float(value).is_finite() or (value == 0 and number != 0):
            raise ValueError("Source number exceeds nonzero finite float representation")
    except (InvalidOperation, ValueError, OverflowError):
        return {"source_text": text, "value": None, "status": "invalid_numeric"}
    return {"source_text": text, "value": value, "status": "finite_reported_value"}


def parse_table(
    content: bytes, entry: dict[str, Any], manifest: dict[str, Any]
) -> list[dict[str, Any]]:
    """Retain every CSV data record, including padding and incomplete context.

    Physical blank lines are not CSV data records. Comma-delimited empty records
    are preserved. Structurally absent columns never become invented observations.
    """
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    columns = reader.fieldnames or []
    if (
        len(columns) != len(set(columns))
        or not set(columns).issuperset(REQUIRED_COLUMNS)
        or not set(columns) <= ALLOWED_COLUMNS
        or len({"Min", "Minute"} & set(columns)) != 1
        or not set(VARIABLES) & set(columns)
    ):
        raise NasaImportError("Unreviewed MR001G CSV layout; no columns were silently dropped")
    time_column = "Min" if "Min" in columns else "Minute"
    end_date = date.fromisoformat(manifest["catalog_narrative_end_date"])
    rows = []
    seen_ids: set[str] = set()
    for ordinal, raw in enumerate(reader, 1):
        if None in raw or any(not isinstance(value, str) for value in raw.values()):
            raise NasaImportError("Malformed MR001G CSV record width")
        issues = []
        empty = all(not value.strip() for value in raw.values())
        for column in (*CONTEXT_COLUMNS, "Stage"):
            if raw[column].strip() in MISSING_TOKENS:
                issues.append("missing_context:" + column)
        identifier = raw["ID"]
        if identifier:
            if not re.fullmatch(r"[0-9]+", identifier):
                issues.append("invalid_source_row_id")
            if identifier in seen_ids:
                issues.append("duplicate_source_row_id")
            seen_ids.add(identifier)
        else:
            issues.append("missing_source_row_id")
        try:
            observed_date = calendar_date(raw["Date"])
        except NasaImportError:
            observed_date = None
            issues.append("invalid_calendar_date")
        if observed_date is not None and observed_date > end_date:
            issues.append("date_after_catalog_narrative_end")
        stage = raw["Stage"].strip()
        if stage != raw["Stage"]:
            issues.append("stage_whitespace_normalized_for_grouping")
        if stage and stage not in {"Supine", "Tilt"}:
            issues.append("unrecognized_source_stage")
        if raw["Test_Phase"] and raw["Test_Phase"] not in {"PRE_TEST", "IN_TEST", "POST_TEST"}:
            issues.append("unrecognized_source_phase")
        step = numeric_cell(raw[time_column])
        if step["status"] != "finite_reported_value":
            issues.append("relative_step:" + step["status"])
        cells = {}
        for variable in VARIABLES:
            if variable not in raw:
                continue
            cell = numeric_cell(raw[variable])
            definition = manifest["variable_definitions"][variable]
            cells[variable] = {
                **cell,
                "source_column": variable,
                "unit": None,
                "unit_status": "unverified_for_this_export",
                "candidate_metric": definition["candidate_metric"],
                "candidate_canonical_unit": definition["candidate_canonical_unit"],
                "transformation": "None; original numerical scale retained",
                "source_file_sha256": entry["sha256"],
                "csv_record_number": ordinal,
                "local_observation_id": hashlib.sha256(
                    f"{entry['file_record_id']}:{entry['sha256']}:{ordinal}:{variable}".encode()
                ).hexdigest(),
            }
            if cell["status"] == "invalid_numeric":
                issues.append("invalid_numeric:" + variable)
        if all(
            cells.get(variable, {}).get("status") == "finite_reported_value"
            for variable in ("SBP", "DBP")
        ):
            systolic = Decimal(raw["SBP"].strip())
            diastolic = Decimal(raw["DBP"].strip())
            if systolic < diastolic:
                issues.append("source_sbp_below_dbp")
            if systolic == diastolic:
                issues.append("source_sbp_equals_dbp")
        rows.append(
            {
                "source_file_id": entry["file_record_id"],
                "source_file_sha256": entry["sha256"],
                "csv_record_number": ordinal,
                "source_row_id": identifier or None,
                "record_kind": "empty_source_record" if empty else "source_record",
                "raw_cells": raw,
                "calendar_date": observed_date.isoformat() if observed_date else None,
                "measured_at": None,
                "interval_end": None,
                "relative_step_column": time_column,
                "relative_step": step,
                "stage_group": stage or None,
                "quality_assessment": "not_assessed",
                "issues": issues,
                "observations": cells,
            }
        )
    if not rows:
        raise NasaImportError("MR001G source file has no CSV data records")
    return rows


def descriptive_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Describe each file/context/stage/channel separately, including flagged values."""
    groups = defaultdict(list)
    for row in rows:
        context = tuple(row["raw_cells"][column] for column in CONTEXT_COLUMNS)
        for variable, cell in row["observations"].items():
            key = (row["source_file_id"], *context, row["stage_group"] or "", variable)
            groups[key].append((row, cell))
    output = []
    for key, pairs in sorted(groups.items()):
        values = [cell["value"] for _, cell in pairs if cell["status"] == "finite_reported_value"]
        try:
            statistics = robust_statistics.describe(values).model_dump(mode="json")
            status = "computed" if values else "no_finite_values"
        except (OverflowError, ValueError):
            statistics = None
            status = "not_representable_by_existing_utility"
        output.append(
            {
                "source_file_id": key[0],
                "source_context": dict(zip(CONTEXT_COLUMNS, key[1:6], strict=True)),
                "stage_group": key[6] or None,
                "source_variable": key[7],
                "unit": None,
                "unit_status": "unverified_for_this_export",
                "record_count": len(pairs),
                "finite_value_count": len(values),
                "source_missing_count": sum(
                    cell["status"] == "source_missing" for _, cell in pairs
                ),
                "invalid_numeric_count": sum(
                    cell["status"] == "invalid_numeric" for _, cell in pairs
                ),
                "flagged_record_count": sum(bool(row["issues"]) for row, _ in pairs),
                "statistics_status": status,
                "statistics": statistics,
            }
        )
    return output


def analyze_bundle(bundle: Mr001gBundle) -> dict[str, Any]:
    """Compute a private, reproducible source-scale report, never a clinical evaluation."""
    manifest = bundle.manifest
    synthetic = manifest["is_synthetic"]
    rows = []
    file_summaries = []
    metadata = metadata_document(bundle, "dataset_metadata")
    originals = {item["id"]: item for item in metadata["related"]["data_files"]["items"]}
    for entry in manifest["files"]:
        if entry["role"] != "observations":
            continue
        parsed = parse_table(bundle.files[entry["path"]], entry, manifest)
        rows.extend(parsed)
        present = set(parsed[0]["raw_cells"])
        file_summaries.append(
            {
                "source_file_id": entry["file_record_id"],
                "source_file_sha256": entry["sha256"],
                "original_filename": originals[entry["file_record_id"]]["__original_file_name"],
                "csv_record_count": len(parsed),
                "source_columns": list(parsed[0]["raw_cells"]),
                "structurally_absent_selected_columns": sorted(set(VARIABLES) - present),
            }
        )
    kind = "synthetic_mr001g_test_data" if synthetic else "authentic_nasa_ground_analog"
    for row in rows:
        row["is_synthetic"] = synthetic
        row["data_kind"] = kind
    cells = [cell for row in rows for cell in row["observations"].values()]
    counts = Counter(cell["status"] for cell in cells)
    issues = Counter(issue for row in rows for issue in row["issues"])
    people = {
        (row["raw_cells"]["Campaign"], row["raw_cells"]["Subject"])
        for row in rows
        if all(
            row["raw_cells"][column].strip() not in MISSING_TOKENS
            for column in ("Campaign", "Subject")
        )
    }
    groups = descriptive_groups(rows)
    return {
        "report_kind": "synthetic_mr001g_test_report"
        if synthetic
        else "authentic_nasa_source_scale_review",
        "data_kind": kind,
        "is_synthetic": synthetic,
        "dataset_id": manifest["dataset_id"],
        "importer_version": VERSION,
        "notice": (
            "SYNTHETIC UNIT TEST DATA. Not NASA observations."
            if synthetic
            else "Authentic NASA-archived terrestrial bed-rest observations. Source units are not "
            "verified for this export. Descriptive outputs are not clinically validated "
            "assessments."
        ),
        "provenance": {
            "source_manifest": manifest,
            "source_manifest_sha256": hashlib.sha256(bundle.manifest_bytes).hexdigest(),
        },
        "summary": {
            "source_csv_files": len(file_summaries),
            "csv_data_records": len(rows),
            "entirely_empty_source_records": sum(
                row["record_kind"] == "empty_source_record" for row in rows
            ),
            "identified_campaign_subject_pairs": len(people),
            "present_selected_cells": len(cells),
            "finite_reported_values": counts["finite_reported_value"],
            "source_missing_cells": counts["source_missing"],
            "invalid_numeric_cells": counts["invalid_numeric"],
            "descriptive_groups": len(groups),
            "sbp_below_dbp_records": issues["source_sbp_below_dbp"],
            "paired_pressure_records": sum(
                all(
                    row["observations"].get(variable, {}).get("status") == "finite_reported_value"
                    for variable in ("SBP", "DBP")
                )
                for row in rows
            ),
            "records_with_missing_context": sum(
                any(issue.startswith("missing_context:") for issue in row["issues"]) for row in rows
            ),
            "nonempty_records_with_missing_context": sum(
                row["record_kind"] != "empty_source_record"
                and any(issue.startswith("missing_context:") for issue in row["issues"])
                for row in rows
            ),
            "structurally_absent_selected_cells": {
                variable: sum(
                    item["csv_record_count"]
                    for item in file_summaries
                    if variable in item["structurally_absent_selected_columns"]
                )
                for variable in VARIABLES
            },
            "issue_counts": dict(sorted(issues.items())),
            "column_counts": {
                variable: dict(
                    Counter(
                        row["observations"][variable]["status"]
                        for row in rows
                        if variable in row["observations"]
                    )
                )
                for variable in VARIABLES
            },
        },
        "scientific_computation": {
            "function": "app.algorithms.robust_statistics.describe",
            "output_contract": "BaselineStatistics when representable",
            "algorithm_source_sha256_lf": hashlib.sha256(
                Path(robust_statistics.__file__).read_text(encoding="utf-8").encode()
            ).hexdigest(),
            "adapter_source_sha256_lf": hashlib.sha256(
                Path(__file__).read_text(encoding="utf-8").encode()
            ).hexdigest(),
            "unit_policy": (
                "Original source scale; unit=null. Candidate canonical units are not applied."
            ),
            "selection_policy": (
                "All finite reported values, including flagged pressure pairs; exclude only "
                "explicitly missing/invalid numeric cells. No imputation or outlier removal."
            ),
            "identity_policy": (
                "No missing context is filled from filenames or other records; unidentified "
                "values remain in separate context groups."
            ),
            "interpretation": (
                "Repeated observations within a protocol are not independent participants. "
                "No inference, health scoring or baseline establishment."
            ),
        },
        "api_integration": {
            "http_requests": 0,
            "canonical_measurements_created": 0,
            "status": "blocked_pending_unit_dictionary_and_temporal_provenance_review",
            "blockers": [
                "The export lacks verified column units and acquisition/averaging definitions.",
                "Calendar dates and relative steps do not supply aware measurement timestamps.",
                "Shared contracts lack fields for all source context, missingness and provenance.",
                "No supported clinical cardiovascular evaluation is fabricated.",
            ],
        },
        "files": file_summaries,
        "records": rows,
        "descriptive_statistics": groups,
    }


def import_dataset(directory: Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """Read a verified local snapshot and compute all source-scale results afresh."""
    return analyze_bundle(verify_bundle(directory))


def encode_report(report: dict[str, Any]) -> str:
    """Serialize stable private results without generated wall-clock fields."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
