"""Building blocks shared by every OrbitVitals data contract."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Opaque, non-empty identifier. Clients must not parse it; UUIDs are recommended.
Identifier = Annotated[str, StringConstraints(min_length=1, max_length=128)]

# Dimensionless value between 0 and 1 inclusive.
UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]


class ContractModel(BaseModel):
    """Base class of every model in the shared data contract.

    Unknown fields are rejected so that typos and contract drift surface early.
    """

    model_config = ConfigDict(extra="forbid")


class HealthDomain(StrEnum):
    """Functional area a metric or an evaluation belongs to."""

    VITAL_SIGNS = "vital_signs"
    SLEEP = "sleep"
    PHYSICAL_ACTIVITY = "physical_activity"
    NUTRITION = "nutrition"


class AlgorithmInfo(ContractModel):
    """Identifies the algorithm that produced a result, for traceability."""

    name: Identifier = Field(description="Stable algorithm identifier, e.g. 'personal_baseline'.")
    version: Identifier = Field(description="Algorithm version, e.g. '0.1.0'.")


def require_chronological(
    start: datetime, end: datetime | None, *, start_field: str, end_field: str
) -> None:
    """Raise `ValueError` when `end` is set and earlier than `start`."""
    if end is not None and end < start:
        raise ValueError(f"{end_field} must not be earlier than {start_field}")
