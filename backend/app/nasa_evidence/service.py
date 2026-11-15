"""Read-only projection of verified pipelines onto a closed, privacy-limited contract.

No network, download, report write, crew repository or model provider is used.
Private pipeline reports are projected field by field, never returned or logged.
"""

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.nasa_data.source import NasaImportError, require_external_destination, source_path
from app.nasa_evidence.catalog import DatasetProfile, reviewed_profiles
from app.nasa_evidence.models import (
    DatasetId,
    EvidenceFailure,
    EvidenceItem,
    EvidenceProvenance,
    EvidenceResponse,
    EvidenceTopic,
    SourceVerification,
    StructuralFinding,
)

INTEGRITY_CHECKS = ("SHA-256", "MD5", "byte_count", "catalog_linkage")
DIAGNOSTICS = {
    DatasetId.ACTIGRAPHY: (
        ("source_record_count", "source_records", "records"),
        ("observed_value_count", "observed_metric_cells", "cells"),
        ("missing_value_count", "source_missing_metric_cells", "cells"),
    ),
    DatasetId.MR001G: (
        ("csv_data_records", "source_records", "records"),
        ("finite_reported_values", "observed_metric_cells", "cells"),
        ("source_missing_cells", "source_missing_metric_cells", "cells"),
        ("invalid_numeric_cells", "invalid_numeric_metric_cells", "cells"),
        ("entirely_empty_source_records", "empty_source_records", "records"),
        ("records_with_missing_context", "records_with_missing_context", "records"),
    ),
}
FAILURE_MESSAGES = {
    "manifest_unavailable": "Reviewed provenance is unavailable; dataset evidence is withheld.",
    "manifest_rejected": "Provenance is not the reviewed snapshot; evidence is withheld.",
    "source_missing": "Configured local sources are incomplete; recomputed findings are withheld.",
    "source_unreadable": "Local sources cannot be read; recomputed findings are withheld.",
    "source_rejected": "Local source integrity or location checks failed; findings are withheld.",
    "processing_failed": "Pipeline input validation failed; recomputed findings are withheld.",
}


def encode_response(response: EvidenceResponse) -> str:
    """Stable JSON: no timestamps, random IDs, private paths or exception text."""
    return json.dumps(response.model_dump(mode="json"), sort_keys=True, indent=2) + "\n"


def _failure(profile: DatasetProfile, code: str) -> EvidenceFailure:
    return EvidenceFailure(dataset_id=profile.dataset_id, code=code, message=FAILURE_MESSAGES[code])


class NasaEvidenceAdapter:
    """Use explicit operator cache paths; never discover a developer's private cache.

    The private profile injection is for synthetic contract tests only. HTTP and CLI
    clients cannot register profiles, approve source revisions or enable fixtures.
    """

    def __init__(
        self,
        cache_directories: Mapping[DatasetId, Path] | None = None,
        *,
        _profiles: tuple[DatasetProfile, ...] | None = None,
    ) -> None:
        self._caches = {
            DatasetId(key): Path(value) for key, value in (cache_directories or {}).items()
        }
        self._profiles = tuple(
            sorted(
                reviewed_profiles() if _profiles is None else _profiles,
                key=lambda item: item.dataset_id,
            )
        )
        if len({profile.dataset_id for profile in self._profiles}) != len(self._profiles):
            raise ValueError("Duplicate evidence dataset profile")

    def retrieve(
        self, topic: EvidenceTopic | str, dataset_id: DatasetId | str | None = None
    ) -> EvidenceResponse:
        topic = EvidenceTopic(topic)
        dataset_id = DatasetId(dataset_id) if dataset_id is not None else None
        selected = [
            profile
            for profile in self._profiles
            if topic in profile.topics and (dataset_id is None or profile.dataset_id == dataset_id)
        ]
        items, failures = [], []
        for profile in selected:
            item, failure = self._retrieve_one(profile, topic)
            if item is not None:
                items.append(item)
            if failure is not None:
                failures.append(failure)
        status = "ok"
        if not selected:
            status = "no_matching_evidence"
        elif not items:
            status = "unavailable"
        elif failures:
            status = "partial"
        return EvidenceResponse(
            topic=topic,
            status=status,
            items=tuple(items),
            failures=tuple(failures),
            contains_synthetic_findings=any(
                item.source_verification.state == "synthetic_fixture_verified" for item in items
            ),
        )

    def _retrieve_one(
        self, profile: DatasetProfile, topic: EvidenceTopic
    ) -> tuple[EvidenceItem | None, EvidenceFailure | None]:
        try:
            manifest, content = profile.load_manifest()
            if (
                hashlib.sha256(content).hexdigest() != profile.manifest_sha256
                or manifest["dataset_id"] != profile.source_identity
                or manifest["is_synthetic"] is not profile.synthetic_fixture
                or manifest["license"]["redistribution_status"] != "unconfirmed"
            ):
                raise NasaImportError("Unreviewed evidence provenance")
        except OSError:
            return None, _failure(profile, "manifest_unavailable")
        except (ValueError, KeyError, TypeError):
            return None, _failure(profile, "manifest_rejected")

        verification = SourceVerification(state="not_configured")
        findings: tuple[StructuralFinding, ...] = ()
        failure = None
        directory = self._caches.get(profile.dataset_id)
        if directory is not None:
            verification, findings, failure = self._source_findings(profile, manifest, directory)
        variables = profile.variables
        if topic == EvidenceTopic.HEART_RATE:
            variables = tuple(variable for variable in variables if "HR" in variable.source_column)
        elif topic == EvidenceTopic.BLOOD_PRESSURE:
            variables = tuple(
                variable for variable in variables if variable.source_column in {"SBP", "DBP"}
            )
        snapshot = json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode()
        fields = {
            "dataset_id": profile.dataset_id,
            "title": manifest["title"],
            "nasa_source_url": manifest["catalog_url"],
            "study_population": (
                "Human terrestrial bed-rest volunteers; neither in-flight astronauts "
                "nor synthetic crew."
            ),
            "topic": topic,
            "relevant_variables": variables,
            "context_findings": profile.context,
            "structural_findings": findings,
            "source_verification": verification,
            "provenance": EvidenceProvenance(
                manifest_path=profile.manifest_path,
                manifest_sha256=profile.manifest_sha256,
                source_snapshot_sha256=hashlib.sha256(snapshot).hexdigest(),
                reviewed_source_file_count=len(manifest["files"]),
                nasa_metadata_url=profile.metadata_url,
                experiment_doi=manifest["experiment_doi"],
                documentation_path=profile.documentation_path,
                pipeline=profile.pipeline,
            ),
            "limitations": profile.limitations,
        }
        item = EvidenceItem(evidence_id="pending", **fields)
        digest = hashlib.sha256(item.model_dump_json(exclude={"evidence_id"}).encode()).hexdigest()
        return item.model_copy(update={"evidence_id": f"nasa-evidence-v1-{digest}"}), failure

    def _source_findings(
        self, profile: DatasetProfile, manifest: dict[str, Any], directory: Path
    ) -> tuple[SourceVerification, tuple[StructuralFinding, ...], EvidenceFailure | None]:
        try:
            require_external_destination(directory)
            if any(
                not source_path(directory, entry["path"]).is_file() for entry in manifest["files"]
            ):
                return (
                    SourceVerification(state="unavailable"),
                    (),
                    _failure(profile, "source_missing"),
                )
            report = profile.import_dataset(directory)
            if (
                report["dataset_id"] != profile.source_identity
                or report["is_synthetic"] is not profile.synthetic_fixture
                or report["provenance"]["source_manifest_sha256"] != profile.manifest_sha256
            ):
                raise NasaImportError("Pipeline report disagrees with reviewed provenance")
            origin = (
                "synthetic_test_fixture"
                if profile.synthetic_fixture
                else "verified_nasa_source_files"
            )
            findings = tuple(
                StructuralFinding(
                    code=code,
                    count_unit=unit,
                    value=report["summary"][key],
                    included_source_columns=tuple(
                        variable.source_column for variable in profile.variables
                    ),
                    data_origin=origin,
                    computation=(
                        f"{profile.pipeline}: summary.{key}; selected export, "
                        "no grouping by participant"
                    ),
                )
                for key, code, unit in DIAGNOSTICS[profile.dataset_id]
            )
            verification = SourceVerification(
                state="synthetic_fixture_verified" if profile.synthetic_fixture else "verified",
                checks=INTEGRITY_CHECKS,
                pipeline_code_sha256=report["scientific_computation"]["adapter_source_sha256_lf"],
            )
            return verification, findings, None
        except OSError:
            return (
                SourceVerification(state="unavailable"),
                (),
                _failure(profile, "source_unreadable"),
            )
        except NasaImportError:
            return SourceVerification(state="rejected"), (), _failure(profile, "source_rejected")
        except (ValueError, KeyError, TypeError, ArithmeticError):
            return SourceVerification(state="rejected"), (), _failure(profile, "processing_failed")
