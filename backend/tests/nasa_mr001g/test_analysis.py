"""Check source preservation and explainability with invented cardiovascular data."""

import json
from pathlib import Path

import pytest

from app.algorithms import robust_statistics
from app.models import BaselineStatistics
from app.nasa_data.source import NasaImportError
from app.nasa_mr001g.analysis import (
    analyze_bundle,
    encode_report,
    import_dataset,
    numeric_cell,
    parse_table,
)
from app.nasa_mr001g.source import Mr001gBundle
from tests.nasa_mr001g.support import HEADERS, csv_bytes, invented_rows, materialize


@pytest.mark.parametrize("text", ["", "NA", " NA "])
def test_missing_tokens_are_not_zero(text: str) -> None:
    cell = numeric_cell(text)
    assert cell == {"source_text": text, "value": None, "status": "source_missing"}


@pytest.mark.parametrize(
    "text", ["NaN", "Infinity", "-inf", "1e999", "1e-999", "-1e-999", "1_000", "broken", "N/A"]
)
def test_invalid_numbers_are_preserved_and_not_reclassified_as_source_missing(text: str) -> None:
    assert numeric_cell(text) == {"source_text": text, "value": None, "status": "invalid_numeric"}


@pytest.mark.parametrize(("text", "value"), [("0", 0), ("-4", -4), ("1e2", 100), ("49.25", 49.25)])
def test_finite_values_keep_the_reported_scale_without_medical_thresholds(
    text: str, value: float
) -> None:
    assert numeric_cell(text)["value"] == value
    assert numeric_cell(text)["status"] == "finite_reported_value"


def primary_entry(bundle: Mr001gBundle) -> dict:
    return next(item for item in bundle.manifest["files"] if item["role"] == "observations")


def test_all_original_cells_records_and_empty_rows_are_preserved(bundle: Mr001gBundle) -> None:
    entry = primary_entry(bundle)
    rows = parse_table(bundle.files[entry["path"]], entry, bundle.manifest)
    assert [row["raw_cells"] for row in rows] == invented_rows()
    assert [row["csv_record_number"] for row in rows] == [1, 2, 3, 4, 5]
    assert rows[3]["record_kind"] == "empty_source_record"
    assert rows[1]["source_row_id"] is None
    assert "duplicate_source_row_id" in rows[2]["issues"]
    assert all(row["quality_assessment"] == "not_assessed" for row in rows)


def test_inverted_pressure_is_flagged_without_swapping_discarding_or_exclusion(
    bundle: Mr001gBundle,
) -> None:
    report = analyze_bundle(bundle)
    row = report["records"][0]
    assert "source_sbp_below_dbp" in row["issues"]
    assert row["observations"]["SBP"]["value"] == 68
    assert row["observations"]["DBP"]["value"] == 92
    group = next(
        g
        for g in report["descriptive_statistics"]
        if g["source_file_id"] == row["source_file_id"]
        and g["stage_group"] == "Supine"
        and g["source_variable"] == "SBP"
    )
    assert group["finite_value_count"] == 2
    assert group["flagged_record_count"] == 1
    assert group["statistics"]["mean"] == 90
    assert report["summary"]["sbp_below_dbp_records"] == 1


def test_decimal_pair_comparison_does_not_lose_anomaly_to_float_rounding(
    bundle: Mr001gBundle,
) -> None:
    raw = invented_rows()[0]
    raw["SBP"] = "0.1000000000000000000000001"
    raw["DBP"] = "0.1000000000000000000000002"
    row = parse_table(csv_bytes([raw]), primary_entry(bundle), bundle.manifest)[0]
    assert row["observations"]["SBP"]["value"] == row["observations"]["DBP"]["value"]
    assert "source_sbp_below_dbp" in row["issues"]
    assert "source_sbp_equals_dbp" not in row["issues"]


def test_zeros_equal_pressure_and_absent_channels_remain_distinct(bundle: Mr001gBundle) -> None:
    report = analyze_bundle(bundle)
    row = report["records"][1]
    assert row["observations"]["SBP"]["value"] == 0
    assert row["observations"]["AVE HR"]["status"] == "source_missing"
    assert "source_sbp_equals_dbp" in row["issues"]
    second = report["records"][-2]
    assert set(second["observations"]) == {"SBP", "HR (Dinamap)"}
    assert "HR" not in second["observations"]
    assert report["summary"]["structurally_absent_selected_cells"]["DBP"] == 2


def test_units_are_never_guessed_and_heart_rate_channels_are_not_pooled(
    bundle: Mr001gBundle,
) -> None:
    report = analyze_bundle(bundle)
    first = report["records"][0]
    assert first["observations"]["HR"]["value"] != first["observations"]["AVE HR"]["value"]
    for row in report["records"]:
        for cell in row["observations"].values():
            assert cell["unit"] is None
            assert cell["unit_status"] == "unverified_for_this_export"
            assert "metric" not in cell
    assert all(group["unit"] is None for group in report["descriptive_statistics"])
    assert report["api_integration"]["canonical_measurements_created"] == 0
    assert report["api_integration"]["http_requests"] == 0
    assert report["api_integration"]["blockers"]


def test_missing_context_is_not_filled_from_other_rows_or_filenames(bundle: Mr001gBundle) -> None:
    report = analyze_bundle(bundle)
    row = report["records"][2]
    assert row["raw_cells"]["Subject"] == ""
    assert row["calendar_date"] is None
    assert row["relative_step"]["source_text"] == "1/2"
    assert row["relative_step"]["status"] == "invalid_numeric"
    assert row["relative_step"]["value"] is None
    assert "missing_context:Subject" in row["issues"]
    unidentified = [
        g for g in report["descriptive_statistics"] if g["source_context"]["Subject"] == ""
    ]
    assert unidentified and any(g["finite_value_count"] for g in unidentified)
    assert report["summary"]["identified_campaign_subject_pairs"] == 2


def test_source_dates_are_not_utc_and_catalog_disagreements_do_not_correct_them(
    bundle: Mr001gBundle,
) -> None:
    report = analyze_bundle(bundle)
    assert all(
        row["measured_at"] is None and row["interval_end"] is None for row in report["records"]
    )
    assert report["records"][1]["raw_cells"]["Stage"] == "Tilt "
    assert report["records"][1]["stage_group"] == "Tilt"
    assert "stage_whitespace_normalized_for_grouping" in report["records"][1]["issues"]
    late = report["records"][-2]
    assert late["calendar_date"] == "2050-01-05"
    assert "date_after_catalog_narrative_end" in late["issues"]
    bad = report["records"][-1]
    assert bad["raw_cells"]["Date"] == "2/30/2050"
    assert bad["calendar_date"] is None and "invalid_calendar_date" in bad["issues"]


@pytest.mark.parametrize(
    "change", ["duplicate_header", "unknown_column", "no_time", "two_times", "no_variables"]
)
def test_unreviewed_layouts_fail_without_losing_columns(bundle: Mr001gBundle, change: str) -> None:
    columns = HEADERS.copy()
    if change == "duplicate_header":
        columns.append("SBP")
    elif change == "unknown_column":
        columns.append("unreviewed_column")
    elif change == "no_time":
        columns.remove("Min")
    elif change == "two_times":
        columns.append("Minute")
    else:
        columns = [c for c in columns if c not in ["SBP", "DBP", "HR", "AVE HR"]]
    body = (",".join(columns) + "\n").encode()
    with pytest.raises(NasaImportError, match="layout"):
        parse_table(body, primary_entry(bundle), bundle.manifest)


def test_bad_record_width_and_header_only_file_fail(bundle: Mr001gBundle) -> None:
    entry = primary_entry(bundle)
    with pytest.raises(NasaImportError, match="width"):
        parse_table(csv_bytes(invented_rows()[:1]).rstrip() + b",extra\n", entry, bundle.manifest)
    with pytest.raises(NasaImportError, match="no CSV data records"):
        parse_table((",".join(HEADERS) + "\n").encode(), entry, bundle.manifest)


def test_real_descriptive_utility_is_called_for_every_group(
    bundle: Mr001gBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = robust_statistics.describe
    calls = []

    def track(values):
        calls.append(list(values))
        return original(values)

    monkeypatch.setattr(robust_statistics, "describe", track)
    report = analyze_bundle(bundle)
    assert len(calls) == report["summary"]["descriptive_groups"] == 20
    assert sum(map(len, calls)) == report["summary"]["finite_reported_values"] == 14
    assert report["summary"]["source_missing_cells"] == 7
    assert report["summary"]["invalid_numeric_cells"] == 3
    for group, values in zip(report["descriptive_statistics"], calls, strict=True):
        assert BaselineStatistics.model_validate(group["statistics"]) == original(values)
        if not values:
            assert all(value is None for value in group["statistics"].values())
    assert "SYNTHETIC UNIT TEST DATA" in report["notice"]
    assert report["is_synthetic"] is True
    assert all(row["is_synthetic"] for row in report["records"])


def test_unrepresentable_statistics_are_reported_explicitly(
    bundle: Mr001gBundle, monkeypatch: pytest.MonkeyPatch
) -> None:
    def overflow(values):
        raise OverflowError("Synthetic numerical-range test")

    monkeypatch.setattr(robust_statistics, "describe", overflow)
    report = analyze_bundle(bundle)
    assert all(group["statistics"] is None for group in report["descriptive_statistics"])
    assert all(
        group["statistics_status"] == "not_representable_by_existing_utility"
        for group in report["descriptive_statistics"]
    )


def test_identifiers_include_file_identity_even_for_identical_bodies(bundle: Mr001gBundle) -> None:
    entry = primary_entry(bundle)
    row = parse_table(csv_bytes(invented_rows()[:1]), entry, bundle.manifest)[0]
    changed = {**entry, "file_record_id": "00000000-0000-0000-0000-000000000099"}
    other = parse_table(csv_bytes(invented_rows()[:1]), changed, bundle.manifest)[0]
    assert (
        row["observations"]["HR"]["local_observation_id"]
        != other["observations"]["HR"]["local_observation_id"]
    )


def test_reproducible_reports_use_only_verified_fixture_bytes(
    trusted_fixture: Mr001gBundle, tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    materialize(trusted_fixture, first)
    materialize(trusted_fixture, second)
    result = encode_report(import_dataset(first))
    assert result == encode_report(import_dataset(first)) == encode_report(import_dataset(second))
    data = json.loads(result)
    assert data["provenance"]["source_manifest"] == trusted_fixture.manifest
    assert "authentic_nasa_ground_analog" not in result
