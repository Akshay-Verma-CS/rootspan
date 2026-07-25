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
    mcp_endpoint: str = "http://localhost:8000/mcp"
    signoz_api_key: str = ""
    signoz_public_url: str = "http://localhost:8080"
    live_window_minutes: int = 15
    live_cohort_size: int = 10

    @classmethod
    def from_environment(cls) -> "Settings":
        origins = os.getenv("ROOTSPAN_CORS_ORIGINS", "http://localhost:5173")
        return cls(
            database_path=Path(os.getenv("ROOTSPAN_DATABASE_PATH", "rootspan.db")),
            cors_origins=tuple(value.strip() for value in origins.split(",") if value.strip()),
            telemetry_enabled=os.getenv("ROOTSPAN_OTEL_ENABLED", "false").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
            mcp_endpoint=os.getenv("ROOTSPAN_MCP_ENDPOINT", "http://localhost:8000/mcp"),
            signoz_api_key=os.getenv("SIGNOZ_API_KEY", ""),
            signoz_public_url=os.getenv("ROOTSPAN_SIGNOZ_PUBLIC_URL", "http://localhost:8080"),
            live_window_minutes=_bounded_int("ROOTSPAN_LIVE_WINDOW_MINUTES", 15, 1, 1440),
            live_cohort_size=_bounded_int("ROOTSPAN_LIVE_COHORT_SIZE", 10, 2, 100),
        )


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
