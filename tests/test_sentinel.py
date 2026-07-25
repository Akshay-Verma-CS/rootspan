"""Leader election, delegation, degradation, and failover safety tests."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from rootspan.domain import IncidentState, SentinelOutcome, SentinelRole, TimeWindow
from rootspan.fixtures.loader import load_scenario
from rootspan.sentinel import (
    InMemorySentinelLeaderStore,
    SentinelContext,
    SentinelMeshCoordinator,
    SentinelMeshError,
    SentinelMeshUnavailable,
    SentinelObservation,
)
from rootspan.storage import IncidentRepository


def _clock() -> datetime:
    return datetime(2026, 7, 26, 9, tzinfo=UTC)


def _context(incident_id: str = "incident-sentinel") -> SentinelContext:
    fixture = load_scenario("inventory-cohort-timeout")
    return SentinelContext(
        incident_id=incident_id,
        target_operation=fixture.target_operation,
        window=TimeWindow(start=_clock() - timedelta(minutes=15), end=_clock()),
        healthy_traces=fixture.healthy_traces,
        failing_traces=fixture.failing_traces,
        first_failure=_clock() - timedelta(minutes=5),
        boundary_url="http://localhost:8080/traces-explorer",
    )


class FakeSentinel:
    def __init__(
        self,
        sentinel_id: str,
        *,
        outcome: SentinelOutcome = SentinelOutcome.READY,
        fails: bool = False,
    ) -> None:
        self._sentinel_id = sentinel_id
        self._outcome = outcome
        self._fails = fails

    @property
    def sentinel_id(self) -> str:
        return self._sentinel_id

    @property
    def system(self) -> str:
        return self._sentinel_id.removeprefix("sentinel.")

    async def observe(self, context: SentinelContext) -> SentinelObservation:
        if self._fails:
            raise RuntimeError("synthetic sentinel failure")
        return SentinelObservation(
            summary=f"Observed {self.system} for {context.incident_id}.",
            outcome=self._outcome,
        )


@pytest.mark.anyio
async def test_mesh_elects_one_leader_and_delegates_to_ready_followers() -> None:
    coordinator = SentinelMeshCoordinator(InMemorySentinelLeaderStore(), clock=_clock)

    result = await coordinator.run(
        _context(),
        (FakeSentinel("sentinel.gateway"), FakeSentinel("sentinel.inventory")),
    )

    assert result.run.leader_id == "sentinel.gateway"
    assert result.run.follower_ids == ("sentinel.inventory",)
    assert result.run.status is SentinelOutcome.READY
    assert [item.outcome for item in result.run.findings] == [
        SentinelOutcome.READY,
        SentinelOutcome.READY,
    ]


@pytest.mark.anyio
async def test_mesh_keeps_leader_and_surfaces_failed_follower() -> None:
    coordinator = SentinelMeshCoordinator(InMemorySentinelLeaderStore(), clock=_clock)

    result = await coordinator.run(
        _context(),
        (FakeSentinel("sentinel.gateway"), FakeSentinel("sentinel.inventory", fails=True)),
    )

    assert result.run.leader_id == "sentinel.gateway"
    assert result.run.previous_leader_ids == ()
    assert result.run.status is SentinelOutcome.DEGRADED
    assert result.run.findings[0].role is SentinelRole.LEADER
    assert result.run.findings[1].outcome is SentinelOutcome.FAILED
    assert result.run.findings[1].error_code == "RuntimeError"


@pytest.mark.anyio
async def test_mesh_fails_over_when_initial_leader_fails() -> None:
    coordinator = SentinelMeshCoordinator(InMemorySentinelLeaderStore(), clock=_clock)

    result = await coordinator.run(
        _context(),
        (
            FakeSentinel("sentinel.gateway", fails=True),
            FakeSentinel("sentinel.checkout"),
            FakeSentinel("sentinel.inventory"),
        ),
    )

    assert result.run.leader_id == "sentinel.checkout"
    assert result.run.previous_leader_ids == ("sentinel.gateway",)
    assert result.run.lease_generation == 2
    assert result.run.status is SentinelOutcome.DEGRADED
    assert [item.role for item in result.run.findings] == [
        SentinelRole.FOLLOWER,
        SentinelRole.LEADER,
        SentinelRole.FOLLOWER,
    ]


@pytest.mark.anyio
async def test_mesh_fails_safely_when_every_sentinel_fails() -> None:
    coordinator = SentinelMeshCoordinator(InMemorySentinelLeaderStore(), clock=_clock)

    with pytest.raises(SentinelMeshUnavailable, match="all attached sentinels failed"):
        await coordinator.run(
            _context(),
            (FakeSentinel("sentinel.gateway", fails=True),),
        )


@pytest.mark.anyio
async def test_mesh_rejects_duplicate_sentinel_identities() -> None:
    coordinator = SentinelMeshCoordinator(InMemorySentinelLeaderStore(), clock=_clock)

    with pytest.raises(SentinelMeshError, match="unique"):
        await coordinator.run(
            _context(),
            (FakeSentinel("sentinel.gateway"), FakeSentinel("sentinel.gateway")),
        )


def test_sqlite_lease_is_stable_then_rotates_after_expiry(tmp_path: Path) -> None:
    path = tmp_path / "sentinel-leases.db"
    repository = IncidentRepository(path)
    repository.initialize()
    repository.start_run(
        incident_id="incident-lease",
        alert_fingerprint=None,
        target_operation="gateway.checkout",
        occurred_at=_clock(),
    )
    candidates = ("sentinel.gateway", "sentinel.checkout")

    first = repository.elect_sentinel_leader(
        incident_id="incident-lease",
        candidates=candidates,
        occurred_at=_clock(),
        lease_ttl=timedelta(seconds=30),
    )
    retained = repository.elect_sentinel_leader(
        incident_id="incident-lease",
        candidates=candidates,
        occurred_at=_clock() + timedelta(seconds=10),
        lease_ttl=timedelta(seconds=30),
    )
    reopened = IncidentRepository(path)
    expired = reopened.elect_sentinel_leader(
        incident_id="incident-lease",
        candidates=candidates,
        occurred_at=_clock() + timedelta(seconds=31),
        lease_ttl=timedelta(seconds=30),
    )

    assert first == retained
    assert first.leader_id == "sentinel.gateway"
    assert first.generation == 1
    assert expired.leader_id == "sentinel.checkout"
    assert expired.generation == 2
    assert repository.progress("incident-lease")[0].state is IncidentState.RECEIVED


@pytest.mark.anyio
async def test_sqlite_backed_mesh_persists_leader_failover(tmp_path: Path) -> None:
    repository = IncidentRepository(tmp_path / "sentinel-failover.db")
    repository.initialize()
    repository.start_run(
        incident_id="incident-persisted-failover",
        alert_fingerprint=None,
        target_operation="gateway.checkout",
        occurred_at=_clock(),
    )
    coordinator = SentinelMeshCoordinator(repository, clock=_clock)
    candidates = (
        FakeSentinel("sentinel.gateway", fails=True),
        FakeSentinel("sentinel.checkout"),
        FakeSentinel("sentinel.inventory"),
    )

    result = await coordinator.run(_context("incident-persisted-failover"), candidates)
    retained = IncidentRepository(tmp_path / "sentinel-failover.db").elect_sentinel_leader(
        incident_id="incident-persisted-failover",
        candidates=tuple(item.sentinel_id for item in candidates),
        occurred_at=_clock() + timedelta(seconds=1),
        lease_ttl=timedelta(seconds=30),
    )

    assert result.run.leader_id == "sentinel.checkout"
    assert retained.leader_id == "sentinel.checkout"
    assert retained.generation == 2
