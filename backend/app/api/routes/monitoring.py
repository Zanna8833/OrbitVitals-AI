"""v0.1 JSON resources and explicit scientific computation commands."""

from collections.abc import Callable
from typing import Annotated, TypeVar

from fastapi import APIRouter, Depends, Path, Query, Request
from pydantic import AwareDatetime

from app.models import (
    METRIC_CATALOG,
    EvaluationResult,
    HealthDomain,
    MetricDefinition,
    MetricType,
    MissionPhaseType,
    PersonalBaseline,
    PhysiologicalMeasurement,
)
from app.services.commands import BaselineCommand, EvaluationCommand, Items, MeasurementBatch
from app.services.integration import IntegrationError, IntegrationService

router = APIRouter(tags=["monitoring"])
CrewId = Annotated[str, Path(min_length=1, max_length=128)]
Timestamp = Annotated[AwareDatetime | None, Query()]
Limit = Annotated[int | None, Query(ge=1, le=1000)]
Result = TypeVar("Result")


def get_service(request: Request) -> IntegrationService:
    return request.app.state.integration_service


Service = Annotated[IntegrationService, Depends(get_service)]


def _compute(operation: Callable[[], Result]) -> Result:
    try:
        return operation()
    except ValueError as error:
        raise IntegrationError(422, str(error)) from error
    except ArithmeticError as error:
        raise IntegrationError(
            422, "Scientific arithmetic is not representable; no result was stored"
        ) from error


def _check_range(start: AwareDatetime | None, end: AwareDatetime | None) -> None:
    if start is not None and end is not None and end <= start:
        raise IntegrationError(422, "end must be after start", ("query",))


@router.get("/metrics", response_model=Items[MetricDefinition])
def metrics() -> Items[MetricDefinition]:
    return Items(items=list(METRIC_CATALOG.values()))


@router.post(
    "/measurements",
    response_model=Items[PhysiologicalMeasurement],
    status_code=201,
    responses={409: {"description": "A measurement ID has conflicting content"}},
)
def ingest_measurements(
    body: MeasurementBatch, service: Service
) -> Items[PhysiologicalMeasurement]:
    return Items(items=service.ingest(body.measurements))


@router.get(
    "/crew-members/{crew_member_id}/measurements", response_model=Items[PhysiologicalMeasurement]
)
def measurements(
    crew_member_id: CrewId,
    service: Service,
    metric: MetricType | None = None,
    start: Timestamp = None,
    end: Timestamp = None,
    limit: Limit = None,
) -> Items[PhysiologicalMeasurement]:
    _check_range(start, end)
    values = [
        value
        for value in service.repository.measurements(crew_member_id)
        if (metric is None or value.metric == metric)
        and (start is None or value.measured_at >= start)
        and (end is None or value.measured_at < end)
    ]
    return Items(items=values[:limit])


@router.get("/crew-members/{crew_member_id}/baselines", response_model=Items[PersonalBaseline])
def baselines(
    crew_member_id: CrewId,
    service: Service,
    metric: MetricType | None = None,
    mission_phase: MissionPhaseType | None = None,
) -> Items[PersonalBaseline]:
    return Items(
        items=[
            value
            for value in service.repository.baselines(crew_member_id)
            if (metric is None or value.metric == metric)
            and (mission_phase is None or value.mission_phase == mission_phase)
        ]
    )


@router.post(
    "/crew-members/{crew_member_id}/baselines", response_model=PersonalBaseline, status_code=201
)
def generate_baseline(
    crew_member_id: CrewId, body: BaselineCommand, service: Service
) -> PersonalBaseline:
    return _compute(lambda: service.generate_baseline(crew_member_id, body))


@router.get("/crew-members/{crew_member_id}/evaluations", response_model=Items[EvaluationResult])
def evaluations(
    crew_member_id: CrewId,
    service: Service,
    domain: HealthDomain | None = None,
    start: Timestamp = None,
    end: Timestamp = None,
    limit: Limit = None,
) -> Items[EvaluationResult]:
    _check_range(start, end)
    values = [
        value
        for value in service.repository.evaluations(crew_member_id)
        if (domain is None or value.domain == domain)
        and (start is None or value.window_end >= start)
        and (end is None or value.window_end < end)
    ]
    return Items(items=values[:limit])


@router.post(
    "/crew-members/{crew_member_id}/evaluations",
    response_model=EvaluationResult,
    status_code=201,
    responses={404: {"description": "A selected crew baseline is missing"}},
)
def generate_evaluation(
    crew_member_id: CrewId, body: EvaluationCommand, service: Service
) -> EvaluationResult:
    return _compute(lambda: service.generate_evaluation(crew_member_id, body))
