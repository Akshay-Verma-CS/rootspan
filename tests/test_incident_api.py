"""End-to-end API, analysis, and persistence tests."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from rootspan.api.app import create_app
from rootspan.config import Settings


@pytest.mark.anyio
async def test_replay_persists_and_returns_evidence_linked_brief(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "incidents.db", cors_origins=())
    transport = ASGITransport(app=create_app(settings=settings))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        replay = await client.post(
            "/api/v1/incidents/replay",
            json={"scenario": "inventory-cohort-timeout"},
        )
        assert replay.status_code == 201
        payload = replay.json()
        incident_id = str(payload["incident_id"])
        stored = await client.get(f"/api/v1/incidents/{incident_id}")
        listed = await client.get("/api/v1/incidents")
        listed_again = await client.get("/api/v1/incidents")

    assert payload["state"] == "READY"
    assert payload["ranked_candidates"][0]["operation_key"] == "inventory|inventory.reserve"
    assert stored.status_code == 200
    assert stored.json() == payload
    assert listed.status_code == 200
    assert listed.json()["incidents"][0]["incident_id"] == incident_id
    assert listed_again.status_code == 200
    assert listed_again.json() == listed.json()


@pytest.mark.anyio
async def test_unknown_scenario_returns_not_found(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "incidents.db", cors_origins=())
    transport = ASGITransport(app=create_app(settings=settings))

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/incidents/replay",
            json={"scenario": "not-a-scenario"},
        )

    assert response.status_code == 404
    assert response.json() == {"detail": "unknown scenario: not-a-scenario"}
