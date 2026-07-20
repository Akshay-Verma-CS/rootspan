"""Versioned incident API route handlers."""

from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request, status

from rootspan.api.contracts import IncidentListResponse, ReplayIncidentRequest
from rootspan.api.services import AppServices
from rootspan.domain import IncidentBrief

router = APIRouter(prefix="/api/v1", tags=["incidents"])


def _services(request: Request) -> AppServices:
    return cast(AppServices, request.app.state.services)


@router.post(
    "/incidents/replay",
    response_model=IncidentBrief,
    status_code=status.HTTP_201_CREATED,
)
def replay_incident(payload: ReplayIncidentRequest, request: Request) -> IncidentBrief:
    """Run one deterministic scenario through the production analysis path."""
    try:
        return _services(request).incidents.replay(payload.scenario)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IncidentListResponse:
    """List the most recently completed incidents."""
    return IncidentListResponse(incidents=_services(request).incidents.list(limit=limit))


@router.get("/incidents/{incident_id}", response_model=IncidentBrief)
def get_incident(incident_id: str, request: Request) -> IncidentBrief:
    """Return one complete evidence-linked incident brief."""
    incident = _services(request).incidents.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    return incident
