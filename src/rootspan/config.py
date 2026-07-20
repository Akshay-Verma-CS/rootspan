"""Environment-backed application settings with explicit defaults."""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime configuration for the API process."""

    database_path: Path
    cors_origins: tuple[str, ...]
    telemetry_enabled: bool = False
    otlp_endpoint: str = "http://localhost:4318"

    @classmethod
    def from_environment(cls) -> "Settings":
        origins = os.getenv("ROOTSPAN_CORS_ORIGINS", "http://localhost:5173")
        return cls(
            database_path=Path(os.getenv("ROOTSPAN_DATABASE_PATH", "rootspan.db")),
            cors_origins=tuple(value.strip() for value in origins.split(",") if value.strip()),
            telemetry_enabled=os.getenv("ROOTSPAN_OTEL_ENABLED", "false").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        )
