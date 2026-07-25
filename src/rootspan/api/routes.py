"""Versioned incident API route handlers."""

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, HTTPException, Query, Request, status
from starlette.responses import StreamingResponse

from rootspan.api.contracts import (
    AlertmanagerWebhook,
    IncidentListResponse,
    IncidentProgressResponse,
    LiveIncidentRequest,
    ReplayIncidentRequest,
    WebhookResponse,
)
from rootspan.api.services import AppServices
from rootspan.config import Settings
from rootspan.domain import IncidentBrief, IncidentState, TimeWindow
from rootspan.service import LiveInvestigationError

router = APIRouter(prefix="/api/v1", tags=["incidents"])


def _services(request: Request) -> AppServices:
    return cast(AppServices, request.app.state.services)


def _settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


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


@router.post(
    "/incidents/live",
    response_model=IncidentBrief,
    status_code=status.HTTP_201_CREATED,
)
async def investigate_live(payload: LiveIncidentRequest, request: Request) -> IncidentBrief:
    """Run a bounded read-only investigation against the configured SigNoz MCP server."""

    now = datetime.now(UTC)
    window = TimeWindow(
        start=payload.start or now - timedelta(minutes=payload.lookback_minutes),
        end=payload.end or now,
    )
    try:
        return await _services(request).incidents.investigate_live(
            window=window,
            cohort_size=payload.cohort_size,
            target_operation=payload.target_operation,
        )
    except LiveInvestigationError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error


@router.post(
    "/webhooks/signoz",
    response_model=WebhookResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def signoz_webhook(payload: AlertmanagerWebhook, request: Request) -> WebhookResponse:
    """Deduplicate firing alerts and investigate each through the same live path."""

    settings = _settings(request)
    now = datetime.now(UTC)
    earliest = now - timedelta(minutes=settings.live_window_minutes)
    incident_ids: list[str] = []
    closed_incident_ids: list[str] = []
    ignored_resolved = 0
    for alert in payload.alerts:
        event_fingerprint = f"{alert.fingerprint}:{alert.startsAt.astimezone(UTC).isoformat()}"
        if alert.status == "resolved":
            closed_id = _services(request).incidents.close_alert(event_fingerprint)
            if closed_id is None:
                ignored_resolved += 1
            else:
                closed_incident_ids.append(closed_id)
            continue
        start = max(alert.startsAt.astimezone(UTC), earliest)
        target_operation = alert.labels.get("rootspan_target_operation", "gateway.checkout")
        try:
            brief = await _services(request).incidents.investigate_live(
                window=TimeWindow(start=start, end=now),
                cohort_size=settings.live_cohort_size,
                target_operation=target_operation,
                alert_fingerprint=event_fingerprint,
            )
        except LiveInvestigationError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error
        incident_ids.append(brief.incident_id)
    return WebhookResponse(
        incident_ids=tuple(incident_ids),
        closed_incident_ids=tuple(closed_incident_ids),
        ignored_resolved=ignored_resolved,
    )


@router.get("/incidents", response_model=IncidentListResponse)
def list_incidents(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> IncidentListResponse:
    """List the most recently completed incidents."""
    return IncidentListResponse(incidents=_services(request).incidents.list(limit=limit))


@router.get("/incidents/{incident_id}/events", response_model=IncidentProgressResponse)
def incident_events(incident_id: str, request: Request) -> IncidentProgressResponse:
    """Return the exact persisted lifecycle history for a live incident."""

    events = _services(request).incidents.progress(incident_id)
    if not events:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    return IncidentProgressResponse(events=events)


@router.get("/incidents/{incident_id}/events/stream", response_class=StreamingResponse)
async def stream_incident_events(incident_id: str, request: Request) -> StreamingResponse:
    """Stream persisted lifecycle transitions as server-sent events."""

    incidents = _services(request).incidents
    if not incidents.progress(incident_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")

    terminal = {
        IncidentState.READY,
        IncidentState.INSUFFICIENT_EVIDENCE,
        IncidentState.FAILED,
        IncidentState.CLOSED,
    }

    async def generate() -> AsyncIterator[str]:
        delivered = 0
        while True:
            events = incidents.progress(incident_id)
            for event in events[delivered:]:
                payload = json.dumps(event.model_dump(mode="json"), separators=(",", ":"))
                yield f"event: incident.progress\ndata: {payload}\n\n"
            delivered = len(events)
            if events and events[-1].state in terminal:
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.25)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/incidents/{incident_id}", response_model=IncidentBrief)
def get_incident(incident_id: str, request: Request) -> IncidentBrief:
    """Return one complete evidence-linked incident brief."""
    incident = _services(request).incidents.get(incident_id)
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="incident not found")
    return incident
