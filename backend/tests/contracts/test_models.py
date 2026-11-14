"""Invariants of the contract models that JSON Schema alone cannot express."""

from typing import Any

import pytest
from pydantic import ValidationError

from app.models import (
    METRIC_CATALOG,
    DataQuality,
    EvaluationStatus,
    MetricType,
    MissionPhase,
    PhysiologicalMeasurement,
    QualityFlag,
    QualityStatus,
)
from tests.support import load_example


def measurement_payload(**overrides: Any) -> dict[str, Any]:
    return {**load_example("physiological_measurement"), **overrides}


def test_every_metric_has_a_catalog_entry() -> None:
    assert set(METRIC_CATALOG) == set(MetricType)


def test_data_quality_and_physiological_status_share_no_values() -> None:
    quality_values = {member.value for member in (*QualityStatus, *QualityFlag)}
    physiological_values = {member.value for member in EvaluationStatus}

    assert quality_values.isdisjoint(physiological_values)


def test_data_quality_contract_does_not_carry_a_physiological_status() -> None:
    assert "EvaluationStatus" not in DataQuality.model_json_schema().get("$defs", {})


def test_unit_must_be_the_canonical_unit_of_the_metric() -> None:
    with pytest.raises(ValidationError, match="canonical unit"):
        PhysiologicalMeasurement.model_validate(measurement_payload(unit="Hz"))


def test_timestamps_must_carry_a_time_zone() -> None:
    with pytest.raises(ValidationError):
        PhysiologicalMeasurement.model_validate(
            measurement_payload(measured_at="2026-11-14T08:30:00")
        )


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PhysiologicalMeasurement.model_validate(measurement_payload(unexpected_field=1))


def test_non_finite_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        PhysiologicalMeasurement.model_validate(measurement_payload(value=float("nan")))


def test_interval_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="interval_end"):
        PhysiologicalMeasurement.model_validate(
            measurement_payload(
                measured_at="2026-11-14T08:30:00Z", interval_end="2026-11-14T08:00:00Z"
            )
        )


def test_mission_phase_cannot_end_before_it_starts() -> None:
    payload = {
        **load_example("mission_phase"),
        "start_time": "2026-10-10T12:00:00Z",
        "end_time": "2026-10-09T12:00:00Z",
    }

    with pytest.raises(ValidationError, match="end_time"):
        MissionPhase.model_validate(payload)
