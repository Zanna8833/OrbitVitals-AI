"""Canonical, reproducible histories, independent crew profiles and explicit policies."""

import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from app.demo_seed.dataset import (
    ACQUISITION_PROTOCOLS,
    CURRENT_START,
    FINAL_AS_OF,
    METRICS,
    REFERENCE_START,
    build_manifest,
    build_plan,
    plan_digest,
)
from app.models import METRIC_CATALOG, MeasurementSource, MetricType, PhysiologicalMeasurement
from app.scenarios import fixtures
from app.scenarios.codec import canonical_json
from app.services.commands import BaselineCommand, EvaluationCommand
from tests.support import load_schema

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_dataset_has_three_distinct_synthetic_longitudinal_crews() -> None:
    plan = build_plan()
    assert len(plan) == len({crew.crew_member_id for crew in plan}) == 3
    assert len({crew.scenario for crew in plan}) == 3
    ids = []
    validator = Draft202012Validator(load_schema("physiological_measurement"))
    for crew in plan:
        assert crew.display_name.startswith("SIMULATED")
        assert {record.metric for record in crew.measurements} == set(METRICS)
        assert (
            min(record.measured_at for record in crew.measurements).date() == REFERENCE_START.date()
        )
        assert max(record.measured_at for record in crew.measurements) > CURRENT_START
        for record in crew.measurements:
            assert record.crew_member_id == crew.crew_member_id
            assert record.measurement_id.startswith(crew.crew_member_id)
            assert record.source == MeasurementSource.SIMULATED
            assert record.unit == METRIC_CATALOG[record.metric].unit
            assert record.data_quality is None
            assert record.measured_at < FINAL_AS_OF
            assert record.interval_end is None or record.interval_end <= FINAL_AS_OF
            payload = record.model_dump(mode="json")
            assert PhysiologicalMeasurement.model_validate(payload) == record
            validator.validate(payload)
            ids.append(record.measurement_id)
    assert len(ids) == len(set(ids)) == 893


def test_commands_reuse_policies_and_never_embed_computed_results() -> None:
    reference_policy = fixtures.baseline_policy()
    for crew in build_plan():
        for command in crew.baselines:
            assert BaselineCommand.model_validate(command.model_dump(mode="json")) == command
            assert command.reference_end <= command.computed_at
            assert (
                command.config.established_min_samples == reference_policy.established_min_samples
            )
            assert command.config.established_min_span == reference_policy.established_min_span
            assert "SIMULATED" in command.config.policy_source
        for spec in crew.evaluations:
            assert (
                EvaluationCommand.model_validate(spec.command.model_dump(mode="json"))
                == spec.command
            )
            assert spec.command.baseline_ids == ()  # Filled only from actual HTTP responses.
            assert spec.command.domain.value in ("sleep", "physical_activity")
            if spec.command.sleep_config is not None:
                assert spec.command.sleep_config == fixtures.sleep_policy()
            if spec.command.activity is not None:
                assert spec.command.activity.policies == fixtures.activity_inputs()[4]
                assert all(
                    session.end_time <= spec.command.window_end
                    for session in spec.command.activity.sessions
                )


def test_session_links_belong_to_the_same_crew_and_scope() -> None:
    for crew in build_plan():
        by_id = {record.measurement_id: record for record in crew.measurements}
        for options in [
            *(item.activity for item in crew.baselines if item.activity is not None),
            *(
                item.command.activity
                for item in crew.evaluations
                if item.command.activity is not None
            ),
        ]:
            for session in options.sessions:
                for identifier in session.measurement_ids:
                    record = by_id[identifier]
                    assert record.crew_member_id == crew.crew_member_id
                    assert session.start_time <= record.measured_at < session.end_time
                    assert record.interval_end <= session.end_time


def test_reused_failure_and_decline_measurements_keep_their_authored_values() -> None:
    _, declining, failures = build_plan()
    sleep_values = [
        record.value
        for record in declining.measurements
        if record.metric in fixtures.SLEEP_METRICS and record.measured_at >= CURRENT_START
    ]
    assert sorted(sleep_values) == sorted(record.value for record in fixtures.restriction_records())
    failure_values = [
        record.value
        for record in failures.measurements
        if record.metric in fixtures.SLEEP_METRICS and record.measured_at >= CURRENT_START
    ]
    assert sorted(failure_values) == sorted(
        record.value for record in fixtures.sensor_failure_records()
    )


def test_manifest_matches_the_committed_machine_readable_artifact() -> None:
    path = BACKEND_ROOT.parent / "docs" / "mission-demo-manifest.json"
    assert path.read_text(encoding="utf-8") == canonical_json(build_manifest())
    assert build_manifest()["evaluated_domains"] == ["sleep", "physical_activity"]
    assert "Unsupported" in build_manifest()["vital_evaluations"]


def test_fresh_plans_and_mutation_cannot_change_later_generation() -> None:
    first = build_plan()
    expected = plan_digest(first)
    assert first == build_plan()
    first[0].measurements[0].value = 999
    assert plan_digest(first) != expected
    assert plan_digest(build_plan()) == expected


def test_acquisition_assumptions_are_fingerprinted_and_manifest_copies_are_independent(
    monkeypatch,
) -> None:
    expected = plan_digest(build_plan())
    manifest = build_manifest()
    manifest["acquisition"]["protocols"]["heart_rate"]["context"] = "Changed returned copy"
    assert plan_digest(build_plan()) == expected
    monkeypatch.setitem(
        ACQUISITION_PROTOCOLS[MetricType.HEART_RATE], "context", "SIMULATED changed protocol"
    )
    assert plan_digest(build_plan()) != expected


def test_manifest_bytes_are_reproducible_across_process_hash_seeds_and_timezones() -> None:
    outputs = []
    for seed, timezone in (("1", "UTC"), ("42", "Europe/Rome")):
        result = subprocess.run(
            [sys.executable, "-m", "app.demo_seed", "manifest"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            check=False,
            timeout=30,
            env={**os.environ, "PYTHONHASHSEED": seed, "TZ": timezone, "PYTHONIOENCODING": "utf-8"},
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["data_kind"] == "simulated"
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
