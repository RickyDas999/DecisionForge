"""Local SQLite persistence for DecisionForge runs and execution events.

Uses the standard-library ``sqlite3`` with parameterized SQL only — no ORM, no
string-interpolated queries. Deterministic file I/O; zero LLM calls, zero agent
calls, zero retries.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models.persistence import EventType, ExecutionEvent, RunRecord, RunStatus
from app.models.routing import AgentRoute

DEFAULT_DB_PATH = Path("data") / "decisionforge.db"
DB_PATH_ENV_VAR = "DECISIONFORGE_DB_PATH"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id             TEXT PRIMARY KEY,
    user_request       TEXT NOT NULL,
    provided_context   TEXT,
    route              TEXT,
    routing_reasoning  TEXT,
    selected_specialist TEXT,
    search_used        INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL,
    result_json        TEXT,
    error              TEXT,
    created_at         TEXT NOT NULL,
    completed_at       TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    message       TEXT,
    metadata_json TEXT NOT NULL,
    timestamp     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_events_run_ts ON events (run_id, timestamp);
"""


def resolve_db_path(explicit: str | Path | None = None) -> Path:
    """Pick the DB path: explicit arg, then ``DECISIONFORGE_DB_PATH``, then default."""
    if explicit is not None:
        return Path(explicit)
    from_env = os.environ.get(DB_PATH_ENV_VAR)
    return Path(from_env) if from_env else DEFAULT_DB_PATH


class SQLiteRunRepository:
    """Create/read runs and append/read their events. Schema is created on init."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        if self.db_path not in (":memory:", ""):
            parent = Path(self.db_path).parent
            if str(parent) not in ("", "."):
                parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # -- connection ------------------------------------------------------- #
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    # -- runs: writes -------------------------------------------------- #
    def create_run(self, record: RunRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, user_request, provided_context, route,
                    routing_reasoning, selected_specialist, search_used, status,
                    result_json, error, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.user_request,
                    record.provided_context,
                    record.route.value if record.route else None,
                    record.routing_reasoning,
                    record.selected_specialist,
                    1 if record.search_used else 0,
                    record.status.value,
                    record.result_json,
                    record.error,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat() if record.completed_at else None,
                ),
            )

    def set_route(
        self,
        run_id: str,
        *,
        route: AgentRoute,
        routing_reasoning: str,
        selected_specialist: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                   SET route = ?, routing_reasoning = ?, selected_specialist = ?,
                       status = ?
                 WHERE run_id = ?
                """,
                (
                    route.value,
                    routing_reasoning,
                    selected_specialist,
                    RunStatus.ROUTED.value,
                    run_id,
                ),
            )

    def set_search_used(self, run_id: str, used: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET search_used = ? WHERE run_id = ?",
                (1 if used else 0, run_id),
            )

    def mark_completed(
        self, run_id: str, *, result_json: str, completed_at: datetime | None = None
    ) -> None:
        stamp = (completed_at or _now()).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                   SET status = ?, result_json = ?, completed_at = ?
                 WHERE run_id = ?
                """,
                (RunStatus.COMPLETED.value, result_json, stamp, run_id),
            )

    def mark_failed(
        self, run_id: str, *, error: str, completed_at: datetime | None = None
    ) -> None:
        stamp = (completed_at or _now()).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status = ?, error = ?, completed_at = ? WHERE run_id = ?",
                (RunStatus.FAILED.value, error, stamp, run_id),
            )

    # -- runs: reads --------------------------------------------------- #
    def get_run(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return _row_to_run(row) if row else None

    def list_recent_runs(self, limit: int = 20) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC, run_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_run(row) for row in rows]

    # -- events ------------------------------------------------------ #
    def append_event(self, event: ExecutionEvent) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, run_id, event_type, message, metadata_json, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.run_id,
                    event.event_type.value,
                    event.message,
                    json.dumps(event.metadata, sort_keys=True),
                    event.timestamp.isoformat(),
                ),
            )

    def get_events(self, run_id: str) -> list[ExecutionEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM events
                 WHERE run_id = ?
                 ORDER BY timestamp ASC, rowid ASC
                """,
                (run_id,),
            ).fetchall()
        return [_row_to_event(row) for row in rows]


# --------------------------------------------------------------------------- #
# Row -> model helpers
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row_to_run(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        run_id=row["run_id"],
        user_request=row["user_request"],
        provided_context=row["provided_context"],
        route=AgentRoute(row["route"]) if row["route"] else None,
        routing_reasoning=row["routing_reasoning"],
        selected_specialist=row["selected_specialist"],
        search_used=bool(row["search_used"]),
        status=RunStatus(row["status"]),
        result_json=row["result_json"],
        error=row["error"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=(
            datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
        ),
    )


def _row_to_event(row: sqlite3.Row) -> ExecutionEvent:
    return ExecutionEvent(
        event_id=row["event_id"],
        run_id=row["run_id"],
        event_type=EventType(row["event_type"]),
        message=row["message"],
        metadata=json.loads(row["metadata_json"]),
        timestamp=datetime.fromisoformat(row["timestamp"]),
    )
