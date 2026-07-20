"""Small SQLite repository for immutable compiled incident briefs."""

import sqlite3
from pathlib import Path

from rootspan.domain import IncidentBrief


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
