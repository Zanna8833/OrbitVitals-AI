"""Validate captured submission evidence and draft structure without changing app code."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import unquote

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# The app's models remain authoritative; this documentation script adds no contract.
from app.models import EvaluationResult, PersonalBaseline, PhysiologicalMeasurement
from jsonschema import Draft202012Validator, FormatChecker


def read_json(name: str) -> dict:
    """Read one package-local JSON object."""
    value = json.loads((PACKAGE / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict), f"Expected an object: {name}"
    return value


def check_evidence() -> int:
    """Validate every captured API item with Pydantic and published JSON Schema."""
    manifest = read_json("evidence/capture-manifest.json")
    assert manifest["data_kind"] == "simulated"
    assert manifest["branch"] == "feature/frontend-bridge"
    assert manifest["seed_checks_passed"] is True
    assert manifest["shared_port_8000_used"] is False
    assert manifest["approved_reference"]["visual_acceptance"] == "not_run"
    counts = manifest["crew_resources"]
    assert [row["measurements"] for row in counts] == [188, 171, 139]
    assert sum(row["measurements"] for row in counts) == 498
    assert sum(row["baselines"] for row in counts) == 21
    assert sum(row["evaluations"] for row in counts) == 13
    for name, facts in manifest["files"].items():
        payload = (PACKAGE / "evidence" / name).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == facts["sha256"], name
        assert len(payload) == facts["bytes"], name

    resources = [
        (
            "noor-sleep-evaluations.json",
            EvaluationResult,
            "evaluation_result.schema.json",
        ),
        (
            "noor-sleep-baselines.json",
            PersonalBaseline,
            "personal_baseline.schema.json",
        ),
        (
            "noor-sleep-duration-measurements.json",
            PhysiologicalMeasurement,
            "physiological_measurement.schema.json",
        ),
    ]
    models: dict[str, list] = {}
    validated = 0
    for filename, model, schema_file in resources:
        envelope = read_json(f"evidence/{filename}")
        assert set(envelope) == {"items"}
        schema = json.loads(
            (ROOT / "schemas" / schema_file).read_text(encoding="utf-8")
        )
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        models[filename] = []
        for item in envelope["items"]:
            validator.validate(item)
            parsed = model.model_validate(item)
            assert parsed.crew_member_id == "sim-mission-v1-02"
            models[filename].append(parsed)
            validated += 1

    baseline = models["noor-sleep-baselines.json"][0]
    assert baseline.statistics.median == 480
    assert baseline.sample_count == 14
    assert baseline.status.value == "established"
    assert baseline.metric.value == "sleep_duration"
    measurements = models["noor-sleep-duration-measurements.json"]
    assert len(measurements) == 21
    assert all(
        item.source.value == "simulated" and item.unit == "min" for item in measurements
    )
    results = sorted(
        models["noor-sleep-evaluations.json"], key=lambda item: item.window_end
    )
    # Expected behavior comes from the existing seed fixture, not a new physiological rule.
    assert [result.status.value for result in results] == [
        "insufficient_data",
        "attention",
        "attention",
    ]
    assert [
        step["included_nights_for_display"] for step in manifest["noor_checkpoints"]
    ] == [2, 4, 7]
    assert [
        step["expected_nights_for_display"] for step in manifest["noor_checkpoints"]
    ] == [2, 5, 9]
    for index, result in enumerate(results):
        finding = next(
            item for item in result.findings if item.metric.value == "sleep_duration"
        )
        assert (
            result.evaluation_id == manifest["noor_checkpoints"][index]["evaluation_id"]
        )
        assert result.algorithm.name == "sleep_monitoring_trends"
        assert result.summary.startswith("SIMULATED DATA.")
        assert finding.explanation.startswith("SIMULATED DATA.")
        assert finding.baseline_id == baseline.baseline_id
        assert baseline.window_end <= result.window_start
        assert baseline.mission_phase == result.mission_phase
        assert finding.baseline_value == 480
        assert finding.observed_value == [482.5, 460, 430][index]
        assert finding.absolute_deviation == [2.5, -20, -50][index]
        assert math.isclose(
            finding.relative_deviation,
            finding.absolute_deviation / finding.baseline_value,
        )
        assert finding.data_quality.status.value == "acceptable"
        assert finding.data_quality.completeness is None
        assert "Theil-Sen slope=-15 min/day" in finding.explanation
    with (PACKAGE / "evidence/noor-nine-night-observations.csv").open(
        encoding="utf-8", newline=""
    ) as stream:
        points = list(csv.DictReader(stream))
    assert len(points) == 9
    assert [item["observed_value_min"] for item in points] == [
        "490",
        "475",
        "",
        "445",
        "430",
        "415",
        "",
        "385",
        "370",
    ]
    assert [
        item["night_bucket_start_utc"][:10]
        for item in points
        if item["record_state"] == "missing"
    ] == ["2026-10-14", "2026-10-18"]
    return validated


def check_drafts() -> tuple[int, int]:
    """Check timing, slide count, local links, JSON readability and disclosure status."""
    for path in PACKAGE.rglob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    story = read_json("video-storyboard.json")
    assert story["artifact_kind"] == "storyboard_draft_not_a_recorded_video"
    assert story["language"] == "en"
    assert story["planned_duration_seconds"] == 29
    assert story["official_maximum_seconds"] == 30
    position = 0
    words = 0
    for shot in story["shots"]:
        assert shot["start_seconds"] == position
        assert shot["end_seconds"] > position
        position = shot["end_seconds"]
        words += len(shot["narration"].split())
        assert (PACKAGE / shot["evidence"]).exists()
    assert position == story["planned_duration_seconds"]
    assert words <= 65, "Rehearsal is still required; keep the narration concise"
    captions = (PACKAGE / "video-captions-draft.srt").read_text(encoding="utf-8")
    cues = captions.strip().split("\n\n")
    spoken_text = " ".join(shot["narration"] for shot in story["shots"])
    caption_text = " ".join(" ".join(cue.splitlines()[2:]) for cue in cues)
    assert " ".join(caption_text.split()) == " ".join(spoken_text.split())
    assert "00:00:29,000" in cues[-1].splitlines()[1]
    assert all(len(line) <= 42 for cue in cues for line in cue.splitlines()[2:])
    slides = (PACKAGE / "seven-slide-script.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^## Slide [1-7] ", slides, re.MULTILINE)) == 7
    assert "@not_executed" in (PACKAGE / "demo6-acceptance.feature").read_text(
        encoding="utf-8"
    )
    disclosures = read_json("ai-disclosure.json")
    assert disclosures["medgemma"]["integration_status"] == "pending_confirmation"
    assert disclosures["local_event"]["status"] == "pending_verification"
    assert disclosures["local_event"]["project_url"] is None
    assert (
        disclosures["project_wide_generated_media_inventory"] == "pending_confirmation"
    )
    checked_links = 0
    for path in PACKAGE.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if re.match(r"[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                continue
            relative = unquote(target.split("#", 1)[0].strip("<>"))
            assert (path.parent / relative).exists(), (
                f"Broken local link: {path.name}: {target}"
            )
            checked_links += 1
    return words, checked_links


def main() -> None:
    """Report completed document checks separately from pending visual/clinical validation."""
    validated = check_evidence()
    words, links = check_drafts()
    print(f"Passed: {validated} API items validated with Pydantic and JSON Schema.")
    print(
        f"Passed: payload hashes, replay facts, 29-second plan, {words} narration words."
    )
    print(
        f"Passed: seven-slide draft, disclosures, JSON files and {links} local links."
    )
    print(
        "Not run: Demo 6 frontend acceptance, actual video timing and rendered slide review."
    )
    print(
        "Not established: clinical validation, final event eligibility or public submission."
    )


if __name__ == "__main__":
    main()
