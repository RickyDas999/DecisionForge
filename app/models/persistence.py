"""Current-architecture persistence models.

These describe a single DecisionForge run and its chronological events. They are
**not** the legacy Phase 0 ``RunState`` / ``WorkflowEvent`` (multi-stage
pipeline) — those remain in ``app/models/state.py`` and ``app/models/events.py``
for old tests only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.models.routing import AgentRoute


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    """Lifecycle status of one DecisionForge run (single-hop architecture)."""

    STARTED = "started"
    ROUTED = "routed"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    """Chronological execution events for one run.

    ``search.*`` events are emitted only when search actually runs.
    """

    RUN_STARTED = "run.started"
    ROUTE_SELECTED = "route.selected"
    SEARCH_STARTED = "search.started"
    SEARCH_COMPLETED = "search.completed"
    SPECIALIST_STARTED = "specialist.started"
    SPECIALIST_COMPLETED = "specialist.completed"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"


class RunRecord(BaseModel):
    """The persisted state of one run."""

    run_id: str
    user_request: str
    provided_context: str | None = None
    route: AgentRoute | None = None
    routing_reasoning: str | None = None
    selected_specialist: str | None = None
    search_used: bool = False
    status: RunStatus = RunStatus.STARTED
    #: Serialized ``DispatchResult`` JSON (present only when status == completed).
    result_json: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None


class ExecutionEvent(BaseModel):
    """One chronological event within a run."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    event_type: EventType
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)
