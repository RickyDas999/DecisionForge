"""A minimal synchronous event recorder backed by a run repository.

No queue, no bus, no async. ``emit`` builds an :class:`ExecutionEvent`, appends
it to the repository, and keeps a copy in :attr:`events` so the caller can return
the full trace in one HTTP response (important for stateless deployments where
the repository stores nothing).
"""

from __future__ import annotations

from typing import Any

from app.models.persistence import EventType, ExecutionEvent
from app.persistence.base import RunRepository


class ExecutionRecorder:
    """Records events for a single ``run_id``."""

    def __init__(self, repository: RunRepository, run_id: str) -> None:
        self._repository = repository
        self._run_id = run_id
        #: Every event emitted this run, in order.
        self.events: list[ExecutionEvent] = []

    def emit(
        self,
        event_type: EventType,
        message: str | None = None,
        /,
        **metadata: Any,
    ) -> ExecutionEvent:
        event = ExecutionEvent(
            run_id=self._run_id,
            event_type=event_type,
            message=message,
            metadata=dict(metadata),
        )
        self._repository.append_event(event)
        self.events.append(event)
        return event
