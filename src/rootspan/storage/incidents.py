"""Small SQLite repository for immutable compiled incident briefs."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from rootspan.domain import (
    IncidentBrief,
    IncidentProgress,
    IncidentState,
    SentinelLeaderLease,
)


class IncidentRepository:
    """Persist complete briefs without introducing an external database."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_briefs (
                    incident_id TEXT PRIMARY KEY,
                    completed_at TEXT NOT NULL,
                    state TEXT NOT NULL,
                    brief_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    alert_fingerprint TEXT UNIQUE,
                    state TEXT NOT NULL,
                    target_operation TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stage_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_stage_runs_incident
                ON stage_runs (incident_id, id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sentinel_leases (
                    incident_id TEXT PRIMARY KEY,
                    leader_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (incident_id) REFERENCES incidents(incident_id)
                )
                """
            )

    def save(self, brief: IncidentBrief) -> None:
        payload = brief.model_dump_json(exclude_computed_fields=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO incident_briefs (incident_id, completed_at, state, brief_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    completed_at = excluded.completed_at,
                    state = excluded.state,
                    brief_json = excluded.brief_json
                """,
                (brief.incident_id, brief.completed_at.isoformat(), brief.state.value, payload),
            )

    def get(self, incident_id: str) -> IncidentBrief | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT brief_json FROM incident_briefs WHERE incident_id = ?",
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse(str(row[0]))

    def get_by_fingerprint(self, fingerprint: str) -> IncidentBrief | None:
        """Return a completed deduplicated incident for an alert fingerprint."""

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT brief.brief_json
                FROM incidents AS incident
                JOIN incident_briefs AS brief ON brief.incident_id = incident.incident_id
                WHERE incident.alert_fingerprint = ?
                """,
                (fingerprint,),
            ).fetchone()
        if row is None:
            return None
        return self._parse(str(row[0]))

    def start_run(
        self,
        *,
        incident_id: str,
        alert_fingerprint: str | None,
        target_operation: str,
        occurred_at: datetime,
    ) -> None:
        """Persist RECEIVED before live collection starts."""

        timestamp = occurred_at.isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, alert_fingerprint, state, target_operation,
                    started_at, updated_at, error
                ) VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    incident_id,
                    alert_fingerprint,
                    IncidentState.RECEIVED.value,
                    target_operation,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO stage_runs (incident_id, state, occurred_at, detail)
                VALUES (?, ?, ?, ?)
                """,
                (
                    incident_id,
                    IncidentState.RECEIVED.value,
                    timestamp,
                    "Incident accepted and persisted before evidence collection.",
                ),
            )

    def transition(
        self,
        incident_id: str,
        state: IncidentState,
        *,
        occurred_at: datetime,
        detail: str,
        error: str | None = None,
    ) -> None:
        """Atomically persist a stage transition before the next stage starts."""

        timestamp = occurred_at.isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE incidents
                SET state = ?, updated_at = ?, error = ?
                WHERE incident_id = ?
                """,
                (state.value, timestamp, error, incident_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"unknown incident run: {incident_id}")
            connection.execute(
                """
                INSERT INTO stage_runs (incident_id, state, occurred_at, detail)
                VALUES (?, ?, ?, ?)
                """,
                (incident_id, state.value, timestamp, detail),
            )

    def progress(self, incident_id: str) -> tuple[IncidentProgress, ...]:
        """List persisted transitions in exact execution order."""

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT state, occurred_at, detail
                FROM stage_runs
                WHERE incident_id = ?
                ORDER BY id ASC
                """,
                (incident_id,),
            ).fetchall()
        return tuple(
            IncidentProgress(
                incident_id=incident_id,
                state=IncidentState(str(row[0])),
                occurred_at=datetime.fromisoformat(str(row[1])),
                detail=str(row[2]),
            )
            for row in rows
        )

    def elect_sentinel_leader(
        self,
        *,
        incident_id: str,
        candidates: tuple[str, ...],
        occurred_at: datetime,
        lease_ttl: timedelta,
        force_failover: bool = False,
    ) -> SentinelLeaderLease:
        """Elect or retain one incident leader using an atomic SQLite lease."""

        if not candidates or any(not item for item in candidates):
            raise ValueError("sentinel leader candidates must be named")
        if len(candidates) != len(set(candidates)):
            raise ValueError("sentinel leader candidates must be unique")
        if occurred_at.tzinfo is None:
            raise ValueError("sentinel leader election time must be timezone-aware")
        if lease_ttl <= timedelta(0):
            raise ValueError("sentinel leader lease TTL must be positive")
        first_candidate = next(iter(candidates))

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT leader_id, generation, expires_at
                FROM sentinel_leases
                WHERE incident_id = ?
                """,
                (incident_id,),
            ).fetchone()
            current_leader = str(row[0]) if row is not None else None
            current_generation = int(row[1]) if row is not None else 0
            current_expiry = datetime.fromisoformat(str(row[2])) if row is not None else None
            if (
                current_leader in candidates
                and current_expiry is not None
                and current_expiry > occurred_at
                and not force_failover
            ):
                return SentinelLeaderLease(
                    incident_id=incident_id,
                    leader_id=current_leader,
                    generation=current_generation,
                    expires_at=current_expiry,
                )

            if current_leader in candidates and len(candidates) > 1:
                next_index = (candidates.index(current_leader) + 1) % len(candidates)
                leader_id = candidates[next_index]
            else:
                leader_id = first_candidate
            generation = current_generation + 1
            expires_at = occurred_at + lease_ttl
            connection.execute(
                """
                INSERT INTO sentinel_leases (incident_id, leader_id, generation, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    leader_id = excluded.leader_id,
                    generation = excluded.generation,
                    expires_at = excluded.expires_at
                """,
                (incident_id, leader_id, generation, expires_at.isoformat()),
            )
            return SentinelLeaderLease(
                incident_id=incident_id,
                leader_id=leader_id,
                generation=generation,
                expires_at=expires_at,
            )

    def list(self, *, limit: int = 20) -> tuple[IncidentBrief, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT brief_json
                FROM incident_briefs
                ORDER BY completed_at DESC, incident_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return tuple(self._parse(str(row[0])) for row in rows)

    @staticmethod
    def _parse(payload: str) -> IncidentBrief:
        # `extra="ignore"` reads records written before computed API fields were excluded.
        return IncidentBrief.model_validate_json(payload, extra="ignore")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection
