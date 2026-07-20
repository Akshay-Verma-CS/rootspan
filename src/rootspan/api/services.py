"""Typed service container attached to the FastAPI application."""

from dataclasses import dataclass
from pathlib import Path

from rootspan.service import IncidentService
from rootspan.storage import IncidentRepository


@dataclass(frozen=True, slots=True)
class AppServices:
    incidents: IncidentService

    @classmethod
    def create(cls, database_path: Path) -> "AppServices":
        repository = IncidentRepository(database_path)
        repository.initialize()
        return cls(incidents=IncidentService(repository))
