"""Internal adapter for the backend's NASA Dataset Evidence Adapter (contract 1.0.0).

The backend exposes `GET /api/v1/nasa-evidence?topic=...` (see
`docs/nasa-evidence-adapter.md` on the branch that adds it). It returns authored context
about two NASA ground studies (UTMB bed-rest Actigraphy and MR001G tilt), their
provenance and their limitations. This module reads it through the same GET-only client
as the crew data, validates it, and keeps only what the agent may show:

- items are research context about terrestrial bed-rest volunteers, never crew data;
- a response with synthetic test findings, an unknown contract version or an item that
  claims crew telemetry, clinical validation or NASA endorsement is rejected as a whole;
- variables keep their unit status; an unresolved MR001G unit stays null;
- the adapter's structural counts (records, cells) are not forwarded: they describe file
  shape, and next to crew values they could be read as physiological figures.

The model never sees this evidence. It is attached by the program, with fixed wording,
so a participant of a NASA study cannot be turned into a simulated astronaut.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from orbit_agent.backend_client import BackendUnavailable, ReadOnlyBackendClient
from orbit_agent.models import (
    DatasetEvidence,
    DatasetEvidenceFailure,
    DatasetEvidenceItem,
    DatasetVariable,
)

CONTRACT_VERSION = "1.0.0"
_TOPICS = ("sleep", "actigraphy", "heart_rate", "blood_pressure", "cardiovascular_adaptation")
_ALLOWED_SOURCE_HOSTS = {"nlsp.nasa.gov"}
_MAX_TOPICS = 2

# A question asks for research context when it names it. The words are an engineering
# choice; without them the section is not requested, so ordinary explanations stay short.
_RESEARCH_CUE = re.compile(
    r"\b(nasa|dataset\w*|data ?set\w*|bed ?rest|ground[- ]stud\w*|analog\w*|research|"
    r"stud(y|ies)|evidence|literature|volunteer\w*)\b",
    re.IGNORECASE,
)
# Topics that the adapter serves, by the words that name them.
_TOPIC_WORDS: dict[str, re.Pattern[str]] = {
    "heart_rate": re.compile(r"\b(heart[- ]?rate|pulse|hr)\b", re.IGNORECASE),
    "blood_pressure": re.compile(r"\b(blood pressure|systolic|diastolic|bp)\b", re.IGNORECASE),
    "cardiovascular_adaptation": re.compile(
        r"\b(cardiovascular|orthostatic|tilt\w*|fainting)\b", re.IGNORECASE
    ),
    "actigraphy": re.compile(r"\b(actigraph\w*|wrist)\b", re.IGNORECASE),
    "sleep": re.compile(r"\bsleep\w*\b", re.IGNORECASE),
}


def plan_topics(question: str | None, domains: list[str]) -> list[str]:
    """Adapter topics worth requesting for this question, at most two.

    Heart rate, blood pressure and cardiovascular words always qualify: the backend does
    not evaluate those signals, so dataset context is the only evidence the adapter can
    add. Sleep and actigraphy qualify only when the question asks for research context.
    """
    text = question or ""
    research = bool(_RESEARCH_CUE.search(text))
    topics = [
        topic
        for topic in ("heart_rate", "blood_pressure", "cardiovascular_adaptation")
        if _TOPIC_WORDS[topic].search(text)
    ]
    if research:
        if _TOPIC_WORDS["actigraphy"].search(text):
            topics.append("actigraphy")
        elif _TOPIC_WORDS["sleep"].search(text) or (not topics and "sleep" in domains):
            topics.append("sleep")
    return topics[:_MAX_TOPICS]


class DatasetEvidenceRejected(Exception):
    """The adapter answered with something the agent must not show."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DatasetEvidenceRejected(f"missing text field {name}")
    return value


def _item(raw: dict[str, Any], topic: str) -> DatasetEvidenceItem:
    if raw.get("topic") != topic:
        raise DatasetEvidenceRejected("item topic disagrees with the request")
    for field, expected in (
        ("evidence_scope", "scientific_context_only"),
        ("study_context", "terrestrial_bed_rest_analogue"),
        ("crew_telemetry", False),
        ("clinically_validated", False),
        ("nasa_endorsement", False),
        ("redistribution_status", "unconfirmed"),
    ):
        if raw.get(field) != expected:
            raise DatasetEvidenceRejected(f"{field} is {raw.get(field)!r}, not {expected!r}")
    url = _text(raw.get("nasa_source_url"), "nasa_source_url")
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in _ALLOWED_SOURCE_HOSTS:
        raise DatasetEvidenceRejected("source URL is not a NASA Life Sciences Portal page")
    verification = raw.get("source_verification") or {}
    state = verification.get("state")
    if state not in {"not_configured", "verified", "unavailable", "rejected"}:
        # `synthetic_fixture_verified` exists only in the adapter's own tests.
        raise DatasetEvidenceRejected(f"source verification state {state!r} is not accepted")
    variables = []
    for variable in raw.get("relevant_variables") or []:
        unit_status = variable.get("unit_verification")
        unit = variable.get("canonical_unit")
        if unit_status not in {"reviewed_source_dictionary", "unresolved"}:
            raise DatasetEvidenceRejected("unknown unit verification status")
        if unit_status == "unresolved" and unit is not None:
            raise DatasetEvidenceRejected("a unit is given although it is unresolved")
        variables.append(
            DatasetVariable(
                source_column=_text(variable.get("source_column"), "source_column"),
                description=_text(variable.get("description"), "description"),
                canonical_unit=unit,
                unit_verification=unit_status,
            )
        )
    return DatasetEvidenceItem(
        evidence_id=_text(raw.get("evidence_id"), "evidence_id"),
        dataset_id=_text(raw.get("dataset_id"), "dataset_id"),
        title=_text(raw.get("title"), "title"),
        nasa_source_url=url,
        topic=topic,
        study_population=_text(raw.get("study_population"), "study_population"),
        study_context="terrestrial_bed_rest_analogue",
        evidence_scope="scientific_context_only",
        crew_telemetry=False,
        clinically_validated=False,
        nasa_endorsement=False,
        redistribution_status="unconfirmed",
        source_verification=state,
        variables=variables,
        context=[_text(line, "context") for line in raw.get("context_findings") or []],
        limitations=[_text(line, "limitation") for line in raw.get("limitations") or []],
    )


def parse_response(payload: dict[str, Any], topic: str) -> tuple[str, list, list]:
    """Validate one adapter response. Returns (status, items, failures)."""
    if payload.get("contract_version") != CONTRACT_VERSION:
        raise DatasetEvidenceRejected(
            f"contract version {payload.get('contract_version')!r} is not {CONTRACT_VERSION}"
        )
    if payload.get("contains_synthetic_findings") is not False:
        raise DatasetEvidenceRejected("the response contains synthetic test findings")
    if payload.get("topic") != topic:
        raise DatasetEvidenceRejected("response topic disagrees with the request")
    status = payload.get("status")
    if status not in {"ok", "partial", "unavailable", "no_matching_evidence"}:
        raise DatasetEvidenceRejected(f"unknown status {status!r}")
    items = [_item(raw, topic) for raw in payload.get("items") or []]
    failures = [
        DatasetEvidenceFailure(
            dataset_id=str(raw.get("dataset_id")),
            code=str(raw.get("code")),
            message=str(raw.get("message")),
        )
        for raw in payload.get("failures") or []
    ]
    return status, items, failures


def retrieve(
    backend: ReadOnlyBackendClient,
    question: str | None,
    domains: list[str],
    *,
    enabled: bool = True,
) -> DatasetEvidence:
    """Read the adapter for the planned topics. Never raises; failures are reported."""
    topics = plan_topics(question, domains)
    if not enabled:
        return DatasetEvidence(status="disabled", topics=topics, reason="Disabled in settings.")
    if not topics:
        return DatasetEvidence(
            status="not_requested",
            reason="The question does not ask for NASA dataset context.",
        )
    items: list[DatasetEvidenceItem] = []
    failures: list[DatasetEvidenceFailure] = []
    statuses: list[str] = []
    for topic in topics:
        try:
            status, found, failed = parse_response(backend.nasa_evidence(topic), topic)
        except BackendUnavailable as error:
            return DatasetEvidence(
                status="endpoint_unavailable",
                topics=topics,
                reason=f"The NASA dataset evidence endpoint could not be read: {error}",
            )
        except DatasetEvidenceRejected as error:
            return DatasetEvidence(
                status="rejected",
                topics=topics,
                reason=f"The NASA dataset evidence was not used: {error}.",
            )
        statuses.append(status)
        # One entry per dataset: the first topic that returned it is the most specific.
        known = {item.dataset_id for item in items}
        items.extend(item for item in found if item.dataset_id not in known)
        failures.extend(failed)
    overall = (
        "partial"
        if "partial" in statuses or (items and failures)
        else "ok"
        if items
        else "unavailable"
        if failures
        else "no_matching_evidence"
    )
    return DatasetEvidence(
        status=overall,
        topics=topics,
        reason="Requested because the question names: " + ", ".join(topics) + ".",
        items=items,
        failures=failures,
    )
