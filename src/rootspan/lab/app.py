"""Instrumented gateway, checkout, and inventory roles for the golden incident."""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, Protocol
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException, status
from opentelemetry import metrics, trace
from pydantic import BaseModel, ConfigDict

from rootspan.telemetry import TelemetryConfig, configure_telemetry

logger = logging.getLogger("rootspan.incident_lab")
logging.basicConfig(level=logging.INFO, format="%(message)s")

tracer = trace.get_tracer("rootspan.incident_lab")
meter = metrics.get_meter("rootspan.incident_lab")
request_counter = meter.create_counter(
    "rootspan.lab.requests",
    description="Requests handled by an incident-lab role",
)
failure_counter = meter.create_counter(
    "rootspan.lab.failures",
    description="Injected failures handled by the incident lab",
)


class LabRole(StrEnum):
    GATEWAY = "gateway"
    CHECKOUT = "checkout"
    INVENTORY = "inventory"


@dataclass(frozen=True, slots=True)
class LabConfig:
    role: LabRole
    checkout_url: str = "http://127.0.0.1:9002"
    inventory_url: str = "http://127.0.0.1:9003"
    failure_delay_seconds: float = 0.35
    telemetry_enabled: bool = False
    otlp_endpoint: str = "http://localhost:4318"

    @classmethod
    def from_environment(cls) -> "LabConfig":
        return cls(
            role=LabRole(os.getenv("SERVICE_ROLE", LabRole.GATEWAY)),
            checkout_url=os.getenv("CHECKOUT_URL", "http://127.0.0.1:9002"),
            inventory_url=os.getenv("INVENTORY_URL", "http://127.0.0.1:9003"),
            failure_delay_seconds=float(os.getenv("FAILURE_DELAY_SECONDS", "0.35")),
            telemetry_enabled=os.getenv("ROOTSPAN_OTEL_ENABLED", "false").lower() == "true",
            otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        )


class LabModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CheckoutPayload(LabModel):
    region: str = "ap-south-1"
    customer_tier: Literal["standard", "premium"] = "standard"
    inventory_version: Literal["v1", "v2"] = "v1"
    flag_variant: Literal["control", "async-reserve"] = "control"


class OrderResponse(LabModel):
    status: Literal["placed", "reserved"]
    order_id: str
    role: LabRole


class ScenarioControl(LabModel):
    enabled: bool


class ScenarioStatus(LabModel):
    enabled: bool
    role: LabRole


class DownstreamClient(Protocol):
    async def post(self, url: str, payload: CheckoutPayload) -> httpx.Response: ...


class HttpxDownstreamClient:
    """Bounded HTTP client whose calls are automatically traced."""

    async def post(self, url: str, payload: CheckoutPayload) -> httpx.Response:
        timeout = httpx.Timeout(2.0, connect=1.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            return await client.post(url, json=payload.model_dump())


class FailureState:
    """Process-local deterministic failure switch for the inventory role."""

    def __init__(self) -> None:
        self.enabled = False


def _event(event_name: str, **attributes: str | int | float | bool) -> None:
    span_context = trace.get_current_span().get_span_context()
    payload: dict[str, str | int | float | bool] = {
        "event.name": event_name,
        **attributes,
    }
    if span_context.is_valid:
        payload["trace_id"] = format(span_context.trace_id, "032x")
        payload["span_id"] = format(span_context.span_id, "016x")
    logger.info(json.dumps(payload, sort_keys=True))


def _annotate(payload: CheckoutPayload) -> None:
    span = trace.get_current_span()
    span.set_attribute("region", payload.region)
    span.set_attribute("customer.tier", payload.customer_tier)
    span.set_attribute("inventory.version", payload.inventory_version)
    span.set_attribute("feature_flag.variant", payload.flag_variant)


def create_lab_app(
    config: LabConfig,
    *,
    downstream: DownstreamClient | None = None,
) -> FastAPI:
    """Create one role of the distributed incident lab."""
    application = FastAPI(title=f"RootSpan incident lab: {config.role}")
    client = downstream or HttpxDownstreamClient()
    failure_state = FailureState()

    async def health() -> dict[str, str]:
        return {"status": "ok", "role": config.role.value}

    application.add_api_route("/health", health, methods=["GET"], tags=["system"])

    if config.role is LabRole.GATEWAY:

        async def gateway_checkout(payload: CheckoutPayload) -> OrderResponse:
            request_counter.add(1, {"service.role": config.role.value})
            with tracer.start_as_current_span("gateway.checkout"):
                _annotate(payload)
                response = await client.post(f"{config.checkout_url}/place-order", payload)
                if response.status_code >= 400:
                    _event("gateway.checkout.failed", downstream_status=response.status_code)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="checkout dependency failed",
                    )
                _event("gateway.checkout.completed")
                return OrderResponse(
                    status="placed",
                    order_id=str(response.json()["order_id"]),
                    role=config.role,
                )

        application.add_api_route(
            "/checkout",
            gateway_checkout,
            methods=["POST"],
            response_model=OrderResponse,
        )

    elif config.role is LabRole.CHECKOUT:

        async def checkout_place_order(payload: CheckoutPayload) -> OrderResponse:
            request_counter.add(1, {"service.role": config.role.value})
            with tracer.start_as_current_span("checkout.place_order"):
                _annotate(payload)
                response = await client.post(f"{config.inventory_url}/reserve", payload)
                if response.status_code >= 400:
                    _event("checkout.inventory.failed", downstream_status=response.status_code)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="inventory dependency failed",
                    )
                order_id = str(uuid4())
                _event("checkout.order.placed", order_id=order_id)
                return OrderResponse(status="placed", order_id=order_id, role=config.role)

        application.add_api_route(
            "/place-order",
            checkout_place_order,
            methods=["POST"],
            response_model=OrderResponse,
        )

    else:

        async def inventory_reserve(payload: CheckoutPayload) -> OrderResponse:
            request_counter.add(1, {"service.role": config.role.value})
            with tracer.start_as_current_span("inventory.reserve") as span:
                _annotate(payload)
                should_fail = (
                    failure_state.enabled
                    and payload.region == "ap-south-1"
                    and payload.inventory_version == "v2"
                    and payload.flag_variant == "async-reserve"
                )
                with tracer.start_as_current_span("inventory.db.select"):
                    await asyncio.sleep(0.01)
                    _event("inventory.stock.read")
                if should_fail:
                    await asyncio.sleep(config.failure_delay_seconds)
                    failure_counter.add(1, {"service.role": config.role.value})
                    span.set_attribute("error.type", "InventoryTimeout")
                    span.set_status(trace.Status(trace.StatusCode.ERROR, "InventoryTimeout"))
                    _event(
                        "inventory.reserve.timeout",
                        inventory_version=payload.inventory_version,
                        region=payload.region,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                        detail="inventory reservation timed out",
                    )
                reservation_id = str(uuid4())
                _event("inventory.reserved", reservation_id=reservation_id)
                return OrderResponse(
                    status="reserved",
                    order_id=reservation_id,
                    role=config.role,
                )

        async def control_failure(control: ScenarioControl) -> ScenarioStatus:
            failure_state.enabled = control.enabled
            _event("feature_flag.changed", enabled=control.enabled)
            return ScenarioStatus(enabled=failure_state.enabled, role=config.role)

        async def get_failure() -> ScenarioStatus:
            return ScenarioStatus(enabled=failure_state.enabled, role=config.role)

        application.add_api_route(
            "/reserve",
            inventory_reserve,
            methods=["POST"],
            response_model=OrderResponse,
        )
        application.add_api_route(
            "/scenario/failure",
            control_failure,
            methods=["POST"],
            response_model=ScenarioStatus,
        )
        application.add_api_route(
            "/scenario/failure",
            get_failure,
            methods=["GET"],
            response_model=ScenarioStatus,
        )

    configure_telemetry(
        application,
        TelemetryConfig(
            service_name=config.role.value,
            endpoint=config.otlp_endpoint,
            enabled=config.telemetry_enabled,
        ),
    )
    return application
