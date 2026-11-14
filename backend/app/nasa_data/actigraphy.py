"""Conservative adapter for the reviewed UTMB Campaign 1 actigraphy table.

The source supplies individual processed records, calendar dates, explicit bed-rest
phases and missing values. It does not supply UTC instants, observation intervals,
device quality assessments, or clinical interpretation. No such fields are inferred.
"""

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

from app.algorithms import robust_statistics
from app.models import METRIC_CATALOG, MetricType
from app.nasa_data.source import DEFAULT_DATA_DIR, NasaImportError, VerifiedBundle, verify_bundle

IMPORTER_VERSION = "2.0.0"
HEADERS = (
    "ID",
    "Subject",
    "Test_Phase",
    "BR_Day",
    "Date",
    "Sleep Latency (hours)",
    "Sleep Duration (hours)",
    "Sleep Efficiency (%)",
    "Notes",
)
PHASES = {"PRE_TEST", "IN_TEST", "POST_TEST"}
METRIC_COLUMNS = {
    MetricType.SLEEP_DURATION: "Sleep Duration (hours)",
    MetricType.SLEEP_EFFICIENCY: "Sleep Efficiency (%)",
}
MISSING_TOKENS = {"", "NA"}
API_BLOCKERS = (
    "Calendar dates have no clock time, time zone, or sleep-interval boundaries. "
    "The measurement contract requires an aware measured_at timestamp.",
    "The measurement contract cannot retain study provenance, the original date precision, "
    "bed-rest context, source cells, or explicit missing values.",
    "Bed-rest phases must not be relabeled as spaceflight mission phases. "
    "Personal baselines and sleep evaluations are not computed for this import.",
)


def duration_minutes(text: str) -> float | None:
    """Convert source HH:MM or HH:MM:SS durations to canonical minutes.

    The NASA ReadMe specifies HH:mm. The main table also writes :SS, with zero
    seconds in all observed values. Its '(hours)' column label is not decimal hours.
    Nonzero seconds are handled arithmetically, without rounding or truncation.
    """
    token = text.strip()
    if token in MISSING_TOKENS:
        return None
    match = re.fullmatch(r"([0-9]+):([0-5][0-9])(?::([0-5][0-9]))?", token)
    if match is None:
        raise NasaImportError(f"Unsupported duration representation: {text!r}")
    hours, minutes = int(match[1]), int(match[2])
    seconds = int(match[3] or 0)
    value = Fraction(hours * 3600 + minutes * 60 + seconds, 60)
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise NasaImportError("Duration is not representable as a finite value") from error
    if not Decimal.from_float(result).is_finite():
        raise NasaImportError("Duration is not representable as a finite value")
    return result


def efficiency_percent(text: str) -> float | None:
    """Preserve source percent values; [0, 100] is the documented unit range."""
    token = text.strip()
    if token in MISSING_TOKENS:
        return None
    try:
        value = Decimal(token)
    except InvalidOperation as error:
        raise NasaImportError(f"Unsupported efficiency representation: {text!r}") from error
    if not value.is_finite() or not 0 <= value <= 100:
        raise NasaImportError(f"Efficiency outside the documented percent range: {text!r}")
    return float(value)


def calendar_date(text: str) -> date | None:
    """Parse the source US calendar date, retaining date-only temporal precision."""
    token = text.strip()
    if token in MISSING_TOKENS:
        return None
    if re.fullmatch(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", token):
        try:
            return datetime.strptime(token, "%m/%d/%Y").date()
        except ValueError:
            pass
    raise NasaImportError(f"Unsupported source calendar date: {text!r}")


@dataclass(frozen=True)
class ActigraphyRow:
    """One source CSV record; raw cells retain the exact decoded source strings."""

    csv_record_number: int
    raw: dict[str, str]
    observed_date: date | None
    duration: float | None
    efficiency: float | None


def parse_table(content: bytes) -> tuple[ActigraphyRow, ...]:
    """Validate the reviewed table layout without filling or dropping missing cells.

    CSV record numbers count data records from one, excluding the header and empty
    physical lines. NASA's original row ID is preserved separately in raw['ID'].
    The auxiliary query export has a different layout and is deliberately rejected.
    """
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    if tuple(reader.fieldnames or ()) != HEADERS:
        raise NasaImportError("Unexpected actigraphy columns; the source requires a new review")
    rows = []
    row_ids: set[str] = set()
    subject_dates: set[tuple[str, date]] = set()
    for number, raw in enumerate(reader, start=1):
        if set(raw) != set(HEADERS) or any(not isinstance(value, str) for value in raw.values()):
            raise NasaImportError(f"Malformed actigraphy CSV record {number}")
        if not re.fullmatch(r"[1-9][0-9]*", raw["ID"]) or raw["ID"] in row_ids:
            raise NasaImportError(f"Invalid or duplicate source row ID in record {number}")
        # Authentic file identity is enforced by the source digests, rather than
        # publishing a participant list in the adapter or its synthetic fixtures.
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", raw["Subject"]):
            raise NasaImportError(f"Invalid source subject in record {number}")
        if raw["Test_Phase"] not in PHASES or not re.fullmatch(r"[0-9]+", raw["BR_Day"]):
            raise NasaImportError(f"Unsupported bed-rest phase or day in record {number}")
        observed_date = calendar_date(raw["Date"])
        key = (raw["Subject"], observed_date) if observed_date is not None else None
        if key is not None:
            if key in subject_dates:
                raise NasaImportError(f"Duplicate subject/calendar-date record {number}")
            subject_dates.add(key)
        row_ids.add(raw["ID"])
        # Latency has no canonical metric. Preserve its source strings (including
        # the source's bare "0" cells) without imposing the duration parser on it.
        rows.append(
            ActigraphyRow(
                csv_record_number=number,
                raw=raw,
                observed_date=observed_date,
                duration=duration_minutes(raw["Sleep Duration (hours)"]),
                efficiency=efficiency_percent(raw["Sleep Efficiency (%)"]),
            )
        )
    if not rows:
        raise NasaImportError("The source table has no data records")
    return tuple(rows)


def observations(row: ActigraphyRow, bundle: VerifiedBundle) -> list[dict[str, Any]]:
    """Expose canonical values with cell-level lineage, including explicit nulls."""
    entry = bundle.entry("primary_table")
    values = {
        MetricType.SLEEP_DURATION: row.duration,
        MetricType.SLEEP_EFFICIENCY: row.efficiency,
    }
    return [
        {
            "local_observation_id": hashlib.sha256(
                f"{entry['sha256']}:{row.csv_record_number}:{metric.value}".encode()
            ).hexdigest(),
            "metric": metric.value,
            "unit": METRIC_CATALOG[metric].unit,
            "value": value,
            "missing": value is None,
            "source_column": METRIC_COLUMNS[metric],
            "source_text": row.raw[METRIC_COLUMNS[metric]],
            "source_file_sha256": entry["sha256"],
            "csv_record_number": row.csv_record_number,
            "conversion": (
                "HH:MM[:SS] to minutes, using the source ReadMe and inspected cell syntax"
                if metric == MetricType.SLEEP_DURATION
                else "Identity conversion; source and canonical units are percent"
            ),
        }
        for metric, value in values.items()
    ]


def descriptive_groups(rows: tuple[ActigraphyRow, ...]) -> list[dict[str, Any]]:
    """Run the existing descriptive algorithm separately by subject, phase and metric.

    Only missing metric cells are excluded from the value sequence. Notes, possible
    confounders and extreme values are not silently screened. These summaries are
    neither established personal baselines nor health/domain evaluations.
    """
    groups: dict[tuple[str, str], list[ActigraphyRow]] = defaultdict(list)
    for row in rows:
        groups[row.raw["Subject"], row.raw["Test_Phase"]].append(row)
    output = []
    for (subject, phase), records in sorted(groups.items()):
        dates = sorted(record.observed_date for record in records if record.observed_date)
        for metric in METRIC_COLUMNS:
            raw_values = [
                record.duration if metric == MetricType.SLEEP_DURATION else record.efficiency
                for record in records
            ]
            values = [value for value in raw_values if value is not None]
            result = robust_statistics.describe(values)
            output.append(
                {
                    "subject_id": subject,
                    "source_phase": phase,
                    "metric": metric.value,
                    "unit": METRIC_CATALOG[metric].unit,
                    "record_count": len(records),
                    "observed_value_count": len(values),
                    "missing_value_count": len(records) - len(values),
                    "missing_date_count": sum(record.observed_date is None for record in records),
                    "first_source_date": dates[0].isoformat() if dates else None,
                    "last_source_date": dates[-1].isoformat() if dates else None,
                    "source_notes": dict(
                        sorted(Counter(row.raw["Notes"] for row in records).items())
                    ),
                    "statistics": result.model_dump(mode="json"),
                }
            )
    return output


def import_dataset(directory: Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """Return a deterministic local report from verified, authentic source files.

    This does not instantiate PhysiologicalMeasurement, create crew members, contact
    an API, assign UTC midnight to dates, or map analog phases to flight phases.
    """
    bundle = verify_bundle(directory)
    rows = parse_table(bundle.files["primary_table"])
    manifest = bundle.manifest
    is_synthetic = manifest["is_synthetic"]
    data_kind = "synthetic_adapter_test_data" if is_synthetic else "authentic_nasa_ground_analog"
    source_records = [
        {
            "data_kind": data_kind,
            "is_synthetic": is_synthetic,
            "participant_key": f"{manifest['dataset_id']}/{row.raw['Subject']}",
            "subject_id": row.raw["Subject"],
            "csv_record_number": row.csv_record_number,
            "source_phase": row.raw["Test_Phase"],
            "source_bed_rest_day": row.raw["BR_Day"],
            "calendar_date": row.observed_date.isoformat() if row.observed_date else None,
            "temporal_precision": "calendar_date" if row.observed_date else "missing",
            "measured_at": None,
            "interval_end": None,
            "measurement_quality": "not_assessed",
            "raw_cells": row.raw,
            "observations": observations(row, bundle),
        }
        for row in rows
    ]
    observed = sum(value is not None for row in rows for value in (row.duration, row.efficiency))
    return {
        "report_kind": (
            "synthetic_adapter_test_report"
            if is_synthetic
            else "authentic_nasa_import_with_descriptive_statistics"
        ),
        "data_kind": data_kind,
        "is_synthetic": is_synthetic,
        "notice": (
            "SYNTHETIC UNIT TEST DATA. Not NASA observations or clinical assessments."
            if is_synthetic
            else "Authentic NASA-archived terrestrial bed-rest study data. Not in-flight astronaut "
            "measurements. Descriptive outputs are not clinically validated assessments."
        ),
        "importer_version": IMPORTER_VERSION,
        "dataset_id": manifest["dataset_id"],
        "provenance": {
            "source_manifest_sha256": hashlib.sha256(bundle.manifest_bytes).hexdigest(),
            "source_manifest": manifest,
        },
        "summary": {
            "source_record_count": len(rows),
            "subject_ids": sorted({row.raw["Subject"] for row in rows}),
            "canonical_cell_count": len(rows) * len(METRIC_COLUMNS),
            "observed_value_count": observed,
            "missing_value_count": len(rows) * len(METRIC_COLUMNS) - observed,
        },
        "scientific_computation": {
            "function": "app.algorithms.robust_statistics.describe",
            "algorithm_source_sha256_lf": hashlib.sha256(
                Path(robust_statistics.__file__).read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest(),
            "adapter_source_sha256_lf": hashlib.sha256(
                Path(__file__).read_text(encoding="utf-8").encode("utf-8")
            ).hexdigest(),
            "output_contract": "BaselineStatistics",
            "interpretation": "Descriptive statistics only; not a PersonalBaseline or evaluation",
            "grouping": ["source subject", "source bed-rest phase", "canonical metric"],
            "exclusion_rule": "Exclude only missing metric cells; no imputation or outlier removal",
        },
        "api_integration": {
            "status": "requires_source_information_and_contract_review",
            "http_requests": 0,
            "blockers": list(API_BLOCKERS),
        },
        "records": source_records,
        "descriptive_statistics": descriptive_groups(rows),
    }


def encode_report(report: dict[str, Any]) -> str:
    """Encode reproducible UTF-8-compatible JSON without generated wall-clock fields."""
    return json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
