"""Live SigNoz evidence collection compiled into the replay domain contract."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import TypeVar

from rootspan.domain import (
    AggregateQuery,
    AggregateResult,
    BlastRadiusSlice,
    Evidence,
    LogQuery,
    ScenarioFixture,
    TimelineEvent,
    TimeWindow,
    TraceGraph,
    TraceSearch,
)
from rootspan.gateway import TelemetryGateway, TelemetryGatewayError, response_hash

Clock = Callable[[], datetime]
T = TypeVar("T")
BLAST_DIMENSIONS = ("region", "inventory.version", "feature_flag.variant", "customer.tier")


class LiveScenarioCollector:
    """Collect bounded live evidence without letting transport types reach the core."""

    def __init__(
        self,
        gateway: TelemetryGateway,
        *,
        clock: Clock | None = None,
        max_concurrency: int = 4,
    ) -> None:
        self._gateway = gateway
        self._clock = clock or (lambda: datetime.now(UTC))
        self._semaphore = asyncio.Semaphore(max_concurrency)

    async def collect(
        self,
        *,
        window: TimeWindow,
        cohort_size: int,
        target_operation: str = "gateway.checkout",
    ) -> ScenarioFixture:
        failing_search = TraceSearch(
            operation=target_operation,
            window=window,
            error=True,
            limit=cohort_size,
        )
        healthy_search = failing_search.model_copy(update={"error": False})
        failing_refs, healthy_refs = await asyncio.gather(
            self._gateway.search_trace_ids(failing_search),
            self._gateway.search_trace_ids(healthy_search),
        )
        failing_traces, healthy_traces = await asyncio.gather(
            self._fetch_traces(tuple(item.trace_id for item in failing_refs), window),
            self._fetch_traces(tuple(item.trace_id for item in healthy_refs), window),
        )
        evidence, timeline = await self._corroborate(
            window=window,
            failing_count=len(failing_traces),
            healthy_count=len(healthy_traces),
            first_failure=min((item.observed_at for item in failing_refs), default=None),
            boundary_url=(healthy_refs or failing_refs)[0].web_url
            if healthy_refs or failing_refs
            else "",
        )
        blast_radius = await self._blast_radius(window)
        return ScenarioFixture(
            schema_version="1.0",
            name="live-signoz-inventory-timeout",
            target_operation=target_operation,
            requested_per_cohort=cohort_size,
            match_dimensions=("root.operation", "incident.window"),
            healthy_traces=healthy_traces,
            failing_traces=failing_traces,
            external_evidence=evidence,
            blast_radius=blast_radius,
            timeline=timeline,
            next_queries=(
                "Compare inventory.reserve by feature_flag.variant and inventory.version.",
                "Inspect the earliest failing inventory trace before propagated checkout errors.",
                "Confirm recovery by comparing inventory self-duration with the healthy cohort.",
            ),
        )

    async def _fetch_traces(
        self,
        trace_ids: tuple[str, ...],
        window: TimeWindow,
    ) -> tuple[TraceGraph, ...]:
        async def fetch(trace_id: str) -> TraceGraph:
            async with self._semaphore:
                return await self._gateway.get_trace(trace_id, window)

        results = await asyncio.gather(*(fetch(trace_id) for trace_id in trace_ids))
        return tuple(results)

    async def _corroborate(
        self,
        *,
        window: TimeWindow,
        failing_count: int,
        healthy_count: int,
        first_failure: datetime | None,
        boundary_url: str,
    ) -> tuple[tuple[Evidence, ...], tuple[TimelineEvent, ...]]:
        timeout_logs = await self._optional(
            self._gateway.search_logs(
                LogQuery(
                    search_text="inventory.reserve.timeout",
                    service="inventory",
                    window=window,
                    limit=20,
                )
            ),
            (),
        )
        change_logs = await self._optional(
            self._gateway.search_logs(
                LogQuery(
                    search_text="feature_flag.changed",
                    service="inventory",
                    window=window,
                    limit=10,
                )
            ),
            (),
        )
        failing_latency, healthy_latency = await asyncio.gather(
            self._optional(
                self._gateway.aggregate(
                    AggregateQuery(
                        signal="traces",
                        aggregation="p50",
                        aggregate_on="duration_nano",
                        operation="inventory.reserve",
                        error=True,
                        window=window,
                    )
                ),
                AggregateResult(rows=(), web_url=""),
            ),
            self._optional(
                self._gateway.aggregate(
                    AggregateQuery(
                        signal="traces",
                        aggregation="p50",
                        aggregate_on="duration_nano",
                        operation="inventory.reserve",
                        error=False,
                        window=window,
                    )
                ),
                AggregateResult(rows=(), web_url=""),
            ),
        )

        now = self._clock()
        evidence: list[Evidence] = []
        if timeout_logs:
            evidence.append(
                Evidence(
                    id="live-log:inventory-timeout",
                    signal="log",
                    operation_key="inventory|inventory.reserve",
                    supports=True,
                    observation=(
                        f"SigNoz returned {len(timeout_logs)} inventory timeout log records in "
                        "the bounded incident window."
                    ),
                    query_tool="signoz_search_logs",
                    query_args={
                        "searchText": "inventory.reserve.timeout",
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                    web_url=timeout_logs[0].web_url,
                    response_hash=response_hash(
                        [item.model_dump(mode="json") for item in timeout_logs]
                    ),
                    observed_at=timeout_logs[0].observed_at,
                )
            )
        failing_p50 = _single_value(failing_latency)
        healthy_p50 = _single_value(healthy_latency)
        if failing_p50 is not None and healthy_p50 is not None:
            evidence.append(
                Evidence(
                    id="live-metric:inventory-duration",
                    signal="metric",
                    operation_key="inventory|inventory.reserve",
                    supports=failing_p50 > healthy_p50 * 1.5,
                    observation=(
                        f"Inventory failing p50 was {failing_p50 / 1_000_000:.1f} ms versus "
                        f"{healthy_p50 / 1_000_000:.1f} ms for healthy spans."
                    ),
                    query_tool="signoz_execute_builder_query",
                    query_args={
                        "aggregation": "p50(duration_nano)",
                        "operation": "inventory.reserve",
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                    web_url=failing_latency.web_url or healthy_latency.web_url,
                    response_hash=response_hash(
                        {
                            "failing": failing_latency.model_dump(mode="json"),
                            "healthy": healthy_latency.model_dump(mode="json"),
                        }
                    ),
                    observed_at=now,
                )
            )
        if change_logs:
            evidence.append(
                Evidence(
                    id="live-change:failure-enabled",
                    signal="change",
                    operation_key="inventory|inventory.reserve",
                    supports=True,
                    observation=(
                        "The scoped inventory failure switch changed inside the incident window."
                    ),
                    query_tool="signoz_search_logs",
                    query_args={
                        "searchText": "feature_flag.changed",
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                    web_url=change_logs[0].web_url,
                    response_hash=response_hash(
                        [item.model_dump(mode="json") for item in change_logs]
                    ),
                    observed_at=change_logs[0].observed_at,
                )
            )
        if healthy_count:
            evidence.append(
                Evidence(
                    id="live-boundary:healthy-control",
                    signal="topology",
                    operation_key="inventory|inventory.reserve",
                    supports=False,
                    observation=(
                        f"{healthy_count} comparable traces remained healthy while {failing_count} "
                        "incident traces failed; the divergence is cohort-bounded, not global."
                    ),
                    query_tool="signoz_search_traces",
                    query_args={
                        "operation": "gateway.checkout",
                        "error": False,
                        "start": window.start.isoformat(),
                        "end": window.end.isoformat(),
                    },
                    web_url=boundary_url,
                    response_hash=response_hash(
                        {"healthyTraceCount": healthy_count, "failingTraceCount": failing_count}
                    ),
                    observed_at=now,
                )
            )

        timeline: list[TimelineEvent] = []
        if change_logs:
            timeline.append(
                TimelineEvent(
                    occurred_at=change_logs[0].observed_at,
                    kind="change",
                    title="Scoped inventory failure enabled",
                    detail="SigNoz recorded the incident-lab failure switch change.",
                    evidence_id="live-change:failure-enabled",
                )
            )
        if first_failure is not None:
            timeline.append(
                TimelineEvent(
                    occurred_at=first_failure,
                    kind="observation",
                    title="Inventory latency diverged",
                    detail="The earliest collected failing cohort trace crossed inventory.reserve.",
                    evidence_id="live-metric:inventory-duration"
                    if failing_p50 is not None
                    else None,
                )
            )
        timeline.append(
            TimelineEvent(
                occurred_at=now,
                kind="alert",
                title="Live RootSpan investigation",
                detail="A bounded read-only SigNoz evidence collection was compiled.",
            )
        )
        timeline.sort(key=lambda item: item.occurred_at)
        return tuple(evidence), tuple(timeline)

    async def _blast_radius(self, window: TimeWindow) -> tuple[BlastRadiusSlice, ...]:
        async def aggregate(dimension: str, error: bool) -> AggregateResult:
            async with self._semaphore:
                return await self._gateway.aggregate(
                    AggregateQuery(
                        signal="traces",
                        aggregation="count",
                        operation="inventory.reserve",
                        group_by=(dimension,),
                        error=error,
                        window=window,
                    )
                )

        tasks = [
            aggregate(dimension, error) for dimension in BLAST_DIMENSIONS for error in (False, True)
        ]
        try:
            results = await asyncio.gather(*tasks)
        except TelemetryGatewayError:
            return ()

        slices: list[BlastRadiusSlice] = []
        for index, dimension in enumerate(BLAST_DIMENSIONS):
            healthy = results[index * 2]
            failing = results[index * 2 + 1]
            healthy_counts = _dimension_counts(healthy, dimension)
            failing_counts = _dimension_counts(failing, dimension)
            for value, affected in failing_counts.items():
                total = int(affected + healthy_counts.get(value, 0))
                if affected > 0 and total > 0:
                    slices.append(
                        BlastRadiusSlice(
                            dimension=dimension,
                            value=value,
                            affected=int(affected),
                            total=total,
                        )
                    )
        return tuple(slices)

    @staticmethod
    async def _optional(
        call: Coroutine[object, object, T],
        fallback: T,
    ) -> T:
        try:
            return await call
        except TelemetryGatewayError:
            return fallback


def _single_value(result: AggregateResult) -> float | None:
    return result.rows[0].value if result.rows else None


def _dimension_counts(result: AggregateResult, dimension: str) -> dict[str, float]:
    return {
        value: row.value
        for row in result.rows
        if (value := row.dimensions.get(dimension)) is not None
    }
