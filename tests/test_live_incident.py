"""Live orchestration, persisted progress, deduplication, and abstention tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from rootspan.api.app import create_app
from rootspan.api.services import AppServices
from rootspan.config import Settings
from rootspan.correlation import CorrelationAnalyzer
from rootspan.domain import IncidentState, SentinelOutcome, TimeWindow
from rootspan.fixtures.loader import load_scenario
from rootspan.gateway import FixtureTelemetryGateway
from rootspan.live import LiveScenarioCollector
from rootspan.sentinel import SentinelMeshCoordinator
from rootspan.service import IncidentService
from rootspan.storage import IncidentRepository


def _clock() -> datetime:
    return datetime(2026, 7, 25, 8, tzinfo=UTC)


def _service(
    path: Path,
    *,
    one_per_cohort: bool = False,
    no_failing_traces: bool = False,
) -> IncidentService:
    fixture = load_scenario("inventory-cohort-timeout")
    if one_per_cohort:
        fixture = fixture.model_copy(
            update={
                "healthy_traces": fixture.healthy_traces[:1],
                "failing_traces": fixture.failing_traces[:1],
            }
        )
    if no_failing_traces:
        fixture = fixture.model_copy(update={"failing_traces": ()})
    repository = IncidentRepository(path)
    repository.initialize()
    return IncidentService(
        repository,
        analyzer=CorrelationAnalyzer(clock=_clock),
        live_collector=LiveScenarioCollector(
            FixtureTelemetryGateway(fixture),
            clock=_clock,
            sentinel_mesh=SentinelMeshCoordinator(repository, clock=_clock),
        ),
        clock=_clock,
    )


def _window() -> TimeWindow:
    return TimeWindow(start=_clock() - timedelta(minutes=15), end=_clock())


@pytest.mark.anyio
async def test_live_run_persists_ordered_stages_and_deduplicates_alerts(tmp_path: Path) -> None:
    service = _service(tmp_path / "live.db")

    first = await service.investigate_live(
        window=_window(), cohort_size=10, alert_fingerprint="alert-123"
    )
    duplicate = await service.investigate_live(
        window=_window(), cohort_size=10, alert_fingerprint="alert-123"
    )

    assert first.state is IncidentState.READY
    assert first.ranked_candidates[0].operation_key == "inventory|inventory.reserve"
    assert first.sentinel_mesh is not None
    assert first.sentinel_mesh.leader_id == "sentinel.gateway"
    assert first.sentinel_mesh.status is SentinelOutcome.DEGRADED
    assert len(first.sentinel_mesh.findings) == 4
    mesh_evidence_ids = {
        evidence_id
        for finding in first.sentinel_mesh.findings
        for evidence_id in finding.evidence_ids
    }
    assert mesh_evidence_ids <= {item.id for item in first.evidence}
    assert duplicate.incident_id == first.incident_id
    assert [event.state for event in service.progress(first.incident_id)] == [
        IncidentState.RECEIVED,
        IncidentState.COLLECTING,
        IncidentState.COHORTING,
        IncidentState.ALIGNING,
        IncidentState.CORROBORATING,
        IncidentState.COMPILING,
        IncidentState.READY,
    ]


@pytest.mark.anyio
async def test_live_run_abstains_when_each_cohort_has_only_one_trace(tmp_path: Path) -> None:
    service = _service(tmp_path / "insufficient.db", one_per_cohort=True)

    brief = await service.investigate_live(window=_window(), cohort_size=2)

    assert brief.state is IncidentState.INSUFFICIENT_EVIDENCE
    assert brief.ranked_candidates == ()
    assert brief.sentinel_mesh is not None
    mesh_evidence_ids = {
        evidence_id
        for finding in brief.sentinel_mesh.findings
        for evidence_id in finding.evidence_ids
    }
    assert mesh_evidence_ids <= {item.id for item in brief.evidence}
    assert service.progress(brief.incident_id)[-1].state is IncidentState.INSUFFICIENT_EVIDENCE


@pytest.mark.anyio
async def test_live_run_does_not_claim_a_divergence_without_failing_traces(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path / "no-failing.db", no_failing_traces=True)

    brief = await service.investigate_live(window=_window(), cohort_size=10)

    assert brief.state is IncidentState.INSUFFICIENT_EVIDENCE
    assert all(event.title != "Inventory latency diverged" for event in brief.timeline)


@pytest.mark.anyio
async def test_live_api_and_webhook_use_the_same_persisted_path(tmp_path: Path) -> None:
    service = _service(tmp_path / "api-live.db")
    settings = Settings(database_path=tmp_path / "unused.db", cors_origins=())
    app = create_app(settings=settings, services=AppServices(incidents=service))
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        overlong = await client.post(
            "/api/v1/incidents/live",
            json={
                "start": "2026-07-23T08:00:00Z",
                "end": "2026-07-25T08:00:00Z",
                "cohort_size": 10,
            },
        )
        live = await client.post(
            "/api/v1/incidents/live",
            json={
                "start": "2026-07-25T07:45:00Z",
                "end": "2026-07-25T08:00:00Z",
                "cohort_size": 10,
            },
        )
        assert live.status_code == 201
        progress = await client.get(f"/api/v1/incidents/{live.json()['incident_id']}/events")
        stream = await client.get(f"/api/v1/incidents/{live.json()['incident_id']}/events/stream")
        webhook = await client.post(
            "/api/v1/webhooks/signoz",
            json={
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "startsAt": "2026-07-25T07:55:00Z",
                        "fingerprint": "webhook-fingerprint",
                        "labels": {"rootspan_target_operation": "gateway.checkout"},
                    }
                ],
            },
        )
        webhook_duplicate = await client.post(
            "/api/v1/webhooks/signoz",
            json={
                "status": "firing",
                "alerts": [
                    {
                        "status": "firing",
                        "startsAt": "2026-07-25T07:55:00Z",
                        "fingerprint": "webhook-fingerprint",
                    }
                ],
            },
        )
        resolved = await client.post(
            "/api/v1/webhooks/signoz",
            json={
                "status": "resolved",
                "alerts": [
                    {
                        "status": "resolved",
                        "startsAt": "2026-07-25T07:55:00Z",
                        "fingerprint": "webhook-fingerprint",
                    }
                ],
            },
        )
        closed_id = webhook.json()["incident_ids"][0]
        closed = await client.get(f"/api/v1/incidents/{closed_id}")

    assert overlong.status_code == 422
    assert progress.status_code == 200
    assert live.json()["sentinel_mesh"]["leader_id"] == "sentinel.gateway"
    assert len(live.json()["sentinel_mesh"]["findings"]) == 4
    assert progress.json()["events"][-1]["state"] == "READY"
    assert stream.status_code == 200
    assert '"state":"READY"' in stream.text
    assert webhook.status_code == 202
    assert webhook_duplicate.json()["incident_ids"] == webhook.json()["incident_ids"]
    assert resolved.json()["closed_incident_ids"] == webhook.json()["incident_ids"]
    assert closed.json()["state"] == "CLOSED"
