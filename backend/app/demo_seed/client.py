"""HTTP-only ingestion, computation and retrieval through unchanged v0.1 endpoints."""

import json
import math
from collections import Counter
from datetime import datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.demo_seed.dataset import FINAL_AS_OF, METRICS, CrewPlan, build_manifest, build_plan
from app.models import (
    METRIC_CATALOG,
    EvaluationResult,
    MetricDefinition,
    PersonalBaseline,
    PhysiologicalMeasurement,
)
from app.scenarios.models import SIMULATION_NOTICE, BehaviorCheck
from app.services.commands import Items, MeasurementBatch


class SeedError(Exception):
    """Actionable transport, contract or dataset-consistency failure."""


class JsonApi(Protocol):
    def request(self, method: str, path: str, payload: dict | None = None) -> dict: ...


class HttpApi:
    """A standard-library client targeting an explicitly local API instance."""

    def __init__(self, base_url: str, timeout: float = 30) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in ("http", "https")
            or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or parsed.path.rstrip("/") != "/api/v1"
        ):
            raise SeedError("base-url must be a loopback HTTP(S) URL ending in /api/v1")
        if not math.isfinite(timeout) or timeout <= 0:
            raise SeedError("timeout must be finite and positive")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload, allow_nan=False).encode("utf-8") if payload is not None else None
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                value = json.load(response)
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise SeedError(f"{method} {path}: HTTP {error.code}: {detail}") from error
        except (URLError, OSError, ValueError) as error:
            raise SeedError(f"{method} {path}: {error}") from error
        if not isinstance(value, dict):
            raise SeedError(f"{method} {path}: expected a JSON object")
        return value


def _check(identifier: str, description: str, expected, actual) -> BehaviorCheck:
    return BehaviorCheck(
        check_id=identifier,
        description=description,
        expected=expected,
        actual=actual,
        passed=expected == actual,
    )


def _preflight(api: JsonApi, plan: tuple[CrewPlan, ...]) -> None:
    health = api.request("GET", "/health")
    if health.get("status") != "ok":
        raise SeedError("The local API health check did not return status=ok")
    try:
        timestamp = health["timestamp"]
        if not isinstance(timestamp, str):
            raise ValueError("timestamp must be a string")
        server_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if server_time.tzinfo is None or server_time < FINAL_AS_OF:
            raise SeedError(
                f"Server clock must be at or after {FINAL_AS_OF.isoformat()}; "
                "no records were written"
            )
    except (KeyError, ValueError, TypeError) as error:
        raise SeedError("The health endpoint did not return a valid server timestamp") from error
    catalog = Items[MetricDefinition].model_validate(api.request("GET", "/metrics"))
    by_metric = {item.metric: item for item in catalog.items}
    for metric in METRICS:
        expected = METRIC_CATALOG[metric]
        if (
            metric not in by_metric
            or by_metric[metric].unit != expected.unit
            or by_metric[metric].domain != expected.domain
        ):
            raise SeedError(f"Server catalog is incompatible with canonical metric {metric.value}")
    # All crew reads happen before the first write. Reserved IDs must not mix with
    # other histories; server-side global-ID conflicts remain atomic HTTP 409s.
    for crew in plan:
        actual = (
            Items[PhysiologicalMeasurement]
            .model_validate(api.request("GET", f"/crew-members/{crew.crew_member_id}/measurements"))
            .items
        )
        expected = {item.measurement_id: item for item in crew.measurements}
        for item in actual:
            desired = expected.get(item.measurement_id)
            if desired is None or desired.model_dump(exclude={"data_quality"}) != item.model_dump(
                exclude={"data_quality"}
            ):
                raise SeedError(
                    f"Reserved crew {crew.crew_member_id} contains unexpected/conflicting records. "
                    "Use a fresh local API process; the seeder never deletes existing data."
                )


def seed_api(api: JsonApi, *, batch_size: int = 500) -> dict:
    """Populate and verify a fixed dataset; expected behaviors never replace real results."""
    if not 1 <= batch_size <= 1000:
        raise SeedError("batch-size must be from 1 through 1000")
    plan = build_plan()
    _preflight(api, plan)
    records = [record for crew in plan for record in crew.measurements]
    for offset in range(0, len(records), batch_size):
        batch = MeasurementBatch(measurements=records[offset : offset + batch_size])
        response = Items[PhysiologicalMeasurement].model_validate(
            api.request("POST", "/measurements", batch.model_dump(mode="json"))
        )
        if {item.measurement_id for item in response.items} != {
            item.measurement_id for item in batch.measurements
        }:
            raise SeedError(
                "Ingestion response did not preserve the submitted measurement identities"
            )
        original = {item.measurement_id: item for item in batch.measurements}
        if any(
            item.model_dump(exclude={"data_quality"})
            != original[item.measurement_id].model_dump(exclude={"data_quality"})
            for item in response.items
        ):
            raise SeedError(
                "Ingestion response changed an authored measurement value or its metadata"
            )
    # Finish every ingestion batch before creating any derived snapshot, so later
    # batches cannot invalidate a partially seeded presentation.
    report = {
        "data_kind": "simulated",
        "notice": SIMULATION_NOTICE,
        "manifest": build_manifest(plan),
        "crews": [],
        "all_checks_passed": True,
    }
    for crew in plan:
        base_path = f"/crew-members/{crew.crew_member_id}"
        created_baselines = {}
        for command in crew.baselines:
            value = PersonalBaseline.model_validate(
                api.request("POST", base_path + "/baselines", command.model_dump(mode="json"))
            )
            if value.crew_member_id != crew.crew_member_id or value.metric != command.metric:
                raise SeedError("Baseline response belongs to a different crew member or metric")
            created_baselines[command.metric] = value
        created_evaluations = []
        checks = []
        for spec in crew.evaluations:
            command = spec.command.model_copy(
                update={
                    "baseline_ids": tuple(
                        created_baselines[metric].baseline_id for metric in spec.baseline_metrics
                    )
                }
            )
            value = EvaluationResult.model_validate(
                api.request("POST", base_path + "/evaluations", command.model_dump(mode="json"))
            )
            if value.crew_member_id != crew.crew_member_id or value.domain != command.domain:
                raise SeedError("Evaluation response belongs to a different crew member or domain")
            checks.append(
                _check(
                    spec.checkpoint,
                    spec.demonstration_behavior,
                    spec.expected_status,
                    value.status.value,
                )
            )
            created_evaluations.append(
                {"checkpoint": spec.checkpoint, "result": value.model_dump(mode="json")}
            )
        retrieved_measurements = (
            Items[PhysiologicalMeasurement]
            .model_validate(api.request("GET", base_path + "/measurements"))
            .items
        )
        retrieved_baselines = (
            Items[PersonalBaseline]
            .model_validate(api.request("GET", base_path + "/baselines"))
            .items
        )
        retrieved_evaluations = (
            Items[EvaluationResult]
            .model_validate(api.request("GET", base_path + "/evaluations"))
            .items
        )
        checks.append(
            _check(
                "measurement_identity",
                "All authored measurement IDs remain retrievable.",
                sorted(item.measurement_id for item in crew.measurements),
                sorted(item.measurement_id for item in retrieved_measurements),
            )
        )
        checks.append(
            _check(
                "measurement_content",
                "Retrieved values, units, acquisition identities and timestamps match the inputs.",
                True,
                {
                    item.measurement_id: item.model_dump(exclude={"data_quality"})
                    for item in crew.measurements
                }
                == {
                    item.measurement_id: item.model_dump(exclude={"data_quality"})
                    for item in retrieved_measurements
                },
            )
        )
        checks.append(
            _check(
                "computed_baseline_retrieval",
                "Every computed baseline remains stored.",
                True,
                all(value in retrieved_baselines for value in created_baselines.values()),
            )
        )
        checks.append(
            _check(
                "computed_evaluation_retrieval",
                "Every computed evaluation remains stored.",
                True,
                all(
                    EvaluationResult.model_validate(item["result"]) in retrieved_evaluations
                    for item in created_evaluations
                ),
            )
        )
        checks.append(
            _check(
                "simulation_labels",
                "Every stored demo measurement is explicitly simulated.",
                True,
                all(item.source.value == "simulated" for item in retrieved_measurements),
            )
        )
        checks.append(
            _check(
                "baseline_establishment",
                "The explicit synthetic reference policy is satisfied.",
                True,
                all(item.status.value == "established" for item in created_baselines.values()),
            )
        )
        unusable = sum(
            item.data_quality is not None and item.data_quality.status.value == "unusable"
            for item in retrieved_measurements
        )
        checks.append(
            _check(
                "quality_engine_provenance",
                "Stored measurements carry real Data Quality Engine provenance.",
                True,
                all(
                    item.data_quality is not None
                    and item.data_quality.algorithm is not None
                    and item.data_quality.algorithm.name == "data_quality"
                    for item in retrieved_measurements
                ),
            )
        )
        checks.append(
            _check(
                "scientific_engine_provenance",
                "Baseline and evaluation algorithms are the integrated engines.",
                True,
                all(
                    item.algorithm.name == "personal_baseline"
                    for item in created_baselines.values()
                )
                and all(
                    item["result"]["algorithm"]["name"]
                    == {
                        "sleep": "sleep_monitoring_trends",
                        "physical_activity": "physical_activity_monitor",
                    }[item["result"]["domain"]]
                    for item in created_evaluations
                ),
            )
        )
        checks.append(
            _check(
                "quality_failure_injection",
                "The telemetry profile contains actual engine-detected failures.",
                crew.scenario == "sensor_failures_and_missing_data",
                unusable > 0,
            )
        )
        failed = any(not item.passed for item in checks)
        report["all_checks_passed"] &= not failed
        report["crews"].append(
            {
                "crew_member_id": crew.crew_member_id,
                "data_kind": "simulated",
                "scenario": crew.scenario,
                "stored_measurement_count": len(retrieved_measurements),
                "metric_record_counts": dict(
                    sorted(Counter(item.metric.value for item in retrieved_measurements).items())
                ),
                "quality_status_counts": dict(
                    sorted(
                        Counter(
                            item.data_quality.status.value
                            if item.data_quality is not None
                            else "not_assessed"
                            for item in retrieved_measurements
                        ).items()
                    )
                ),
                "quality_flag_counts": dict(
                    sorted(
                        Counter(
                            flag.value
                            for item in retrieved_measurements
                            if item.data_quality is not None
                            for flag in item.data_quality.flags
                        ).items()
                    )
                ),
                "baselines": [item.model_dump(mode="json") for item in created_baselines.values()],
                "evaluations": created_evaluations,
                "checks": [item.model_dump(mode="json") for item in checks],
            }
        )
    return report
