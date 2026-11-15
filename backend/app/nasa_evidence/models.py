"""Versioned evidence contracts, separate from crew measurement contracts."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class EvidenceTopic(StrEnum):
    SLEEP = "sleep"
    ACTIGRAPHY = "actigraphy"
    HEART_RATE = "heart_rate"
    BLOOD_PRESSURE = "blood_pressure"
    CARDIOVASCULAR_ADAPTATION = "cardiovascular_adaptation"
    DATA_QUALITY = "data_quality"


class DatasetId(StrEnum):
    ACTIGRAPHY = "nasa-lsda-brsmact-utmb-campaign-1"
    MR001G = "nasa-lsda-mr001g-utmb-campaign-3-tilt"


class EvidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class EvidenceVariable(EvidenceModel):
    source_column: str
    description: str
    source_representation: str
    unit_verification: Literal["reviewed_source_dictionary", "unresolved"]
    canonical_unit: Literal["min", "%"] | None
    transformation: str


class StructuralFinding(EvidenceModel):
    """Whole-export shape diagnostics; physiological statistics have no field here."""

    code: Literal[
        "source_records",
        "observed_metric_cells",
        "source_missing_metric_cells",
        "invalid_numeric_metric_cells",
        "empty_source_records",
        "records_with_missing_context",
    ]
    value: Annotated[int, Field(strict=True, ge=0)]
    count_unit: Literal["records", "cells"]
    scope: Literal["complete_selected_export"] = "complete_selected_export"
    included_source_columns: tuple[str, ...] = Field(min_length=1)
    data_origin: Literal["verified_nasa_source_files", "synthetic_test_fixture"]
    computation: str


class SourceVerification(EvidenceModel):
    model_config = ConfigDict(
        json_schema_extra={
            "if": {"properties": {"state": {"enum": ["verified", "synthetic_fixture_verified"]}}},
            "then": {
                "required": ["checks", "pipeline_code_sha256"],
                "properties": {
                    "checks": {"minItems": 4, "maxItems": 4, "uniqueItems": True},
                    "pipeline_code_sha256": {"type": "string"},
                },
            },
            "else": {
                "properties": {
                    "checks": {"maxItems": 0},
                    "pipeline_code_sha256": {"type": "null"},
                }
            },
        }
    )
    state: Literal[
        "not_configured", "verified", "synthetic_fixture_verified", "unavailable", "rejected"
    ]
    checks: tuple[Literal["SHA-256", "MD5", "byte_count", "catalog_linkage"], ...] = ()
    pipeline_code_sha256: Digest | None = None

    @model_validator(mode="after")
    def require_integrity_proof(self) -> "SourceVerification":
        if self.state in {"verified", "synthetic_fixture_verified"}:
            if (
                len(self.checks) != 4
                or set(self.checks) != {"SHA-256", "MD5", "byte_count", "catalog_linkage"}
                or self.pipeline_code_sha256 is None
            ):
                raise ValueError("Verified evidence requires complete integrity provenance")
        elif self.checks or self.pipeline_code_sha256 is not None:
            raise ValueError("Unverified sources cannot carry successful verification proof")
        return self


class EvidenceProvenance(EvidenceModel):
    manifest_path: str
    manifest_sha256: Digest
    source_snapshot_sha256: Digest
    reviewed_source_file_count: Annotated[int, Field(strict=True, ge=1)]
    nasa_metadata_url: str
    experiment_doi: str | None
    documentation_path: str
    pipeline: str


class EvidenceItem(EvidenceModel):
    model_config = ConfigDict(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"dataset_id": {"const": DatasetId.MR001G.value}}},
                    "then": {
                        "properties": {
                            "relevant_variables": {
                                "items": {
                                    "properties": {
                                        "unit_verification": {"const": "unresolved"},
                                        "canonical_unit": {"type": "null"},
                                    }
                                }
                            }
                        }
                    },
                },
                {
                    "if": {
                        "properties": {
                            "source_verification": {
                                "properties": {
                                    "state": {
                                        "not": {"enum": ["verified", "synthetic_fixture_verified"]}
                                    }
                                }
                            }
                        }
                    },
                    "then": {"properties": {"structural_findings": {"maxItems": 0}}},
                },
                {
                    "if": {
                        "properties": {
                            "source_verification": {
                                "properties": {"state": {"const": "synthetic_fixture_verified"}}
                            }
                        }
                    },
                    "then": {
                        "properties": {
                            "structural_findings": {
                                "items": {
                                    "properties": {
                                        "data_origin": {"const": "synthetic_test_fixture"}
                                    }
                                }
                            }
                        }
                    },
                    "else": {
                        "properties": {
                            "structural_findings": {
                                "items": {
                                    "properties": {
                                        "data_origin": {"const": "verified_nasa_source_files"}
                                    }
                                }
                            }
                        }
                    },
                },
            ]
        }
    )
    evidence_id: str
    dataset_id: DatasetId
    title: str
    nasa_source_url: str
    study_population: str
    study_context: Literal["terrestrial_bed_rest_analogue"] = "terrestrial_bed_rest_analogue"
    evidence_scope: Literal["scientific_context_only"] = "scientific_context_only"
    crew_telemetry: Literal[False] = False
    clinically_validated: Literal[False] = False
    nasa_endorsement: Literal[False] = False
    topic: EvidenceTopic
    relevant_variables: tuple[EvidenceVariable, ...]
    context_findings: tuple[str, ...]
    structural_findings: tuple[StructuralFinding, ...] = ()
    source_verification: SourceVerification
    provenance: EvidenceProvenance
    redistribution_status: Literal["unconfirmed"] = "unconfirmed"
    publication_policy: Literal["authored_context_and_verified_structural_counts_only"] = (
        "authored_context_and_verified_structural_counts_only"
    )
    limitations: tuple[str, ...]

    @model_validator(mode="after")
    def enforce_evidence_boundaries(self) -> "EvidenceItem":
        state = self.source_verification.state
        if self.structural_findings and state not in {"verified", "synthetic_fixture_verified"}:
            raise ValueError("Numeric findings require verified source files")
        origin = (
            "synthetic_test_fixture"
            if state == "synthetic_fixture_verified"
            else ("verified_nasa_source_files")
        )
        if any(finding.data_origin != origin for finding in self.structural_findings):
            raise ValueError("Finding origin disagrees with source verification")
        if self.dataset_id == DatasetId.MR001G and any(
            variable.unit_verification != "unresolved" or variable.canonical_unit is not None
            for variable in self.relevant_variables
        ):
            raise ValueError("MR001G source units remain unresolved")
        return self


class EvidenceFailure(EvidenceModel):
    dataset_id: DatasetId
    code: Literal[
        "manifest_unavailable",
        "manifest_rejected",
        "source_missing",
        "source_unreadable",
        "source_rejected",
        "processing_failed",
    ]
    message: str


class EvidenceResponse(EvidenceModel):
    model_config = ConfigDict(
        json_schema_extra={
            "if": {
                "properties": {
                    "items": {
                        "contains": {
                            "properties": {
                                "source_verification": {
                                    "properties": {"state": {"const": "synthetic_fixture_verified"}}
                                }
                            }
                        }
                    }
                }
            },
            "then": {"properties": {"contains_synthetic_findings": {"const": True}}},
            "else": {"properties": {"contains_synthetic_findings": {"const": False}}},
        }
    )
    contract_version: Literal["1.0.0"] = "1.0.0"
    topic: EvidenceTopic
    status: Literal["ok", "partial", "unavailable", "no_matching_evidence"]
    contains_synthetic_findings: bool
    items: tuple[EvidenceItem, ...]
    failures: tuple[EvidenceFailure, ...] = ()
    notice: Literal[
        "Scientific dataset context only. Never substitute for crew telemetry or clinical "
        "assessment. Synthetic-fixture findings are tests, not NASA observations."
    ] = (
        "Scientific dataset context only. Never substitute for crew telemetry or clinical "
        "assessment. Synthetic-fixture findings are tests, not NASA observations."
    )

    @model_validator(mode="after")
    def require_consistent_result(self) -> "EvidenceResponse":
        synthetic = any(
            item.source_verification.state == "synthetic_fixture_verified" for item in self.items
        )
        if synthetic != self.contains_synthetic_findings:
            raise ValueError("Synthetic finding indicator disagrees with the evidence items")
        if any(item.topic != self.topic for item in self.items):
            raise ValueError("Evidence topic disagrees with the requested topic")
        if len({item.dataset_id for item in self.items}) != len(self.items):
            raise ValueError("Duplicate evidence dataset")
        expected = (
            "partial"
            if self.failures and self.items
            else "unavailable"
            if self.failures
            else "ok"
            if self.items
            else "no_matching_evidence"
        )
        if self.status != expected:
            raise ValueError("Evidence status disagrees with items and failures")
        return self
