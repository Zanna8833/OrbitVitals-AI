"""Exercise reviewed context, real synthetic pipelines, privacy and fail-closed states."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.nasa_data.source import REPO_ROOT, NasaImportError
from app.nasa_evidence import (
    DatasetId,
    EvidenceResponse,
    EvidenceTopic,
    NasaEvidenceAdapter,
    encode_response,
)
from app.nasa_evidence.catalog import reviewed_profiles
from app.nasa_evidence.models import EvidenceItem, StructuralFinding


@pytest.mark.parametrize("topic", list(EvidenceTopic))
def test_all_topics_work_without_data_or_network(topic: EvidenceTopic) -> None:
    response = NasaEvidenceAdapter().retrieve(topic)
    assert response.status == "ok"
    assert not response.failures and not response.contains_synthetic_findings
    assert all(item.source_verification.state == "not_configured" for item in response.items)
    assert all(not item.structural_findings for item in response.items)
    assert all(
        item.crew_telemetry is False and item.clinically_validated is False
        for item in response.items
    )
    assert encode_response(response) == encode_response(NasaEvidenceAdapter().retrieve(topic))


@pytest.mark.parametrize("topic", [EvidenceTopic.SLEEP, EvidenceTopic.ACTIGRAPHY])
def test_sleep_topics_route_to_actigraphy(topic: EvidenceTopic) -> None:
    response = NasaEvidenceAdapter().retrieve(topic)
    assert [item.dataset_id for item in response.items] == [DatasetId.ACTIGRAPHY]
    assert [variable.canonical_unit for variable in response.items[0].relevant_variables] == [
        "min",
        "%",
    ]


@pytest.mark.parametrize(
    ("topic", "columns"),
    [
        (EvidenceTopic.HEART_RATE, ["HR", "HR (Dinamap)", "AVE HR"]),
        (EvidenceTopic.BLOOD_PRESSURE, ["SBP", "DBP"]),
        (EvidenceTopic.CARDIOVASCULAR_ADAPTATION, ["SBP", "DBP", "HR", "HR (Dinamap)", "AVE HR"]),
    ],
)
def test_mr001g_channels_and_unresolved_units_are_explicit(topic, columns) -> None:
    item = NasaEvidenceAdapter().retrieve(topic).items[0]
    assert item.dataset_id == DatasetId.MR001G
    assert [variable.source_column for variable in item.relevant_variables] == columns
    assert all(variable.unit_verification == "unresolved" for variable in item.relevant_variables)
    assert all(variable.canonical_unit is None for variable in item.relevant_variables)
    assert any("protocol" in line for line in item.limitations)


def test_dataset_filter_and_unsupported_pair_are_deterministic() -> None:
    adapter = NasaEvidenceAdapter()
    assert [item.dataset_id for item in adapter.retrieve("data_quality").items] == list(DatasetId)
    assert len(adapter.retrieve("data_quality", DatasetId.MR001G).items) == 1
    result = adapter.retrieve("sleep", DatasetId.MR001G)
    assert result.status == "no_matching_evidence" and not result.items and not result.failures
    with pytest.raises(ValueError):
        adapter.retrieve("diagnosis")
    with pytest.raises(ValueError):
        adapter.retrieve("sleep", "new-dataset")


def test_verified_fixture_counts_are_computed_by_existing_importers(
    adapter: NasaEvidenceAdapter,
) -> None:
    response = adapter.retrieve("data_quality")
    assert response.status == "ok" and response.contains_synthetic_findings
    counts = [
        {finding.code: finding.value for finding in item.structural_findings}
        for item in response.items
    ]
    assert counts[0] == {
        "source_records": 6,
        "observed_metric_cells": 9,
        "source_missing_metric_cells": 3,
    }
    assert counts[1] == {
        "source_records": 7,
        "observed_metric_cells": 14,
        "source_missing_metric_cells": 7,
        "invalid_numeric_metric_cells": 3,
        "empty_source_records": 1,
        "records_with_missing_context": 2,
    }
    for item in response.items:
        assert item.source_verification.state == "synthetic_fixture_verified"
        assert item.source_verification.pipeline_code_sha256
        assert all(
            finding.data_origin == "synthetic_test_fixture" for finding in item.structural_findings
        )
    assert encode_response(response) == encode_response(adapter.retrieve("data_quality"))
    assert EvidenceResponse.model_validate_json(encode_response(response)) == response


def test_projection_never_exposes_private_report_fields(adapter: NasaEvidenceAdapter) -> None:
    payload = json.loads(encode_response(adapter.retrieve("data_quality")))
    prohibited = {
        "subject_id",
        "subject_ids",
        "participant_key",
        "source_context",
        "raw_cells",
        "source_text",
        "original_filename",
        "records",
        "descriptive_statistics",
        "statistics",
        "mean",
        "median",
        "minimum",
        "maximum",
        "measured_at",
        "calendar_date",
        "source_notes",
        "threshold",
    }

    def check(value):
        if isinstance(value, dict):
            assert not prohibited.intersection(value)
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(payload)
    encoded = json.dumps(payload)
    assert "TEST_PERSON" not in encoded and "SYNTHETIC_A" not in encoded
    assert "2042" not in encoded and "2050" not in encoded


def test_files_and_evidence_ids_do_not_change_during_retrieval(
    adapter: NasaEvidenceAdapter,
) -> None:
    snapshots = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in adapter._caches.values()
        for path in directory.rglob("*")
        if path.is_file()
    }
    first = adapter.retrieve("data_quality")
    assert first == adapter.retrieve("data_quality")
    assert snapshots == {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in snapshots}
    for item in first.items:
        assert item.evidence_id.startswith("nasa-evidence-v1-")


def test_missing_cache_is_explained_and_never_uses_an_implicit_cache(tmp_path: Path) -> None:
    response = NasaEvidenceAdapter({DatasetId.ACTIGRAPHY: tmp_path / "absent"}).retrieve("sleep")
    assert response.status == "partial"
    assert response.failures[0].code == "source_missing"
    assert response.items[0].source_verification.state == "unavailable"
    assert not response.items[0].structural_findings
    assert str(tmp_path) not in encode_response(response)


def test_in_repository_source_locations_are_rejected() -> None:
    response = NasaEvidenceAdapter({DatasetId.ACTIGRAPHY: REPO_ROOT / ".nasa-private"}).retrieve(
        "sleep"
    )
    assert response.failures[0].code == "source_rejected"
    assert not response.items[0].structural_findings


def test_corrupt_source_withholds_counts_but_keeps_reviewed_context(
    adapter: NasaEvidenceAdapter,
) -> None:
    directory = adapter._caches[DatasetId.MR001G]
    path = next((directory / "raw").glob("*.csv"))
    path.write_bytes(path.read_bytes() + b"changed")
    response = adapter.retrieve("data_quality")
    assert response.status == "partial"
    assert response.failures[0].dataset_id == DatasetId.MR001G
    assert response.failures[0].code == "source_rejected"
    assert response.items[0].structural_findings
    assert not response.items[1].structural_findings
    assert response.items[1].source_verification.state == "rejected"


def test_cache_local_manifest_cannot_authorize_revised_data(adapter: NasaEvidenceAdapter) -> None:
    directory = adapter._caches[DatasetId.ACTIGRAPHY]
    (directory / "manifest.json").write_text('{"approved": true}')
    assert adapter.retrieve("sleep").status == "ok"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (FileNotFoundError("PRIVATE_PATH"), "manifest_unavailable"),
        (NasaImportError("PRIVATE_SOURCE_CELL"), "manifest_rejected"),
    ],
)
def test_manifest_failures_are_sanitized(error, code) -> None:
    def load():
        raise error

    profile = replace(reviewed_profiles()[0], load_manifest=load)
    result = NasaEvidenceAdapter(_profiles=(profile,)).retrieve("sleep")
    assert result.status == "unavailable" and not result.items
    assert result.failures[0].code == code
    assert "PRIVATE_" not in encode_response(result)


def test_even_valid_manifest_revisions_require_explicit_review() -> None:
    profile = replace(reviewed_profiles()[0], manifest_sha256="0" * 64)
    result = NasaEvidenceAdapter(_profiles=(profile,)).retrieve("sleep")
    assert result.failures[0].code == "manifest_rejected"


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (PermissionError("PRIVATE_PATH"), "source_unreadable"),
        (NasaImportError("PRIVATE_CELL"), "source_rejected"),
        (ValueError("PRIVATE_CELL"), "processing_failed"),
        (KeyError("PRIVATE_CELL"), "processing_failed"),
        (ArithmeticError("PRIVATE_CELL"), "processing_failed"),
    ],
)
def test_processing_failures_withhold_counts_and_sanitize_details(adapter, error, code) -> None:
    def fail(_directory):
        raise error

    profile = replace(adapter._profiles[0], import_dataset=fail)
    failed = NasaEvidenceAdapter(adapter._caches, _profiles=(profile,)).retrieve("sleep")
    assert failed.status == "partial" and failed.failures[0].code == code
    assert not failed.items[0].structural_findings
    assert "PRIVATE_" not in encode_response(failed)


def test_source_report_provenance_mismatch_is_rejected(adapter) -> None:
    profile = adapter._profiles[0]
    report = profile.import_dataset(adapter._caches[profile.dataset_id])
    report["provenance"]["source_manifest_sha256"] = "0" * 64
    changed = replace(profile, import_dataset=lambda _: report)
    result = NasaEvidenceAdapter(adapter._caches, _profiles=(changed,)).retrieve("sleep")
    assert result.failures[0].code == "source_rejected"


def test_synthetic_sources_cannot_be_promoted_to_nasa_sources(adapter) -> None:
    profile = replace(adapter._profiles[0], synthetic_fixture=False)
    result = NasaEvidenceAdapter(adapter._caches, _profiles=(profile,)).retrieve("sleep")
    assert result.status == "unavailable" and result.failures[0].code == "manifest_rejected"


def test_numeric_diagnostics_identify_all_counted_columns_even_for_narrow_topics(adapter) -> None:
    item = adapter.retrieve("heart_rate").items[0]
    assert len(item.relevant_variables) == 3
    for finding in item.structural_findings:
        assert finding.included_source_columns == ("SBP", "DBP", "HR", "HR (Dinamap)", "AVE HR")


def test_malformed_pipeline_counts_are_withheld(adapter) -> None:
    profile = adapter._profiles[0]
    report = profile.import_dataset(adapter._caches[profile.dataset_id])
    report["summary"]["observed_value_count"] = True
    changed = replace(profile, import_dataset=lambda _: report)
    result = NasaEvidenceAdapter(adapter._caches, _profiles=(changed,)).retrieve("sleep")
    assert result.failures[0].code == "processing_failed"
    assert not result.items[0].structural_findings


def test_contract_rejects_unverified_numbers_and_mr001g_unit_normalization() -> None:
    item = NasaEvidenceAdapter().retrieve("heart_rate").items[0].model_dump(mode="json")
    item["relevant_variables"][0]["canonical_unit"] = "min"
    with pytest.raises(ValidationError, match="MR001G"):
        EvidenceItem.model_validate(item)
    item = NasaEvidenceAdapter().retrieve("sleep").items[0].model_dump(mode="json")
    item["structural_findings"] = [
        {
            "code": "source_records",
            "included_source_columns": ["Sleep Duration (hours)", "Sleep Efficiency (%)"],
            "value": 2,
            "count_unit": "records",
            "data_origin": "verified_nasa_source_files",
            "computation": "Synthetic contract test",
        }
    ]
    with pytest.raises(ValidationError, match="verified source"):
        EvidenceItem.model_validate(item)


@pytest.mark.parametrize("value", [True, -1, 1.5, float("nan"), float("inf")])
def test_structural_counts_are_strict_nonnegative_integers(value) -> None:
    with pytest.raises(ValidationError):
        StructuralFinding(
            code="source_records",
            value=value,
            count_unit="records",
            included_source_columns=("Synthetic test column",),
            data_origin="synthetic_test_fixture",
            computation="Synthetic test",
        )
