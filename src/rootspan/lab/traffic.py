"""Generate bounded healthy or failing checkout traffic."""

import argparse
import asyncio
from dataclasses import dataclass

import httpx

from rootspan.lab.app import CheckoutPayload


@dataclass(frozen=True, slots=True)
class TrafficResult:
    attempted: int
    succeeded: int
    failed: int


async def generate_traffic(
    gateway_url: str,
    *,
    mode: str,
    count: int,
) -> TrafficResult:
    payload = (
        CheckoutPayload()
        if mode == "healthy"
        else CheckoutPayload(inventory_version="v2", flag_variant="async-reserve")
    )
    succeeded = 0
    failed = 0
    timeout = httpx.Timeout(3.0, connect=1.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for _ in range(count):
            response = await client.post(
                f"{gateway_url.rstrip('/')}/checkout", json=payload.model_dump()
            )
            if response.is_success:
                succeeded += 1
            else:
                failed += 1
    return TrafficResult(attempted=count, succeeded=succeeded, failed=failed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway-url", default="http://127.0.0.1:9001")
    parser.add_argument("--mode", choices=("healthy", "incident"), default="healthy")
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()
    if args.count < 1 or args.count > 1000:
        parser.error("--count must be between 1 and 1000")
    result = asyncio.run(
        generate_traffic(str(args.gateway_url), mode=str(args.mode), count=int(args.count))
    )
    print(f"attempted={result.attempted} succeeded={result.succeeded} failed={result.failed}")


if __name__ == "__main__":
    main()
