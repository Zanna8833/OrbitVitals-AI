"""Use invented records to check units, missingness, provenance and real computation."""

import hashlib
import json
import statistics
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.algorithms import robust_statistics
from app.models import BaselineStatistics, PhysiologicalMeasurement
from app.nasa_data.actigraphy import (
    HEADERS,
    calendar_date,
    descriptive_groups,
    duration_minutes,
    efficiency_percent,
    encode_report,
    import_dataset,
    parse_table,
)
from app.nasa_data.source import NasaImportError, VerifiedBundle
from tests.nasa_data.support import SYNTHETIC_NOTICE, materialize, synthetic_rows, table_bytes


@pytest.mark.parametrize(
    ("text", "expected"),
    [("0:00", 0), ("1:17:30", 77.5), ("2:03", 123), ("25:00", 1500), ("0:00:01", 1 / 60)],
)
def test_duration_conversion(text: str, expected: float) -> None:
    assert duration_minutes(text) == expected


@pytest.mark.parametrize("text", ["1.5", "1:60", "1:00:60", "-1:00", "NaN", "7h", "0:1"])
def test_ambiguous_duration_fails(text: str) -> None:
    with pytest.raises(NasaImportError, match="duration"):
        duration_minutes(text)


@pytest.mark.parametrize("text", ["NA", "", " NA "])
def test_missing_tokens_remain_null(text: str) -> None:
    assert duration_minutes(text) is None
    assert efficiency_percent(text) is None
    assert calendar_date(text) is None


@pytest.mark.parametrize("text", ["0", "41.5", "100", " 52.25 "])
def test_efficiency_preserves_percent(text: str) -> None:
    assert efficiency_percent(text) == float(text)


@pytest.mark.parametrize("text", ["-1", "100.1", "NaN", "Infinity", "52%", "N/A"])
def test_invalid_percent_fails(text: str) -> None:
    with pytest.raises(NasaImportError):
        efficiency_percent(text)


def test_calendar_precision_and_source_day_are_preserved() -> None:
    rows = parse_table(table_bytes(synthetic_rows()))
    assert rows[0].observed_date == date(2042, 1, 2)
    assert rows[0].raw["BR_Day"] == "2"
    assert rows[3].observed_date is None
    assert rows[3].duration == 0
    assert rows[3].efficiency == 0


@pytest.mark.parametrize("text", ["31/10/2042", "2/30/2042", "2042-01-02", "1/2/2042T00:00Z"])
def test_unreviewed_timestamp_formats_fail(text: str) -> None:
    with pytest.raises(NasaImportError, match="calendar date"):
        calendar_date(text)


def test_all_raw_cells_remain_unchanged() -> None:
    original = synthetic_rows()
    source = table_bytes(original)
    parsed = parse_table(source)
    assert [row.raw for row in parsed] == original
    assert [row.csv_record_number for row in parsed] == list(range(1, 7))
    assert source == table_bytes(original)
    assert all(row.raw["Notes"] == SYNTHETIC_NOTICE for row in parsed)


def test_absent_rows_are_never_generated() -> None:
    original = synthetic_rows()
    rows = parse_table(table_bytes([original[0], original[2]]))
    assert len(rows) == 2
    assert [row.raw["ID"] for row in rows] == ["1", "3"]


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("Subject", ""),
        ("Subject", "with spaces"),
        ("Test_Phase", "in_flight"),
        ("BR_Day", "-2"),
        ("ID", "0"),
    ],
)
def test_invalid_structure_is_rejected(column: str, value: str) -> None:
    row = synthetic_rows()[0]
    row[column] = value
    with pytest.raises(NasaImportError):
        parse_table(table_bytes([row]))


def test_duplicate_identity_or_subject_date_fails() -> None:
    row = synthetic_rows()[0]
    with pytest.raises(NasaImportError, match="duplicate source row ID"):
        parse_table(table_bytes([row, row]))
    with pytest.raises(NasaImportError, match="Duplicate subject/calendar-date"):
        parse_table(table_bytes([row, {**row, "ID": "99"}]))


@pytest.mark.parametrize("content", [b"", (",".join(HEADERS) + "\n").encode(), b"a,b\n1,2\n"])
def test_empty_or_changed_table_fails(content: bytes) -> None:
    with pytest.raises(NasaImportError):
        parse_table(content)


def test_malformed_record_and_auxiliary_export_are_rejected(bundle: VerifiedBundle) -> None:
    with pytest.raises(NasaImportError, match="Malformed"):
        parse_table(table_bytes(synthetic_rows()[:1]).rstrip() + b",extra\n")
    with pytest.raises(NasaImportError, match="columns"):
        parse_table(bundle.files["query_export"])


def test_missing_and_single_value_statistics_have_correct_nulls() -> None:
    row = synthetic_rows()[2]
    groups = descriptive_groups(parse_table(table_bytes([row])))
    assert all(all(value is None for value in group["statistics"].values()) for group in groups)
    row["Sleep Efficiency (%)"] = "0"
    groups = descriptive_groups(parse_table(table_bytes([row])))
    assert groups[0]["observed_value_count"] == 0
    assert groups[1]["statistics"]["mean"] == 0
    assert groups[1]["statistics"]["standard_deviation"] is None


def test_real_algorithm_and_cell_lineage_use_only_synthetic_values(
    fixture_manifest: VerifiedBundle, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    materialize(fixture_manifest, tmp_path)
    original = robust_statistics.describe
    calls = []

    def track(values: list[float]) -> BaselineStatistics:
        calls.append(list(values))
        return original(values)

    monkeypatch.setattr(robust_statistics, "describe", track)
    report = import_dataset(tmp_path)
    assert len(calls) == 6
    assert sum(map(len, calls)) == 9
    assert report["is_synthetic"] is True
    assert report["data_kind"] == "synthetic_adapter_test_data"
    assert "SYNTHETIC UNIT TEST DATA" in report["notice"]
    assert report["summary"] == {
        "source_record_count": 6,
        "subject_ids": ["SYNTHETIC_A", "SYNTHETIC_B"],
        "canonical_cell_count": 12,
        "observed_value_count": 9,
        "missing_value_count": 3,
    }
    identifiers = []
    for record in report["records"]:
        assert record["is_synthetic"] is True
        assert record["measured_at"] is None and record["interval_end"] is None
        assert record["measurement_quality"] == "not_assessed"
        for observation in record["observations"]:
            assert observation["source_text"] == record["raw_cells"][observation["source_column"]]
            assert observation["csv_record_number"] == record["csv_record_number"]
            assert (
                observation["source_file_sha256"]
                == fixture_manifest.entry("primary_table")["sha256"]
            )
            identifiers.append(observation["local_observation_id"])
    assert len(set(identifiers)) == 12
    for group, values in zip(report["descriptive_statistics"], calls, strict=True):
        assert BaselineStatistics.model_validate(group["statistics"]) == original(values)
        if values:
            assert group["statistics"]["mean"] == statistics.mean(values)
    assert report["api_integration"]["http_requests"] == 0
    assert report["api_integration"]["blockers"]


def test_repeated_imports_and_a_copied_cache_are_identical(
    fixture_manifest: VerifiedBundle, tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    materialize(fixture_manifest, first)
    materialize(fixture_manifest, second)
    encoded = encode_report(import_dataset(first))
    assert encoded == encode_report(import_dataset(first)) == encode_report(import_dataset(second))
    report = json.loads(encoded)
    assert report["provenance"]["source_manifest"] == fixture_manifest.manifest
    assert (
        report["provenance"]["source_manifest_sha256"]
        == hashlib.sha256(fixture_manifest.manifest_bytes).hexdigest()
    )
    assert "authentic_nasa_ground_analog" not in encoded
    assert "Vega" not in encoded and "Noor" not in encoded and "Chen" not in encoded


def test_current_measurement_contract_rejects_date_only_and_extra_provenance() -> None:
    with pytest.raises(ValidationError) as caught:
        PhysiologicalMeasurement.model_validate(
            {
                "measurement_id": "synthetic-contract-check",
                "crew_member_id": "SYNTHETIC_A",
                "metric": "sleep_duration",
                "unit": "min",
                "value": 77.5,
                "measured_at": "2042-01-02",
                "source": "simulated",
                "provenance": SYNTHETIC_NOTICE,
            }
        )
    assert {tuple(error["loc"]) for error in caught.value.errors()} >= {
        ("measured_at",),
        ("provenance",),
    }
