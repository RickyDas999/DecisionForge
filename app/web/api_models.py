"""Typed request/response models for the web API.

These shape the JSON the browser sees. Raw DB rows and SDK objects are never
exposed; the stored ``result_json`` is parsed back into a plain object.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.persistence import EventType, ExecutionEvent, RunRecord, RunStatus
from app.models.routing import AgentRoute
from app.skills.mapping import ROUTE_SKILLS

_PREVIEW_CHARS = 120

#: The hard architectural ceiling (1 orchestrator + 1 specialist).
MAX_LLM_CALLS = 2


def _llm_calls_from_events(events: list[ExecutionEvent]) -> int:
    """Deterministically count the model calls that completed this run.

    ``route.selected`` => the orchestrator call returned (1).
    ``specialist.completed`` => the specialist call returned (2).
    """
    seen = {e.event_type for e in events}
    calls = 0
    if EventType.ROUTE_SELECTED in seen:
        calls += 1
    if EventType.SPECIALIST_COMPLETED in seen:
        calls += 1
    return calls


class RunView(BaseModel):
    """One run, with its structured result parsed from storage."""

    run_id: str
    user_request: str
    provided_context: str | None
    status: RunStatus
    route: AgentRoute | None
    routing_reasoning: str | None
    selected_specialist: str | None
    search_used: bool
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def from_record(cls, record: RunRecord) -> "RunView":
        # ``result_json`` stores the whole DispatchResult
        # ({route, routing_reasoning, result}); expose just the specialist payload
        # here (route / reasoning are already dedicated fields).
        result: dict[str, Any] | None = None
        if record.result_json:
            try:
                parsed = json.loads(record.result_json)
            except json.JSONDecodeError:  # pragma: no cover - stored by us as JSON
                parsed = None
            if isinstance(parsed, dict):
                result = parsed.get("result", parsed)
        return cls(
            run_id=record.run_id,
            user_request=record.user_request,
            provided_context=record.provided_context,
            status=record.status,
            route=record.route,
            routing_reasoning=record.routing_reasoning,
            selected_specialist=record.selected_specialist,
            search_used=record.search_used,
            result=result,
            error=record.error,
            created_at=record.created_at,
            completed_at=record.completed_at,
        )


class EventView(BaseModel):
    """One execution event."""

    event_type: EventType
    message: str | None
    metadata: dict[str, Any]
    timestamp: datetime

    @classmethod
    def from_event(cls, event: ExecutionEvent) -> "EventView":
        return cls(
            event_type=event.event_type,
            message=event.message,
            metadata=event.metadata,
            timestamp=event.timestamp,
        )


class RunSummary(BaseModel):
    """A compact row for the 'recent runs' list."""

    run_id: str
    request_preview: str
    route: AgentRoute | None
    status: RunStatus
    search_used: bool
    created_at: datetime

    @classmethod
    def from_record(cls, record: RunRecord) -> "RunSummary":
        preview = record.user_request.strip().replace("\n", " ")
        if len(preview) > _PREVIEW_CHARS:
            preview = preview[: _PREVIEW_CHARS - 1] + "…"
        return cls(
            run_id=record.run_id,
            request_preview=preview,
            route=record.route,
            status=record.status,
            search_used=record.search_used,
            created_at=record.created_at,
        )


class RunResult(RunView):
    """A run's fields **plus** its event trace and deterministic demo metadata.

    Returned by ``POST /api/runs`` and ``GET /api/runs/{id}`` so the browser can
    render a completed run — result, trace, execution path — from a single
    response, with no follow-up request. This matters for stateless deployments.

    ``selected_skill``, ``llm_calls`` and ``llm_calls_max`` are derived
    deterministically (route -> skill mapping; event trace) — no model call.
    """

    selected_skill: str | None
    llm_calls: int
    llm_calls_max: int = MAX_LLM_CALLS

    events: list[EventView] = Field(default_factory=list)

    @classmethod
    def from_run(
        cls, record: RunRecord, events: list[ExecutionEvent]
    ) -> "RunResult":
        base = RunView.from_record(record)
        skill = ROUTE_SKILLS.get(record.route) if record.route else None
        return cls(
            **base.model_dump(),
            selected_skill=skill,
            llm_calls=_llm_calls_from_events(events),
            events=[EventView.from_event(e) for e in events],
        )


class RecentRuns(BaseModel):
    runs: list[RunSummary]


class ErrorResponse(BaseModel):
    """A safe error body (no stack traces, no secrets)."""

    detail: str
    error_type: str
    run_id: str | None = None
