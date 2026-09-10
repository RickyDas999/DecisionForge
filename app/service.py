"""Application service: run a request through the dispatcher, persist everything.

``DecisionForgeService`` owns the run lifecycle and persistence. The dispatcher
stays exactly what it was — routing + optional search + one specialist — and is
called **once** per request. Persistence adds zero model calls, zero agent calls,
and zero retries. On any failure the run is marked ``failed``, the error text is
stored, a ``run.failed`` event is recorded, and the original exception is
re-raised unchanged.
"""

from __future__ import annotations

import uuid

from app.agents.base import AgentRuntimeContext
from app.events.recorder import ExecutionRecorder
from app.models.dispatch import DispatchRequest
from app.models.persistence import EventType, RunRecord, RunStatus
from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.orchestration.observer import DispatchObserver
from app.persistence.sqlite import SQLiteRunRepository

_SPECIALIST_CLASS_NAME = {
    AgentRoute.RESEARCH: "ResearchAgent",
    AgentRoute.COMPARISON: "ComparisonAgent",
    AgentRoute.BRIEF: "BriefAgent",
}


def _safe_error_text(exc: BaseException) -> str:
    """A short, secret-free description of a failure."""
    text = str(exc).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


class _PersistenceObserver(DispatchObserver):
    """Writes route + search-usage to the run row and records events."""

    def __init__(self, repository: SQLiteRunRepository, run_id: str) -> None:
        self._repo = repository
        self._run_id = run_id
        self._recorder = ExecutionRecorder(repository, run_id)

    def _emit(self, event_type: EventType, message: str | None = None, **metadata) -> None:
        self._recorder.emit(event_type, message, **metadata)

    def on_routing_completed(self, decision: RoutingDecision) -> None:
        specialist = _SPECIALIST_CLASS_NAME[decision.route]
        self._repo.set_route(
            self._run_id,
            route=decision.route,
            routing_reasoning=decision.reasoning,
            selected_specialist=specialist,
        )
        self._emit(
            EventType.ROUTE_SELECTED,
            decision.route.value,
            route=decision.route.value,
            specialist=specialist,
        )

    def on_search_started(self, query: str) -> None:
        self._emit(EventType.SEARCH_STARTED)

    def on_search_completed(self, response: SearchResponse) -> None:
        self._repo.set_search_used(self._run_id, True)
        self._emit(
            EventType.SEARCH_COMPLETED, result_count=len(response.results)
        )

    def on_specialist_started(self, route: AgentRoute) -> None:
        self._emit(EventType.SPECIALIST_STARTED, route=route.value)

    def on_specialist_completed(self, route: AgentRoute) -> None:
        self._emit(EventType.SPECIALIST_COMPLETED, route=route.value)


class DecisionForgeService:
    """Runs one request end-to-end and persists the run and its events."""

    def __init__(
        self,
        dispatcher: DecisionForgeDispatcher,
        repository: SQLiteRunRepository,
    ) -> None:
        self._dispatcher = dispatcher
        self._repository = repository

    async def run(
        self,
        request: DispatchRequest,
        context: AgentRuntimeContext | None = None,
        *,
        run_id: str | None = None,
    ) -> RunRecord:
        run_id = run_id or str(uuid.uuid4())
        ctx = context or AgentRuntimeContext(run_id=run_id)

        self._repository.create_run(
            RunRecord(
                run_id=run_id,
                user_request=request.user_request,
                provided_context=request.provided_context,
                status=RunStatus.STARTED,
            )
        )
        recorder = ExecutionRecorder(self._repository, run_id)
        recorder.emit(EventType.RUN_STARTED)

        observer = _PersistenceObserver(self._repository, run_id)

        try:
            result = await self._dispatcher.dispatch(request, ctx, observer=observer)
        except Exception as exc:
            self._repository.mark_failed(run_id, error=_safe_error_text(exc))
            recorder.emit(EventType.RUN_FAILED, type(exc).__name__)
            raise

        self._repository.mark_completed(run_id, result_json=result.model_dump_json())
        recorder.emit(EventType.RUN_COMPLETED, result.route.value, route=result.route.value)
        return self._repository.get_run(run_id)  # type: ignore[return-value]
