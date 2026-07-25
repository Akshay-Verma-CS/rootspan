"""Bounded leader/follower coordination for read-only system sentinels."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Protocol

from opentelemetry import trace

from rootspan.domain import (
    BlastRadiusSlice,
    Evidence,
    SentinelFinding,
    SentinelLeaderLease,
    SentinelMeshRun,
    SentinelOutcome,
    SentinelRole,
    TimelineEvent,
    TimeWindow,
    TraceGraph,
)

Clock = Callable[[], datetime]
Observer = Callable[["SentinelContext"], Awaitable["SentinelObservation"]]


class SentinelMeshError(RuntimeError):
    """The sentinel mesh could not produce a safely coordinated result."""


class SentinelMeshUnavailable(SentinelMeshError):
    """No sentinel remained available to lead an investigation."""


@dataclass(frozen=True, slots=True)
class SentinelContext:
    """Bounded incident context shared with system-scoped observers."""

    incident_id: str
    target_operation: str
    window: TimeWindow
    healthy_traces: tuple[TraceGraph, ...]
    failing_traces: tuple[TraceGraph, ...]
    first_failure: datetime | None
    boundary_url: str


@dataclass(frozen=True, slots=True)
class SentinelObservation:
    """A sentinel's compact result before leader compilation."""

    summary: str
    outcome: SentinelOutcome = SentinelOutcome.READY
    evidence: tuple[Evidence, ...] = ()
    timeline: tuple[TimelineEvent, ...] = ()
    blast_radius: tuple[BlastRadiusSlice, ...] = ()
    evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SentinelMeshResult:
    """Compiled agent metadata and deterministic evidence inputs."""

    run: SentinelMeshRun
    evidence: tuple[Evidence, ...]
    timeline: tuple[TimelineEvent, ...]
    blast_radius: tuple[BlastRadiusSlice, ...]


class SentinelAgent(Protocol):
    """One read-only observer attached to a bounded system scope."""

    @property
    def sentinel_id(self) -> str: ...

    @property
    def system(self) -> str: ...

    async def observe(self, context: SentinelContext) -> SentinelObservation: ...


class SentinelLeaderStore(Protocol):
    """Persistent deterministic leader election boundary."""

    def elect_sentinel_leader(
        self,
        *,
        incident_id: str,
        candidates: tuple[str, ...],
        occurred_at: datetime,
        lease_ttl: timedelta,
        force_failover: bool = False,
    ) -> SentinelLeaderLease: ...


class InMemorySentinelLeaderStore:
    """Process-local lease store for contract tests and fixture adapters."""

    def __init__(self) -> None:
        self._leases: dict[str, SentinelLeaderLease] = {}
        self._lock = Lock()

    def elect_sentinel_leader(
        self,
        *,
        incident_id: str,
        candidates: tuple[str, ...],
        occurred_at: datetime,
        lease_ttl: timedelta,
        force_failover: bool = False,
    ) -> SentinelLeaderLease:
        _validate_election(candidates, occurred_at, lease_ttl)
        with self._lock:
            current = self._leases.get(incident_id)
            leader_id, generation = _next_leader(
                current=current,
                candidates=candidates,
                occurred_at=occurred_at,
                force_failover=force_failover,
            )
            lease = SentinelLeaderLease(
                incident_id=incident_id,
                leader_id=leader_id,
                generation=generation,
                expires_at=occurred_at + lease_ttl,
            )
            self._leases[incident_id] = lease
            return lease


class CallbackSentinelAgent:
    """Small adapter for a typed system-specific observation callback."""

    def __init__(self, sentinel_id: str, system: str, observer: Observer) -> None:
        self._sentinel_id = sentinel_id
        self._system = system
        self._observer = observer

    @property
    def sentinel_id(self) -> str:
        return self._sentinel_id

    @property
    def system(self) -> str:
        return self._system

    async def observe(self, context: SentinelContext) -> SentinelObservation:
        return await self._observer(context)


class TraceSystemSentinel:
    """Observe one attached system from the already bounded trace cohorts."""

    def __init__(self, sentinel_id: str, system: str, operation_key: str) -> None:
        self._sentinel_id = sentinel_id
        self._system = system
        self._operation_key = operation_key

    @property
    def sentinel_id(self) -> str:
        return self._sentinel_id

    @property
    def system(self) -> str:
        return self._system

    async def observe(self, context: SentinelContext) -> SentinelObservation:
        healthy_count = _trace_count(context.healthy_traces, self._operation_key)
        failing_count = _trace_count(context.failing_traces, self._operation_key)
        comparable = min(healthy_count, failing_count) >= 2
        return SentinelObservation(
            summary=(
                f"Observed {self._operation_key} in {healthy_count} healthy and "
                f"{failing_count} failing traces."
            ),
            outcome=(SentinelOutcome.READY if comparable else SentinelOutcome.DEGRADED),
            evidence_ids=(f"trace-diff:{self._operation_key}",) if comparable else (),
        )


class SentinelMeshCoordinator:
    """Elect one leader and run system observers with bounded parallelism."""

    def __init__(
        self,
        leader_store: SentinelLeaderStore,
        *,
        clock: Clock | None = None,
        max_concurrency: int = 4,
        lease_ttl: timedelta = timedelta(seconds=30),
    ) -> None:
        if max_concurrency < 1 or max_concurrency > 32:
            raise ValueError("sentinel concurrency must be between 1 and 32")
        if lease_ttl <= timedelta(0):
            raise ValueError("sentinel lease TTL must be positive")
        self._leader_store = leader_store
        self._clock = clock or (lambda: datetime.now(UTC))
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._lease_ttl = lease_ttl
        self._tracer = trace.get_tracer("rootspan.sentinel_mesh")

    async def run(
        self,
        context: SentinelContext,
        agents: Sequence[SentinelAgent],
    ) -> SentinelMeshResult:
        if not agents:
            raise SentinelMeshUnavailable("no sentinels are attached to the incident")
        agent_ids = tuple(agent.sentinel_id for agent in agents)
        if len(agent_ids) != len(set(agent_ids)):
            raise SentinelMeshError("sentinel IDs must be unique")

        started_at = self._clock()
        with self._tracer.start_as_current_span("sentinel.leader.elect") as span:
            lease = self._leader_store.elect_sentinel_leader(
                incident_id=context.incident_id,
                candidates=agent_ids,
                occurred_at=started_at,
                lease_ttl=self._lease_ttl,
            )
            span.set_attribute("rootspan.sentinel.leader", lease.leader_id)
            span.set_attribute("rootspan.sentinel.generation", lease.generation)

        async def run_one(
            agent: SentinelAgent,
        ) -> tuple[SentinelFinding, SentinelObservation | None]:
            observation_started = self._clock()
            try:
                async with self._semaphore:
                    with self._tracer.start_as_current_span("sentinel.observe") as span:
                        span.set_attribute("rootspan.sentinel.id", agent.sentinel_id)
                        span.set_attribute("rootspan.sentinel.system", agent.system)
                        observation = await agent.observe(context)
                        if observation.outcome is SentinelOutcome.FAILED:
                            raise SentinelMeshError(
                                "sentinel observations cannot self-report FAILED"
                            )
                        span.set_attribute("rootspan.sentinel.outcome", observation.outcome.value)
                finding = SentinelFinding(
                    sentinel_id=agent.sentinel_id,
                    system=agent.system,
                    role=SentinelRole.FOLLOWER,
                    outcome=observation.outcome,
                    summary=observation.summary,
                    evidence_ids=observation.evidence_ids,
                    started_at=observation_started,
                    completed_at=self._clock(),
                )
                return finding, observation
            except Exception as error:
                return (
                    SentinelFinding(
                        sentinel_id=agent.sentinel_id,
                        system=agent.system,
                        role=SentinelRole.FOLLOWER,
                        outcome=SentinelOutcome.FAILED,
                        summary="The sentinel stopped safely without changing the observed system.",
                        started_at=observation_started,
                        completed_at=self._clock(),
                        error_code=type(error).__name__,
                    ),
                    None,
                )

        with self._tracer.start_as_current_span("sentinel.delegate") as span:
            span.set_attribute("rootspan.sentinel.count", len(agents))
            results = await asyncio.gather(*(run_one(agent) for agent in agents))

        findings = [finding for finding, _ in results]
        initial_leader = lease.leader_id
        leader_finding = next(item for item in findings if item.sentinel_id == initial_leader)
        previous_leaders: tuple[str, ...] = ()
        if leader_finding.outcome is SentinelOutcome.FAILED:
            available = tuple(
                item.sentinel_id for item in findings if item.outcome is not SentinelOutcome.FAILED
            )
            if not available:
                raise SentinelMeshUnavailable("all attached sentinels failed")
            previous_leaders = (initial_leader,)
            with self._tracer.start_as_current_span("sentinel.leader.failover") as span:
                lease = self._leader_store.elect_sentinel_leader(
                    incident_id=context.incident_id,
                    candidates=available,
                    occurred_at=self._clock(),
                    lease_ttl=self._lease_ttl,
                    force_failover=True,
                )
                span.set_attribute("rootspan.sentinel.previous_leader", initial_leader)
                span.set_attribute("rootspan.sentinel.leader", lease.leader_id)
                span.set_attribute("rootspan.sentinel.generation", lease.generation)

        findings = [
            item.model_copy(
                update={
                    "role": (
                        SentinelRole.LEADER
                        if item.sentinel_id == lease.leader_id
                        else SentinelRole.FOLLOWER
                    )
                }
            )
            for item in findings
        ]
        observations = tuple(observation for _, observation in results if observation is not None)
        evidence = _merge_evidence(observations)
        timeline = tuple(
            sorted(
                (event for item in observations for event in item.timeline),
                key=lambda event: (event.occurred_at, event.title),
            )
        )
        blast_radius = _merge_blast_radius(observations)
        status = (
            SentinelOutcome.READY
            if not previous_leaders
            and all(item.outcome is SentinelOutcome.READY for item in findings)
            else SentinelOutcome.DEGRADED
        )
        run = SentinelMeshRun(
            leader_id=lease.leader_id,
            previous_leader_ids=previous_leaders,
            follower_ids=tuple(
                item.sentinel_id for item in findings if item.sentinel_id != lease.leader_id
            ),
            status=status,
            lease_generation=lease.generation,
            started_at=started_at,
            completed_at=self._clock(),
            findings=tuple(findings),
        )
        return SentinelMeshResult(
            run=run,
            evidence=evidence,
            timeline=timeline,
            blast_radius=blast_radius,
        )


def _trace_count(traces: tuple[TraceGraph, ...], operation_key: str) -> int:
    return sum(
        any(span.operation_key == operation_key for span in trace_graph.spans)
        for trace_graph in traces
    )


def _merge_evidence(observations: tuple[SentinelObservation, ...]) -> tuple[Evidence, ...]:
    merged: dict[str, Evidence] = {}
    for observation in observations:
        for item in observation.evidence:
            existing = merged.get(item.id)
            if existing is not None and existing != item:
                raise SentinelMeshError(f"conflicting sentinel evidence ID: {item.id}")
            merged[item.id] = item
    return tuple(merged[item_id] for item_id in sorted(merged))


def _merge_blast_radius(
    observations: tuple[SentinelObservation, ...],
) -> tuple[BlastRadiusSlice, ...]:
    merged: dict[tuple[str, str], BlastRadiusSlice] = {}
    for observation in observations:
        for item in observation.blast_radius:
            key = (item.dimension, item.value)
            existing = merged.get(key)
            if existing is not None and existing != item:
                raise SentinelMeshError(
                    f"conflicting sentinel blast-radius slice: {item.dimension}={item.value}"
                )
            merged[key] = item
    return tuple(merged[key] for key in sorted(merged))


def _validate_election(
    candidates: tuple[str, ...],
    occurred_at: datetime,
    lease_ttl: timedelta,
) -> None:
    if not candidates or any(not item for item in candidates):
        raise SentinelMeshError("leader election requires named candidates")
    if len(candidates) != len(set(candidates)):
        raise SentinelMeshError("leader election candidates must be unique")
    if occurred_at.tzinfo is None:
        raise SentinelMeshError("leader election time must be timezone-aware")
    if lease_ttl <= timedelta(0):
        raise SentinelMeshError("leader lease TTL must be positive")


def _next_leader(
    *,
    current: SentinelLeaderLease | None,
    candidates: tuple[str, ...],
    occurred_at: datetime,
    force_failover: bool,
) -> tuple[str, int]:
    if not candidates:
        raise SentinelMeshError("leader election requires candidates")
    first_candidate = next(iter(candidates))
    if (
        current is not None
        and current.leader_id in candidates
        and current.expires_at > occurred_at
        and not force_failover
    ):
        return current.leader_id, current.generation
    if current is None:
        return first_candidate, 1
    if current.leader_id in candidates and len(candidates) > 1:
        index = (candidates.index(current.leader_id) + 1) % len(candidates)
        return candidates[index], current.generation + 1
    return first_candidate, current.generation + 1
