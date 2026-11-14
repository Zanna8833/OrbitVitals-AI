"""SIMULATED sleep workflow against an existing local FastAPI server.

Run from backend/: python -m scripts.demo_sleep_http --validate
Source of all fixture dates, values, checkpoints and engineering policy settings:
docs/sleep-http-demo.md. None is a medical threshold or validated mission setting.
The client generates inputs and checks responses; all scientific computation is HTTP.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from app.models import EvaluationResult, PersonalBaseline, PhysiologicalMeasurement
from app.services.commands import BaselineCommand, EvaluationCommand, MeasurementBatch

JsonObject = dict[str, Any]
Requester = Callable[[str, str, JsonObject | None], tuple[int, JsonObject]]
DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
NOTICE = (
    "SIMULATED DATA: HTTP integration demonstration, not clinical validation or medical advice."
)
# Source: docs/sleep-http-demo.md, "Synthetic protocol". All windows are fixed UTC.
PRIOR_START = datetime(2026, 10, 18, 12, tzinfo=UTC)
WINDOW_START = datetime(2026, 11, 1, 12, tzinfo=UTC)
WINDOW_END = datetime(2026, 11, 10, 12, tzinfo=UTC)
EVALUATED_AT = datetime(2026, 11, 11, 12, tzinfo=UTC)
SLEEP_UNITS = {"sleep_duration": "min", "sleep_efficiency": "%"}
POLICY_SOURCE = (
    "SIMULATED sleep HTTP fixture policy; docs/sleep-http-demo.md; "
    "seven samples spanning six days is an engineering example, not validation evidence"
)


class DemoError(Exception):
    """An HTTP, response, isolation or validation problem that prevents verification."""


def encode(value: Any) -> str:
    """Return stable finite JSON; retain actual server response timestamps."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n"


def _timestamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def sleep_policy() -> JsonObject:
    """An explicitly synthetic, complete SleepConfig, never an application default."""
    # Source: docs/sleep-http-demo.md, "Synthetic protocol"; effect sizes follow
    # the existing app/domains/sleep/demo.py illustration, with no clinical claim.
    return {
        "policy_id": "simulated-sleep-http-v1",
        "duration": {
            "minimum_slope_per_day": 5,
            "minimum_total_change": 30,
            "minimum_observation_deviation": 60,
        },
        "efficiency": {
            "minimum_slope_per_day": 0.5,
            "minimum_total_change": 3,
            "minimum_observation_deviation": 5,
        },
        "minimum_nights": 4,
        "minimum_coverage": 0.6,
        "minimum_span_days": 3,
        "maximum_consecutive_missing_nights": 2,
        "minimum_decreasing_fraction": 0.75,
        "night_start_hour_utc": 12,
    }


def _records(
    crew: str,
    label: str,
    start: datetime,
    durations: Sequence[float],
    efficiencies: Sequence[float],
    *,
    missing: frozenset[int] = frozenset(),
) -> list[JsonObject]:
    records = []
    for index, values in enumerate(zip(durations, efficiencies, strict=True)):
        if index in missing:
            continue
        # Fixture acquisition: start 22:00 UTC, end 07:00 UTC, canonical values
        # supplied independently of elapsed time (docs/sleep-http-demo.md).
        at = start + timedelta(days=index, hours=10)
        for (metric, unit), value in zip(SLEEP_UNITS.items(), values, strict=True):
            record = PhysiologicalMeasurement(
                measurement_id=f"{crew}-{label}-{index:02d}-{metric}",
                crew_member_id=crew,
                metric=metric,
                unit=unit,
                value=value,
                measured_at=at,
                interval_end=at + timedelta(hours=9),
                source="simulated",
                device_id="simulated-sleep-http-fixture-v1",
            )
            records.append(record.model_dump(mode="json", exclude={"data_quality"}))
    return records


def _baseline_command(metric: str) -> JsonObject:
    # Source: the synthetic protocol; this phase contains the historical and
    # evaluation windows. Reference data end before any evaluation observation.
    return BaselineCommand.model_validate(
        {
            "metric": metric,
            "mission_phase": "in_flight",
            "aggregation": "measurement",
            "mission_phases": [
                {
                    "phase_id": "simulated-sleep-http-phase",
                    "mission_id": "simulated-sleep-http-mission",
                    "phase": "in_flight",
                    "label": "SIMULATED in-flight context",
                    "start_time": "2026-10-01T00:00:00Z",
                }
            ],
            "reference_start": _timestamp(PRIOR_START),
            "reference_end": _timestamp(PRIOR_START + timedelta(days=7)),
            "computed_at": _timestamp(WINDOW_START),
            "config": {
                "minimum_samples": 2,
                "established_min_samples": 7,
                "established_min_span": "P6D",
                "policy_source": POLICY_SOURCE,
            },
        }
    ).model_dump(mode="json")


def build_cases(namespace: str = "v1") -> tuple[JsonObject, ...]:
    """Build fresh, isolated, deterministic simulated inputs, never engine outputs."""
    if re.fullmatch(r"[A-Za-z0-9_-]{1,32}", namespace) is None:
        raise DemoError("namespace must contain 1-32 ASCII letters, digits, underscores or hyphens")
    cases = []
    # Source: docs/sleep-http-demo.md, "Synthetic protocol": independent cases,
    # deliberately authored levels, faults and missing-night positions.
    for name, expected in (
        ("restriction", "attention"),
        ("sparse", "insufficient_data"),
        ("unusable", "insufficient_data"),
    ):
        crew = f"sim-sleep-http-{namespace}-{name}"
        if name == "restriction":
            prior = _records(
                crew,
                "prior",
                PRIOR_START,
                (470, 480, 490, 475, 485, 480, 480),
                (90, 91, 92, 91, 93, 92, 92),
            )
            current = _records(
                crew,
                "current",
                WINDOW_START,
                (490, 475, 460, 445, 430, 415, 400, 385, 370),
                (92, 92, 92, 92, 125, 92, 92, 92, 92),
                missing=frozenset({2, 6}),
            )
            original = next(
                record
                for record in current
                if record["metric"] == "sleep_duration"
                and record["measured_at"] == _timestamp(WINDOW_START + timedelta(days=3, hours=10))
            )
            # A distinct opaque ID copies one observation; DQ retains the
            # lexicographically earlier original. No identifier is parsed.
            current.append({**original, "measurement_id": f"zz-{crew}-redundant-copy"})
            records = prior + current
        elif name == "sparse":
            records = _records(crew, "prior", PRIOR_START, (480,), (91,)) + _records(
                crew, "current", WINDOW_START, (480, 465), (92, 92)
            )
        else:
            records = _records(crew, "current", WINDOW_START, (-30,) * 5, (125,) * 5)
        batch = MeasurementBatch(measurements=records).model_dump(mode="json", exclude_none=True)
        evaluation = EvaluationCommand.model_validate(
            {
                "domain": "sleep",
                "mission_phase": "in_flight",
                "window_start": _timestamp(WINDOW_START),
                "window_end": _timestamp(WINDOW_END),
                "evaluated_at": _timestamp(EVALUATED_AT),
                "sleep_config": sleep_policy(),
            }
        ).model_dump(mode="json", exclude_none=True)
        cases.append(
            {
                "case_id": name,
                "crew_member_id": crew,
                "measurement_batch": batch,
                "baseline_commands": [_baseline_command(metric) for metric in SLEEP_UNITS]
                if name != "unusable"
                else [],
                "evaluation_command": evaluation,
                "expected_status": expected,
            }
        )
    return tuple(cases)


def _base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or parsed.hostname not in ("localhost", "127.0.0.1", "::1")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/api/v1"
    ):
        raise DemoError("base URL must be a local HTTP(S) /api/v1 URL without credentials or query")
    return value.rstrip("/")


def http_request(
    method: str,
    url: str,
    payload: JsonObject | None,
    *,
    timeout: float = 10,
) -> tuple[int, JsonObject]:
    """Send JSON over loopback HTTP; HTTP errors retain their real response bodies."""
    request = Request(
        url,
        method=method,
        data=encode(payload).encode("utf-8") if payload is not None else None,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        opener = build_opener(ProxyHandler({}))
        try:
            response = opener.open(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            status = response.code
            body = json.loads(response.read().decode("utf-8"))
    except (URLError, OSError, ValueError) as error:
        raise DemoError(f"Request failed for {method} {url}: {error}") from error
    if not isinstance(body, dict):
        raise DemoError(f"Expected a JSON object from {method} {url}")
    return status, body


def _identity(payload: JsonObject) -> JsonObject:
    return PhysiologicalMeasurement.model_validate(payload).model_dump(
        mode="json", exclude={"data_quality"}
    )


def _check(name: str, expected: Any, actual: Any) -> JsonObject:
    return {"name": name, "expected": expected, "actual": actual, "passed": expected == actual}


def run_demo(
    base_url: str = DEFAULT_BASE_URL,
    *,
    namespace: str = "v1",
    timeout: float = 10,
    requester: Requester | None = None,
) -> JsonObject:
    """Ingest, build, evaluate and read through HTTP; never invoke an engine directly.

    The injectable requester lets tests exercise the same client against the real
    FastAPI app via its ASGI transport, with no network or replaced scientific logic.
    """
    base = _base_url(base_url)
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise DemoError("timeout must be a finite positive number")
    cases = build_cases(namespace)
    send = requester if requester is not None else partial(http_request, timeout=timeout)
    exchanges: list[JsonObject] = []

    def request(
        method: str,
        path: str,
        payload: JsonObject | None = None,
        *,
        expected: int = 200,
        resource: str | None = None,
        collection: bool = False,
    ) -> JsonObject:
        status, body = send(method, f"{base}{path}", payload)
        exchanges.append(
            {
                "method": method,
                "path": path,
                "request": payload,
                "status_code": status,
                "response": body,
                "resource": resource,
                "collection": collection,
            }
        )
        if status != expected:
            raise DemoError(
                f"{method} {path}: expected HTTP {expected}, received {status}: "
                f"{encode(body).strip()}"
            )
        model = {
            "physiological_measurement": PhysiologicalMeasurement,
            "personal_baseline": PersonalBaseline,
            "evaluation_result": EvaluationResult,
        }.get(resource)
        if collection and (set(body) != {"items"} or not isinstance(body["items"], list)):
            raise DemoError(f"{method} {path} did not return the documented items envelope")
        if model is not None:
            for item in body["items"] if collection else [body]:
                parsed = model.model_validate(item)
                if isinstance(parsed, PhysiologicalMeasurement) and (
                    parsed.data_quality is None or parsed.data_quality.algorithm is None
                ):
                    raise DemoError("Server did not return an engine assessment for a measurement")
        return body

    health = request("GET", "/health")
    if health.get("status") != "ok" or health.get("service") != "orbitvitals-api":
        raise DemoError("The local server did not identify itself as the OrbitVitals API")
    catalog = request("GET", "/metrics", collection=True)
    units = {item["metric"]: item["unit"] for item in catalog["items"]}
    if any(units.get(metric) != unit for metric, unit in SLEEP_UNITS.items()):
        raise DemoError("Server metric catalog does not match the canonical sleep metrics")

    # Check all namespaces before any writes. Never reset a server or delete data.
    for case in cases:
        path = f"/crew-members/{quote(case['crew_member_id'], safe='')}"
        stored = request(
            "GET", f"{path}/measurements", resource="physiological_measurement", collection=True
        )
        intended = {
            item["measurement_id"]: _identity(item)
            for item in case["measurement_batch"]["measurements"]
        }
        if any(intended.get(item["measurement_id"]) != _identity(item) for item in stored["items"]):
            raise DemoError(
                "The demo namespace contains other measurement content; choose another --namespace"
            )

    results = []
    for case in cases:
        path = f"/crew-members/{quote(case['crew_member_id'], safe='')}"
        ingestion = request(
            "POST",
            "/measurements",
            case["measurement_batch"],
            expected=201,
            resource="physiological_measurement",
            collection=True,
        )
        stored_measurements = request(
            "GET", f"{path}/measurements", resource="physiological_measurement", collection=True
        )
        received = {item["measurement_id"]: item for item in ingestion["items"]}
        stored_by_id = {item["measurement_id"]: item for item in stored_measurements["items"]}
        checks = [
            _check("stored_measurements_match", received, stored_by_id),
            _check(
                "input_values_preserved",
                {
                    item["measurement_id"]: _identity(item)
                    for item in case["measurement_batch"]["measurements"]
                },
                {key: _identity(item) for key, item in received.items()},
            ),
            _check(
                "real_quality_engine",
                ["data_quality"],
                sorted({item["data_quality"]["algorithm"]["name"] for item in received.values()}),
            ),
        ]
        baselines = [
            request(
                "POST", f"{path}/baselines", command, expected=201, resource="personal_baseline"
            )
            for command in case["baseline_commands"]
        ]
        if baselines:
            stored_baselines = request(
                "GET",
                f"{path}/baselines?mission_phase=in_flight",
                resource="personal_baseline",
                collection=True,
            )["items"]
            baseline_map = {item["baseline_id"]: item for item in stored_baselines}
            checks.append(
                _check(
                    "stored_baselines_match",
                    baselines,
                    [baseline_map.get(item["baseline_id"]) for item in baselines],
                )
            )
            checks.append(
                _check(
                    "baseline_statuses",
                    ["established"] * 2
                    if case["case_id"] == "restriction"
                    else ["insufficient_data"] * 2,
                    [item["status"] for item in baselines],
                )
            )
        command = {
            **case["evaluation_command"],
            "baseline_ids": [
                item["baseline_id"] for item in baselines if item["status"] == "established"
            ],
        }
        evaluation = request(
            "POST", f"{path}/evaluations", command, expected=201, resource="evaluation_result"
        )
        saved = request(
            "GET",
            f"{path}/evaluations?{urlencode({'domain': 'sleep'})}",
            resource="evaluation_result",
            collection=True,
        )["items"]
        matches = [item for item in saved if item["evaluation_id"] == evaluation["evaluation_id"]]
        checks.extend(
            (
                _check("evaluation_id_found_once", 1, len(matches)),
                _check(
                    "stored_evaluation_matches",
                    evaluation,
                    matches[0] if len(matches) == 1 else None,
                ),
                _check("evaluation_status", case["expected_status"], evaluation["status"]),
                _check(
                    "real_sleep_engine", "sleep_monitoring_trends", evaluation["algorithm"]["name"]
                ),
                _check(
                    "no_unsupported_alarm",
                    False,
                    evaluation["status"] == "alert"
                    or any(item["status"] == "alert" for item in evaluation["findings"]),
                ),
            )
        )
        findings = {item["metric"]: item for item in evaluation["findings"]}
        duration = findings["sleep_duration"]
        if case["case_id"] == "restriction":
            checks.extend(
                (
                    _check("duration_median", 430.0, duration["observed_value"]),
                    _check("duration_reference", 480.0, duration["baseline_value"]),
                    _check("duration_deviation", -50.0, duration["absolute_deviation"]),
                    _check(
                        "actual_trend_explanation",
                        True,
                        "Theil-Sen slope=-15 min/day" in duration["explanation"],
                    ),
                    _check(
                        "missing_nights_retained",
                        True,
                        "missing nights=2026-11-03, 2026-11-07" in duration["explanation"],
                    ),
                    _check(
                        "invalid_efficiency_excluded",
                        "nominal",
                        findings["sleep_efficiency"]["status"],
                    ),
                    _check(
                        "excluded_ids_explained",
                        True,
                        "API eligibility policy excluded non-acceptable" in duration["explanation"],
                    ),
                )
            )
        else:
            checks.append(
                _check(
                    "no_invented_reference",
                    [None, None],
                    [item["baseline_value"] for item in evaluation["findings"]],
                )
            )
        if case["case_id"] == "unusable":
            checks.extend(
                (
                    _check("unusable_window", "unusable", evaluation["data_quality"]["status"]),
                    _check(
                        "no_invented_observations",
                        [None, None],
                        [item["observed_value"] for item in evaluation["findings"]],
                    ),
                )
            )
        results.append(
            {
                "case_id": case["case_id"],
                "crew_member_id": case["crew_member_id"],
                "ingestion_response": ingestion,
                "baseline_responses": baselines,
                "evaluation_request": command,
                "evaluation_response": evaluation,
                "stored_evaluation_response": matches[0] if len(matches) == 1 else None,
                "checks": checks,
                "checks_passed": all(check["passed"] for check in checks),
            }
        )
    return {
        "data_kind": "simulated",
        "notice": NOTICE,
        "demo_version": "0.1.0",
        "api_base_url": base,
        "namespace": namespace,
        "sleep_policy": sleep_policy(),
        "cases": results,
        "http_exchanges": exchanges,
        "all_checks_passed": all(case["checks_passed"] for case in results),
    }


def summarize(report: JsonObject) -> JsonObject:
    """Project actual response fields for a compact console summary, without classifying data."""
    cases = []
    for case in report["cases"]:
        evaluation = case["evaluation_response"]
        duration = next(
            item for item in evaluation["findings"] if item["metric"] == "sleep_duration"
        )
        cases.append(
            {
                "case_id": case["case_id"],
                "crew_member_id": case["crew_member_id"],
                "ingested_measurements": len(case["ingestion_response"]["items"]),
                "measurement_quality_counts": dict(
                    sorted(
                        Counter(
                            item["data_quality"]["status"]
                            for item in case["ingestion_response"]["items"]
                        ).items()
                    )
                ),
                "baselines": [
                    {
                        "metric": item["metric"],
                        "status": item["status"],
                        "sample_count": item["sample_count"],
                        "median": item["statistics"]["median"],
                    }
                    for item in case["baseline_responses"]
                ],
                "evaluation_id": evaluation["evaluation_id"],
                "evaluation_status": evaluation["status"],
                "window_quality_status": evaluation["data_quality"]["status"],
                "duration_median_minutes": duration["observed_value"],
                "duration_reference_minutes": duration["baseline_value"],
                "duration_deviation_minutes": duration["absolute_deviation"],
                "stored_evaluation_matches": case["stored_evaluation_response"] == evaluation,
                "checks_passed": case["checks_passed"],
            }
        )
    return {
        key: report[key]
        for key in ("data_kind", "notice", "api_base_url", "namespace", "all_checks_passed")
    } | {"cases": cases}


def validate_responses(report: JsonObject) -> int:
    """Validate all measurement/baseline/evaluation responses against committed schemas."""
    from jsonschema import Draft202012Validator

    schemas = Path(__file__).resolve().parents[2] / "schemas"
    validators = {}
    count = 0
    for exchange in report["http_exchanges"]:
        resource = exchange["resource"]
        if resource is None:
            continue
        if resource not in validators:
            schema = json.loads((schemas / f"{resource}.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            validators[resource] = Draft202012Validator(schema)
        values = exchange["response"]["items"] if exchange["collection"] else [exchange["response"]]
        for value in values:
            errors = list(validators[resource].iter_errors(value))
            if errors:
                raise DemoError(f"Schema mismatch for {exchange['path']}: {errors[0].message}")
            count += 1
    return count


def main(argv: Sequence[str] | None = None) -> int:
    """Print actual HTTP results; nonzero exits expose mismatches or transport failures."""
    parser = argparse.ArgumentParser(description=NOTICE)
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, help="Existing local /api/v1 base URL."
    )
    parser.add_argument("--namespace", default="v1", help="Deterministic isolated demo namespace.")
    parser.add_argument(
        "--timeout", type=float, default=10, help="HTTP request timeout in seconds."
    )
    parser.add_argument(
        "--full", action="store_true", help="Include exact HTTP requests and responses."
    )
    parser.add_argument(
        "--validate", action="store_true", help="Check committed schemas with jsonschema."
    )
    args = parser.parse_args(argv)
    try:
        report = run_demo(args.base_url, namespace=args.namespace, timeout=args.timeout)
        if args.validate:
            report["validated_response_payloads"] = validate_responses(report)
            report["schema_validation"] = "passed"
        output = report if args.full else summarize(report)
        if args.validate:
            output["schema_validation"] = report["schema_validation"]
        print(encode(output), end="")
    except (DemoError, ValueError, OSError, ImportError) as error:
        print(f"Sleep HTTP demonstration failed: {error}", file=sys.stderr)
        return 2
    return 0 if report["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
