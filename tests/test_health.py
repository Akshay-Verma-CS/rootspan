"""System-boundary tests for the RootSpan API."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from rootspan.api.app import create_app
from rootspan.config import Settings


@pytest.mark.anyio
async def test_health_reports_service_version(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "health.db", cors_origins=())
    transport = ASGITransport(app=create_app(settings=settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "rootspan-api",
        "version": "0.1.0",
    }
