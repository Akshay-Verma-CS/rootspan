"""Run the deployed golden path and fail on any unexpected behavior."""

import argparse
import asyncio
from dataclasses import dataclass

import httpx

from rootspan.api.contracts import IncidentProgressResponse
from rootspan.domain import IncidentBrief, IncidentState
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
    """Exercise replay, live correlation, failure injection, and recovery."""
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
        brief = IncidentBrief.model_validate(replay.json(), extra="ignore")
        if brief.state is not IncidentState.READY or not brief.ranked_candidates:
            raise RuntimeError("replay did not return a READY incident with candidates")
        if brief.ranked_candidates[0].operation_key != "inventory|inventory.reserve":
            raise RuntimeError("replay did not rank inventory.reserve first")
        incident_id = brief.incident_id
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

            live_brief: IncidentBrief | None = None
            for attempt in range(5):
                live = await client.post(
                    f"{console_url}/api/v1/incidents/live",
                    json={"lookback_minutes": 15, "cohort_size": config.cohort_size},
                )
                live.raise_for_status()
                candidate = IncidentBrief.model_validate(live.json(), extra="ignore")
                if candidate.state is IncidentState.READY:
                    live_brief = candidate
                    break
                if attempt < 4:
                    await asyncio.sleep(1)
            if live_brief is None:
                raise RuntimeError("live SigNoz investigation did not become READY")
            if not live_brief.ranked_candidates:
                raise RuntimeError("live investigation returned no ranked candidates")
            if live_brief.ranked_candidates[0].operation_key != "inventory|inventory.reserve":
                raise RuntimeError("live investigation did not rank inventory.reserve first")
            evidence_signals = {item.signal for item in live_brief.evidence}
            if not {"trace", "log", "metric", "change", "topology"} <= evidence_signals:
                raise RuntimeError(
                    "live investigation did not return all required evidence signals"
                )
            live_incident_id = live_brief.incident_id
            events = await client.get(f"{console_url}/api/v1/incidents/{live_incident_id}/events")
            events.raise_for_status()
            progress = IncidentProgressResponse.model_validate(events.json()).events
            if not progress or progress[-1].state is not IncidentState.READY:
                raise RuntimeError("live investigation lifecycle was not persisted through READY")
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
        # Allow the collector's one-second batch window to flush before storage assertions.
        await asyncio.sleep(2)

    print(
        "smoke=passed "
        f"healthy={healthy.succeeded}/{healthy.attempted} "
        f"incident_failures={incident.failed}/{incident.attempted} "
        f"live_incident={live_incident_id} "
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
