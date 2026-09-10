"""Workflow event contracts.

The same event model will later back logs, SQLite persistence, and frontend live
updates. Phase 0 defines the contract only; there is no event bus.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    """Categories of workflow event."""

    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"

    AGENT_STARTED = "agent.started"
    AGENT_COMPLETED = "agent.completed"
    AGENT_FAILED = "agent.failed"

    LOOP_ITERATION_STARTED = "loop.iteration.started"

    JUDGE_APPROVED = "judge.approved"
    JUDGE_REJECTED = "judge.rejected"

    WORKFLOW_STATUS_CHANGED = "workflow.status.changed"


class WorkflowEvent(BaseModel):
    """A single observable event emitted during a run."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_id: str
    event_type: EventType
    agent_name: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utcnow)
