"""Run the deployed golden path and fail on any unexpected behavior."""

import argparse
import asyncio
from dataclasses import dataclass

import httpx

from rootspan.lab.traffic import TrafficResult, generate_traffic


@dataclass(frozen=True, slots=True)
class SmokeConfig:
    console_url: str
    gateway_url: str
    inventory_url: str
    cohort_size: int = 10


def _require_result(
    result: TrafficResult,
    *,
    expected_successes: int,
    label: str,
) -> None:
    if result.succeeded != expected_successes:
        raise RuntimeError(
            f"{label}: expected {expected_successes} successes, "
            f"observed {result.succeeded} successes and {result.failed} failures"
        )


async def run_smoke(config: SmokeConfig) -> None:
    """Exercise replay, healthy traffic, failure injection, and recovery."""
    console_url = config.console_url.rstrip("/")
    inventory_url = config.inventory_url.rstrip("/")
    timeout = httpx.Timeout(5.0, connect=2.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        console = await client.get(console_url)
        console.raise_for_status()

        replay = await client.post(
            f"{console_url}/api/v1/incidents/replay",
            json={"scenario": "inventory-cohort-timeout"},
        )
        replay.raise_for_status()
        brief = replay.json()
        candidates = brief.get("ranked_candidates", [])
        if brief.get("state") != "READY" or not candidates:
            raise RuntimeError("replay did not return a READY incident with candidates")
        if candidates[0].get("operation_key") != "inventory|inventory.reserve":
            raise RuntimeError("replay did not rank inventory.reserve first")
        incident_id = brief.get("incident_id")
        if not isinstance(incident_id, str):
            raise RuntimeError("replay did not return an incident ID")
        persisted = await client.get(f"{console_url}/api/v1/incidents/{incident_id}")
        persisted.raise_for_status()
        if persisted.json().get("incident_id") != incident_id:
            raise RuntimeError("replayed incident was not persisted")

        healthy = await generate_traffic(
            config.gateway_url,
            mode="healthy",
            count=config.cohort_size,
        )
        _require_result(
            healthy,
            expected_successes=config.cohort_size,
            label="healthy cohort",
        )

        try:
            enabled = await client.post(
                f"{inventory_url}/scenario/failure",
                json={"enabled": True},
            )
            enabled.raise_for_status()
            incident = await generate_traffic(
                config.gateway_url,
                mode="incident",
                count=config.cohort_size,
            )
            _require_result(incident, expected_successes=0, label="incident cohort")
        finally:
            reset = await client.post(
                f"{inventory_url}/scenario/failure",
                json={"enabled": False},
            )
            reset.raise_for_status()

        recovered = await generate_traffic(
            config.gateway_url,
            mode="incident",
            count=1,
        )
        _require_result(recovered, expected_successes=1, label="recovery request")

    print(
        "smoke=passed "
        f"healthy={healthy.succeeded}/{healthy.attempted} "
        f"incident_failures={incident.failed}/{incident.attempted} "
        f"recovered={recovered.succeeded}/{recovered.attempted}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--console-url", default="http://127.0.0.1:5173")
    parser.add_argument("--gateway-url", default="http://127.0.0.1:9001")
    parser.add_argument("--inventory-url", default="http://127.0.0.1:9003")
    parser.add_argument("--cohort-size", type=int, default=10)
    args = parser.parse_args()
    if args.cohort_size < 1 or args.cohort_size > 100:
        parser.error("--cohort-size must be between 1 and 100")
    asyncio.run(
        run_smoke(
            SmokeConfig(
                console_url=str(args.console_url),
                gateway_url=str(args.gateway_url),
                inventory_url=str(args.inventory_url),
                cohort_size=int(args.cohort_size),
            )
        )
    )


if __name__ == "__main__":
    main()
