"""A minimal synchronous event recorder backed by a SQLite repository.

No queue, no bus, no async. ``emit`` builds an :class:`ExecutionEvent` and
appends it immediately. Its only job is to make later UI / trace work easy.
"""

from __future__ import annotations

from typing import Any

from app.models.persistence import EventType, ExecutionEvent
from app.persistence.sqlite import SQLiteRunRepository


class ExecutionRecorder:
    """Records events for a single ``run_id``."""

    def __init__(self, repository: SQLiteRunRepository, run_id: str) -> None:
        self._repository = repository
        self._run_id = run_id

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
        return event
