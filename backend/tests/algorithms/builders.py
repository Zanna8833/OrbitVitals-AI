"""Builders of synthetic contract objects for the algorithm tests.

Every value built here is synthetic and chosen for arithmetic convenience. Measurements
are labelled `source: "simulated"` unless a test asks for another source.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from itertools import count

from app.models import (
    METRIC_CATALOG,
    MeasurementSource,
    MetricType,
    MissionPhase,
    MissionPhaseType,
    PhysiologicalMeasurement,
)

T0 = datetime(2026, 9, 1, tzinfo=UTC)
DAY = timedelta(days=1)
HOUR = timedelta(hours=1)
CREW = "crew-test-001"
DEVICE = "sim-device-01"
MISSION = "mission-test-001"

# Timeline returned by `timeline()`.
PRE_FLIGHT_START = T0
LAUNCH_START = T0 + 30 * DAY
IN_FLIGHT_START = T0 + 31 * DAY

_identifiers = count(1)


def measurement(
    value: float,
    at: datetime = T0,
    *,
    metric: MetricType = MetricType.HEART_RATE,
    crew_member_id: str = CREW,
    measurement_id: str | None = None,
    device_id: str | None = DEVICE,
    interval_end: datetime | None = None,
    source: MeasurementSource = MeasurementSource.SIMULATED,
) -> PhysiologicalMeasurement:
    """Build a measurement in the canonical unit of its metric, with a unique identifier."""
    return PhysiologicalMeasurement(
        measurement_id=measurement_id or f"meas-{next(_identifiers):06d}",
        crew_member_id=crew_member_id,
        metric=metric,
        unit=METRIC_CATALOG[metric].unit,
        value=value,
        measured_at=at,
        interval_end=interval_end,
        source=source,
        device_id=device_id,
    )


def series(
    values: Sequence[float], *, start: datetime = T0, step: timedelta = DAY, **fields: object
) -> list[PhysiologicalMeasurement]:
    """Build one measurement per `step`, the first one at `start`."""
    return [
        measurement(value, start + index * step, **fields) for index, value in enumerate(values)
    ]


def phase(
    kind: MissionPhaseType,
    start: datetime,
    end: datetime | None = None,
    *,
    phase_id: str | None = None,
    mission_id: str = MISSION,
) -> MissionPhase:
    return MissionPhase(
        phase_id=phase_id or f"phase-{kind.value}-{start.isoformat()}",
        mission_id=mission_id,
        phase=kind,
        start_time=start,
        end_time=end,
    )


def timeline() -> list[MissionPhase]:
    """Pre-flight for 30 days from `T0`, launch for one day, then an open-ended flight."""
    return [
        phase(MissionPhaseType.PRE_FLIGHT, PRE_FLIGHT_START, LAUNCH_START),
        phase(MissionPhaseType.LAUNCH, LAUNCH_START, IN_FLIGHT_START),
        phase(MissionPhaseType.IN_FLIGHT, IN_FLIGHT_START),
    ]
