"""A stateless run repository: writes are no-ops, reads return nothing.

Used for deployments (Vercel) where there is no writable durable store. A request
still runs end-to-end and returns its full result + event trace — that data is
assembled in-memory by :class:`app.service.DecisionForgeService` and handed
straight back in the HTTP response, never persisted.

This is deliberately **not** an in-memory history: it keeps no runs between
requests, so ``list_recent_runs`` is always empty and ``get_run`` always misses.
"""

from __future__ import annotations

from datetime import datetime

from app.models.persistence import ExecutionEvent, RunRecord
from app.models.routing import AgentRoute


class NullRunRepository:
    """Implements the ``RunRepository`` protocol as no-ops / empty reads."""

    def create_run(self, record: RunRecord) -> None:
        return None

    def set_route(
        self,
        run_id: str,
        *,
        route: AgentRoute,
        routing_reasoning: str,
        selected_specialist: str,
    ) -> None:
        return None

    def set_search_used(self, run_id: str, used: bool) -> None:
        return None

    def mark_completed(
        self, run_id: str, *, result_json: str, completed_at: datetime | None = None
    ) -> None:
        return None

    def mark_failed(
        self, run_id: str, *, error: str, completed_at: datetime | None = None
    ) -> None:
        return None

    def get_run(self, run_id: str) -> RunRecord | None:
        return None

    def list_recent_runs(self, limit: int = 20) -> list[RunRecord]:
        return []

    def append_event(self, event: ExecutionEvent) -> None:
        return None

    def get_events(self, run_id: str) -> list[ExecutionEvent]:
        return []
