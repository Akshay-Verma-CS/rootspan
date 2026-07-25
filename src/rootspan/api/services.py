"""Typed service container attached to the FastAPI application."""

from dataclasses import dataclass

from rootspan.config import Settings
from rootspan.gateway import McpSigNozGateway
from rootspan.live import LiveScenarioCollector
from rootspan.sentinel import SentinelMeshCoordinator
from rootspan.service import IncidentService
from rootspan.storage import IncidentRepository


@dataclass(frozen=True, slots=True)
class AppServices:
    incidents: IncidentService

    @classmethod
    def create(cls, settings: Settings) -> "AppServices":
        repository = IncidentRepository(settings.database_path)
        repository.initialize()
        gateway = McpSigNozGateway(
            settings.mcp_endpoint,
            api_key=settings.signoz_api_key,
            public_url=settings.signoz_public_url,
        )
        return cls(
            incidents=IncidentService(
                repository,
                live_collector=LiveScenarioCollector(
                    gateway,
                    sentinel_mesh=SentinelMeshCoordinator(repository),
                ),
            )
        )
