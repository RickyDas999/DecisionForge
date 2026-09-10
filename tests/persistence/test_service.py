"""Tests for :class:`DecisionForgeService` (dispatch + persistence).

Every model call is mocked; every search is mocked; DB is a temp file. Proves
persistence adds no model calls and the 2-call ceiling still holds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest
from app.models.persistence import EventType, RunStatus
from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.orchestration.exceptions import MissingBriefContextError
from app.persistence.sqlite import SQLiteRunRepository
from app.providers.exceptions import MockResponseExhaustedError
from app.providers.mock import MockModelProvider
from app.service import DecisionForgeService
from app.tools.exceptions import SearchProviderError
from app.tools.search import MockSearchProvider, SearchProvider


def _routing(route: AgentRoute) -> RoutingDecision:
    return RoutingDecision(route=route, reasoning="because")


def _research() -> ResearchResponse:
    return ResearchResponse(topic="t", summary="s")


def _comparison() -> ComparisonResponse:
    return ComparisonResponse(
        question="q",
        options=[ComparisonOption(name="A")],
        recommendation="A",
        rationale="r",
        confidence=0.5,
    )


def _brief() -> BriefResponse:
    return BriefResponse(title="T", executive_summary="ES", key_points=["k"])


def _search_response() -> SearchResponse:
    return SearchResponse(
        query="the request",
        results=[
            SearchResult(
                title="Evidence",
                url="https://evidence.example/1",
                snippet="snippet",
                source="evidence.example",
            )
        ],
    )


class _FailingSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        raise SearchProviderError("search backend down")


@dataclass
class Rig:
    service: DecisionForgeService
    repo: SQLiteRunRepository
    orch: MockModelProvider
    research: MockModelProvider
    comparison: MockModelProvider
    brief: MockModelProvider
    search: SearchProvider | None


def make_rig(
    tmp_path,
    routing: RoutingDecision,
    *,
    research: list | None = None,
    comparison: list | None = None,
    brief: list | None = None,
    search: SearchProvider | None = None,
) -> Rig:
    orch = MockModelProvider(structured_responses=[routing])
    res = MockModelProvider(structured_responses=research or [])
    cmp = MockModelProvider(structured_responses=comparison or [])
    brf = MockModelProvider(structured_responses=brief or [])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(res),
        comparison_agent=ComparisonAgent(cmp),
        brief_agent=BriefAgent(brf),
        search_provider=search,
    )
    repo = SQLiteRunRepository(tmp_path / "runs.db")
    return Rig(DecisionForgeService(dispatcher, repo), repo, orch, res, cmp, brf, search)


def _model_calls(rig: Rig) -> int:
    return (
        len(rig.orch.calls)
        + len(rig.research.calls)
        + len(rig.comparison.calls)
        + len(rig.brief.calls)
    )


def _event_types(rig: Rig, run_id: str) -> list[EventType]:
    return [e.event_type for e in rig.repo.get_events(run_id)]


# --------------------------------------------------------------------------- #
# Successful research request (no search)
# --------------------------------------------------------------------------- #
def test_successful_research_run_is_persisted(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    record = asyncio.run(
        rig.service.run(DispatchRequest(user_request="Research vector DBs."))
    ).record

    assert record.status is RunStatus.COMPLETED
    assert record.route is AgentRoute.RESEARCH
    assert record.selected_specialist == "ResearchAgent"
    assert record.search_used is False
    assert record.result_json and '"route":"research"' in record.result_json
    assert record.completed_at is not None
    assert _model_calls(rig) == 2  # persistence added none

    assert _event_types(rig, record.run_id) == [
        EventType.RUN_STARTED,
        EventType.ROUTE_SELECTED,
        EventType.SPECIALIST_STARTED,
        EventType.SPECIALIST_COMPLETED,
        EventType.RUN_COMPLETED,
    ]


# --------------------------------------------------------------------------- #
# Research / comparison with search
# --------------------------------------------------------------------------- #
def test_research_with_search_records_search_events(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.RESEARCH),
        research=[_research()],
        search=MockSearchProvider(responses=[_search_response()]),
    )
    record = asyncio.run(
        rig.service.run(DispatchRequest(user_request="Research vector DBs."))
    ).record

    assert record.search_used is True
    assert _model_calls(rig) == 2
    assert _event_types(rig, record.run_id) == [
        EventType.RUN_STARTED,
        EventType.ROUTE_SELECTED,
        EventType.SEARCH_STARTED,
        EventType.SEARCH_COMPLETED,
        EventType.SPECIALIST_STARTED,
        EventType.SPECIALIST_COMPLETED,
        EventType.RUN_COMPLETED,
    ]
    search_completed = next(
        e for e in rig.repo.get_events(record.run_id)
        if e.event_type is EventType.SEARCH_COMPLETED
    )
    assert search_completed.metadata["result_count"] == 1


def test_comparison_with_search_records_search_events(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.COMPARISON),
        comparison=[_comparison()],
        search=MockSearchProvider(responses=[_search_response()]),
    )
    record = asyncio.run(
        rig.service.run(DispatchRequest(user_request="Compare A and B."))
    ).record
    assert record.search_used is True
    assert record.selected_specialist == "ComparisonAgent"
    assert EventType.SEARCH_STARTED in _event_types(rig, record.run_id)
    assert _model_calls(rig) == 2


# --------------------------------------------------------------------------- #
# Brief never searches
# --------------------------------------------------------------------------- #
def test_brief_run_has_no_search_events(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.BRIEF),
        brief=[_brief()],
        search=MockSearchProvider(responses=[_search_response()]),
    )
    record = asyncio.run(
        rig.service.run(
            DispatchRequest(
                user_request="Make a brief.", provided_context="source material"
            )
        )
    ).record

    assert record.status is RunStatus.COMPLETED
    assert record.search_used is False
    events = _event_types(rig, record.run_id)
    assert EventType.SEARCH_STARTED not in events
    assert EventType.SEARCH_COMPLETED not in events
    assert isinstance(rig.search, MockSearchProvider)
    assert rig.search.calls == []  # search provider never called
    assert _model_calls(rig) == 2


# --------------------------------------------------------------------------- #
# Failures are persisted; exception still propagates; no retry
# --------------------------------------------------------------------------- #
def test_specialist_failure_is_persisted_and_reraised(tmp_path) -> None:
    # research provider returns an invalid payload -> StructuredOutputError
    rig = make_rig(
        tmp_path, _routing(AgentRoute.RESEARCH), research=[{"bad": True}]
    )
    with pytest.raises(Exception) as excinfo:
        asyncio.run(rig.service.run(DispatchRequest(user_request="Research X.")))

    assert "StructuredOutputError" in type(excinfo.value).__name__

    recent = rig.repo.list_recent_runs()
    assert len(recent) == 1
    record = recent[0]
    assert record.status is RunStatus.FAILED
    assert record.error and "StructuredOutputError" in record.error
    assert record.result_json is None
    assert EventType.RUN_FAILED in _event_types(rig, record.run_id)
    assert EventType.RUN_COMPLETED not in _event_types(rig, record.run_id)
    # one orchestrator + one specialist attempt, no retry
    assert len(rig.orch.calls) == 1
    assert len(rig.research.calls) == 1


def test_orchestrator_failure_is_persisted_with_no_specialist_call(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    rig.orch.structured_responses.clear()  # force exhaustion during routing
    with pytest.raises(MockResponseExhaustedError):
        asyncio.run(rig.service.run(DispatchRequest(user_request="X")))

    record = rig.repo.list_recent_runs()[0]
    assert record.status is RunStatus.FAILED
    assert record.route is None
    assert _event_types(rig, record.run_id) == [
        EventType.RUN_STARTED,
        EventType.RUN_FAILED,
    ]
    assert len(rig.research.calls) == 0


def test_search_failure_is_persisted_and_reraised(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.RESEARCH),
        research=[_research()],
        search=_FailingSearch(),
    )
    with pytest.raises(SearchProviderError):
        asyncio.run(rig.service.run(DispatchRequest(user_request="Research X.")))

    record = rig.repo.list_recent_runs()[0]
    assert record.status is RunStatus.FAILED
    assert record.route is AgentRoute.RESEARCH  # routing happened before search
    assert record.search_used is False
    events = _event_types(rig, record.run_id)
    assert events == [
        EventType.RUN_STARTED,
        EventType.ROUTE_SELECTED,
        EventType.SEARCH_STARTED,
        EventType.RUN_FAILED,
    ]
    assert len(rig.orch.calls) == 1
    assert len(rig.research.calls) == 0  # no specialist call, no fallback


def test_missing_brief_context_is_persisted_as_failure(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.BRIEF), brief=[_brief()])
    with pytest.raises(MissingBriefContextError):
        asyncio.run(rig.service.run(DispatchRequest(user_request="Make a brief.")))

    record = rig.repo.list_recent_runs()[0]
    assert record.status is RunStatus.FAILED
    assert record.route is AgentRoute.BRIEF
    assert EventType.RUN_FAILED in _event_types(rig, record.run_id)
    assert len(rig.brief.calls) == 0


# --------------------------------------------------------------------------- #
# Independence
# --------------------------------------------------------------------------- #
def test_two_runs_through_one_service_are_independent(tmp_path) -> None:
    orch = MockModelProvider(
        structured_responses=[
            _routing(AgentRoute.RESEARCH),
            _routing(AgentRoute.COMPARISON),
        ]
    )
    res = MockModelProvider(structured_responses=[_research()])
    cmp = MockModelProvider(structured_responses=[_comparison()])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(res),
        comparison_agent=ComparisonAgent(cmp),
        brief_agent=BriefAgent(MockModelProvider()),
    )
    repo = SQLiteRunRepository(tmp_path / "runs.db")
    service = DecisionForgeService(dispatcher, repo)

    r1 = asyncio.run(service.run(DispatchRequest(user_request="Research X."))).record
    r2 = asyncio.run(service.run(DispatchRequest(user_request="Compare A and B."))).record

    assert r1.run_id != r2.run_id
    assert r1.route is AgentRoute.RESEARCH
    assert r2.route is AgentRoute.COMPARISON
    assert {r.run_id for r in repo.list_recent_runs()} == {r1.run_id, r2.run_id}
    assert len(repo.get_events(r1.run_id)) == 5
    assert len(repo.get_events(r2.run_id)) == 5
