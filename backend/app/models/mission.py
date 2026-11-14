"""Mission-phase contract."""

from enum import StrEnum
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from app.models.common import ContractModel, Identifier, require_chronological


class MissionPhaseType(StrEnum):
    """Kinds of mission phase.

    The list is an initial proposal, open to review by the team.
    """

    PRE_FLIGHT = "pre_flight"
    LAUNCH = "launch"
    IN_FLIGHT = "in_flight"
    RETURN_TO_EARTH = "return_to_earth"
    POST_FLIGHT = "post_flight"


class MissionPhase(ContractModel):
    """One entry of a mission timeline: a phase and the period it covers."""

    phase_id: Identifier = Field(description="Unique identifier of this timeline entry.")
    mission_id: Identifier = Field(description="Mission the phase belongs to.")
    phase: MissionPhaseType = Field(description="Kind of phase.")
    label: str | None = Field(default=None, description="Optional display name.")
    start_time: AwareDatetime = Field(description="Start of the phase (UTC).")
    end_time: AwareDatetime | None = Field(
        default=None,
        description="End of the phase (UTC). Null while the phase is ongoing or open-ended.",
    )

    @model_validator(mode="after")
    def _check_period(self) -> Self:
        require_chronological(
            self.start_time, self.end_time, start_field="start_time", end_field="end_time"
        )
        return self
