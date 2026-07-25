"""FastAPI application factory."""

from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rootspan import __version__
from rootspan.api.routes import router
from rootspan.api.services import AppServices
from rootspan.config import Settings
from rootspan.telemetry import TelemetryConfig, configure_telemetry


class HealthResponse(BaseModel):
    """Public liveness response."""

    status: Literal["ok"] = "ok"
    service: Literal["rootspan-api"] = "rootspan-api"
    version: str


async def health() -> HealthResponse:
    """Report process liveness and the running service version."""
    return HealthResponse(version=__version__)


def create_app(
    *,
    settings: Settings | None = None,
    services: AppServices | None = None,
) -> FastAPI:
    """Create the RootSpan API with explicit versioned routes."""
    resolved_settings = settings or Settings.from_environment()
    resolved_services = services or AppServices.create(resolved_settings)
    application = FastAPI(
        title="RootSpan API",
        summary="Evidence-bound incident correlation for SigNoz",
        version=__version__,
    )
    application.state.services = resolved_services
    application.state.settings = resolved_settings
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    application.add_api_route(
        "/api/v1/health",
        health,
        methods=["GET"],
        tags=["system"],
        response_model=HealthResponse,
    )
    application.include_router(router)
    configure_telemetry(
        application,
        TelemetryConfig(
            service_name="rootspan-api",
            endpoint=resolved_settings.otlp_endpoint,
            enabled=resolved_settings.telemetry_enabled,
        ),
    )

    return application


app = create_app()
