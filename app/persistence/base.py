"""The run-repository interface.

Two implementations: :class:`app.persistence.sqlite.SQLiteRunRepository` (durable
local history) and :class:`app.persistence.null.NullRunRepository` (stateless —
for Vercel / demo deployments where there is no writable durable store).
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from app.models.persistence import ExecutionEvent, RunRecord
from app.models.routing import AgentRoute


@runtime_checkable
class RunRepository(Protocol):
    """Write a run + its events; read them back. Deterministic; no LLM, no agents."""

    def create_run(self, record: RunRecord) -> None: ...

    def set_route(
        self,
        run_id: str,
        *,
        route: AgentRoute,
        routing_reasoning: str,
        selected_specialist: str,
    ) -> None: ...

    def set_search_used(self, run_id: str, used: bool) -> None: ...

    def mark_completed(
        self, run_id: str, *, result_json: str, completed_at: datetime | None = None
    ) -> None: ...

    def mark_failed(
        self, run_id: str, *, error: str, completed_at: datetime | None = None
    ) -> None: ...

    def get_run(self, run_id: str) -> RunRecord | None: ...

    def list_recent_runs(self, limit: int = 20) -> list[RunRecord]: ...

    def append_event(self, event: ExecutionEvent) -> None: ...

    def get_events(self, run_id: str) -> list[ExecutionEvent]: ...
