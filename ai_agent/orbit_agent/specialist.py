"""Plug-in point for an optional second-opinion model.

The agent works with one model. A specialist (for example a biomedical model maintained
by another team member) can be connected later through an adapter, without changing the
pipeline. This module makes no assumption about how that specialist is called or what
it returns: the adapter owns the translation in both directions.

Contract of an adapter:

- Input: a `SpecialistRequest` holding the question, the backend facts and the
  interpretations that already passed verification. Plain data, no agent internals.
- Output: a `SpecialistReport` with zero or more `SpecialistOpinion` items, each about
  one interpretation, plus an opaque `raw` payload kept for inspection.

What the agent does with a report is deliberately narrow. A specialist can make the
explanation more cautious, never less:

- `unsupported`: the interpretation is removed.
- `overstated`: the interpretation is kept with confidence `low`.
- `supported` / `no_opinion`: nothing changes.
- A comment is shown only if it passes the same verifier as any other sentence.

A specialist cannot add observations, numbers, citations or suggested checks. If the
adapter is unavailable or fails, the explanation is returned without it and says so.

To connect a specialist:

    from orbit_agent.specialist import register_specialist

    register_specialist("my-specialist", lambda settings: MyAdapter(settings))

and start the service with `ORBITVITALS_AGENT_SPECIALIST=my-specialist`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from orbit_agent.config import Settings
from orbit_agent.models import Fact, Interpretation

Verdict = Literal["supported", "overstated", "unsupported", "no_opinion"]


@dataclass(frozen=True)
class SpecialistRequest:
    crew_member_id: str
    question: str | None
    facts: tuple[Fact, ...]
    interpretations: tuple[Interpretation, ...]


@dataclass(frozen=True)
class SpecialistOpinion:
    statement_id: str
    verdict: Verdict
    comment: str | None = None


@dataclass(frozen=True)
class SpecialistReport:
    opinions: tuple[SpecialistOpinion, ...] = ()
    model: str | None = None
    duration_ms: float | None = None
    # Whatever the specialist returned, untouched. Never shown to the operator.
    raw: Any = field(default=None, compare=False)


class SpecialistError(Exception):
    """The specialist could not produce a report. The agent continues without it."""


@runtime_checkable
class SpecialistAdapter(Protocol):
    name: str

    def is_available(self) -> bool:
        """Cheap check that the specialist can be called right now."""
        ...

    def review(self, request: SpecialistRequest) -> SpecialistReport:
        """Return opinions about `request.interpretations`. Raise `SpecialistError` on failure."""
        ...


class NoSpecialist:
    """Default adapter: no second model is configured."""

    name = "none"

    def is_available(self) -> bool:
        return False

    def review(self, request: SpecialistRequest) -> SpecialistReport:
        raise SpecialistError("No specialist is configured")


SpecialistFactory = Callable[[Settings], SpecialistAdapter]
_REGISTRY: dict[str, SpecialistFactory] = {"none": lambda settings: NoSpecialist()}


def register_specialist(name: str, factory: SpecialistFactory) -> None:
    """Make an adapter selectable through `ORBITVITALS_AGENT_SPECIALIST=<name>`."""
    if not name or name == "none":
        raise ValueError("A specialist needs a name other than 'none'")
    _REGISTRY[name] = factory


def registered_specialists() -> list[str]:
    return sorted(_REGISTRY)


def create_specialist(settings: Settings) -> SpecialistAdapter:
    try:
        factory = _REGISTRY[settings.specialist]
    except KeyError:
        raise ValueError(
            f"Unknown specialist {settings.specialist!r}. Registered: "
            f"{', '.join(registered_specialists())}"
        ) from None
    return factory(settings)


def should_consult(interpretations: list[Interpretation]) -> tuple[bool, str]:
    """A second opinion is requested only for readings of the crew member's physiology.

    Explanations about data quality or insufficient data contain no biomedical reading
    to review, so a second inference would add latency without a possible benefit.
    """
    if any(item.kind == "screening_signal" for item in interpretations):
        return True, "The explanation contains a reading of a screening result."
    return False, "The explanation contains no physiological reading to review."
