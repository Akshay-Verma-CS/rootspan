"""Functional tests for role-configured incident-lab behavior."""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from rootspan.lab import LabConfig, LabRole, create_lab_app
from rootspan.lab.app import CheckoutPayload


class StubDownstream:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        self.calls: list[tuple[str, CheckoutPayload]] = []

    async def post(self, url: str, payload: CheckoutPayload) -> httpx.Response:
        self.calls.append((url, payload))
        return httpx.Response(
            self.status_code,
            json={"order_id": "downstream-order"},
            request=httpx.Request("POST", url),
        )


@pytest.mark.anyio
async def test_inventory_failure_is_scoped_and_resettable() -> None:
    config = LabConfig(
        role=LabRole.INVENTORY,
        failure_delay_seconds=0,
        telemetry_enabled=False,
    )
    transport = ASGITransport(app=create_lab_app(config))

    async with AsyncClient(transport=transport, base_url="http://inventory") as client:
        enabled = await client.post("/scenario/failure", json={"enabled": True})
        healthy = await client.post(
            "/reserve",
            json={"inventory_version": "v1", "flag_variant": "control"},
        )
        failing = await client.post(
            "/reserve",
            json={"inventory_version": "v2", "flag_variant": "async-reserve"},
        )
        reset = await client.post("/scenario/failure", json={"enabled": False})
        recovered = await client.post(
            "/reserve",
            json={"inventory_version": "v2", "flag_variant": "async-reserve"},
        )

    assert enabled.json()["enabled"] is True
    assert healthy.status_code == 200
    assert failing.status_code == 504
    assert reset.json()["enabled"] is False
    assert recovered.status_code == 200


@pytest.mark.anyio
async def test_gateway_propagates_dimensions_to_checkout() -> None:
    downstream = StubDownstream(status_code=200)
    config = LabConfig(role=LabRole.GATEWAY, checkout_url="http://checkout")
    transport = ASGITransport(app=create_lab_app(config, downstream=downstream))

    async with AsyncClient(transport=transport, base_url="http://gateway") as client:
        response = await client.post(
            "/checkout",
            json={
                "region": "ap-south-1",
                "customer_tier": "premium",
                "inventory_version": "v2",
                "flag_variant": "async-reserve",
            },
        )

    assert response.status_code == 200
    assert len(downstream.calls) == 1
    url, payload = downstream.calls[0]
    assert url == "http://checkout/place-order"
    assert payload.customer_tier == "premium"
    assert payload.inventory_version == "v2"


@pytest.mark.anyio
async def test_checkout_turns_inventory_timeout_into_dependency_failure() -> None:
    downstream = StubDownstream(status_code=504)
    config = LabConfig(role=LabRole.CHECKOUT, inventory_url="http://inventory")
    transport = ASGITransport(app=create_lab_app(config, downstream=downstream))

    async with AsyncClient(transport=transport, base_url="http://checkout") as client:
        response = await client.post("/place-order", json={})

    assert response.status_code == 502
    assert response.json() == {"detail": "inventory dependency failed"}
