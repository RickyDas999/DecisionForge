"""Dispatcher + search-tool integration.

Every model call is mocked (``MockModelProvider``) and every search is mocked
(``MockSearchProvider``). No network, no Anthropic. Proves search adds evidence
without adding model calls, and that the two-call ceiling holds.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest
from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.skills.local import LocalSkillRegistry
from app.skills.mapping import skill_for_route
from app.tools.exceptions import SearchProviderError
from app.tools.search import MockSearchProvider, SearchProvider
from app.providers.mock import MockModelProvider

CTX = AgentRuntimeContext(run_id="dispatch-search-test")

SEARCH_MARK_URL = "https://evidence.example/page-1"
SEARCH_MARK_SNIPPET = "Deterministic search snippet about the topic."


def _routing(route: AgentRoute) -> RoutingDecision:
    return RoutingDecision(route=route, reasoning="because")


def _search_response() -> SearchResponse:
    return SearchResponse(
        query="the user request",
        results=[
            SearchResult(
                title="Evidence One",
                url=SEARCH_MARK_URL,
                snippet=SEARCH_MARK_SNIPPET,
                source="evidence.example",
            )
        ],
    )


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


class _FailingSearchProvider(SearchProvider):
    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        raise SearchProviderError("search backend is down")


@dataclass
class Rig:
    dispatcher: DecisionForgeDispatcher
    orch: MockModelProvider
    research: MockModelProvider
    comparison: MockModelProvider
    brief: MockModelProvider
    search: SearchProvider


def make_rig(
    routing: RoutingDecision,
    *,
    search: SearchProvider,
    research: list | None = None,
    comparison: list | None = None,
    brief: list | None = None,
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
    return Rig(dispatcher, orch, res, cmp, brf, search)


def _model_calls(rig: Rig) -> int:
    return (
        len(rig.orch.calls)
        + len(rig.research.calls)
        + len(rig.comparison.calls)
        + len(rig.brief.calls)
    )


def _dispatch(rig: Rig, request: DispatchRequest) -> object:
    return asyncio.run(rig.dispatcher.dispatch(request, CTX))


# --------------------------------------------------------------------------- #
# Research + search
# --------------------------------------------------------------------------- #
def test_research_route_runs_search_once_and_two_model_calls() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(_routing(AgentRoute.RESEARCH), search=search, research=[_research()])

    _dispatch(rig, DispatchRequest(user_request="Research vector databases."))

    assert len(rig.orch.calls) == 1
    assert len(search.calls) == 1
    assert search.calls[0].query == "Research vector databases."
    assert len(rig.research.calls) == 1
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0
    assert _model_calls(rig) == 2  # search is not a model call


def test_research_agent_receives_search_evidence() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(_routing(AgentRoute.RESEARCH), search=search, research=[_research()])

    _dispatch(rig, DispatchRequest(user_request="Research vector databases."))

    prompt = rig.research.calls[0].user_prompt
    assert SEARCH_MARK_URL in prompt
    assert SEARCH_MARK_SNIPPET in prompt


# --------------------------------------------------------------------------- #
# Comparison + search
# --------------------------------------------------------------------------- #
def test_comparison_route_runs_search_once_and_two_model_calls() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(
        _routing(AgentRoute.COMPARISON), search=search, comparison=[_comparison()]
    )

    _dispatch(rig, DispatchRequest(user_request="Compare A and B."))

    assert len(rig.orch.calls) == 1
    assert len(search.calls) == 1
    assert len(rig.comparison.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.brief.calls) == 0
    assert _model_calls(rig) == 2


def test_comparison_agent_receives_search_evidence() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(
        _routing(AgentRoute.COMPARISON), search=search, comparison=[_comparison()]
    )
    _dispatch(rig, DispatchRequest(user_request="Compare A and B."))
    assert SEARCH_MARK_URL in rig.comparison.calls[0].user_prompt


# --------------------------------------------------------------------------- #
# Brief never searches
# --------------------------------------------------------------------------- #
def test_brief_route_never_calls_search_provider() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(_routing(AgentRoute.BRIEF), search=search, brief=[_brief()])

    _dispatch(
        rig,
        DispatchRequest(
            user_request="Make a brief.", provided_context="user source material"
        ),
    )

    assert len(rig.orch.calls) == 1
    assert len(search.calls) == 0  # important: Brief does not search
    assert len(rig.brief.calls) == 1
    assert _model_calls(rig) == 2


# --------------------------------------------------------------------------- #
# User context is preserved alongside search evidence
# --------------------------------------------------------------------------- #
def test_user_context_and_search_context_both_reach_specialist() -> None:
    search = MockSearchProvider(responses=[_search_response()])
    rig = make_rig(_routing(AgentRoute.RESEARCH), search=search, research=[_research()])

    _dispatch(
        rig,
        DispatchRequest(
            user_request="Research X.",
            provided_context="USER-NOTE: budget is tight",
        ),
    )

    prompt = rig.research.calls[0].user_prompt
    assert "USER-NOTE: budget is tight" in prompt
    assert SEARCH_MARK_URL in prompt
    assert "USER-PROVIDED CONTEXT" in prompt and "SEARCH EVIDENCE" in prompt


# --------------------------------------------------------------------------- #
# Search failure: stop, no retry, no fallback, only 1 model call
# --------------------------------------------------------------------------- #
def test_search_failure_stops_with_one_model_call_and_no_specialist() -> None:
    rig = make_rig(
        _routing(AgentRoute.RESEARCH),
        search=_FailingSearchProvider(),
        research=[_research()],
    )

    with pytest.raises(SearchProviderError):
        _dispatch(rig, DispatchRequest(user_request="Research X."))

    assert len(rig.orch.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0
    assert _model_calls(rig) == 1  # orchestrator only


# --------------------------------------------------------------------------- #
# No search provider configured -> behaviour unchanged (context passes through)
# --------------------------------------------------------------------------- #
def test_skill_isolation_holds_with_search(tmp_path) -> None:
    registry = LocalSkillRegistry()
    comparison_instructions = registry.load(
        skill_for_route(AgentRoute.COMPARISON)
    ).instructions

    orch = MockModelProvider(structured_responses=[_routing(AgentRoute.COMPARISON)])
    cmp = MockModelProvider(structured_responses=[_comparison()])
    search = MockSearchProvider(responses=[_search_response()])

    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(
            MockModelProvider(),
            registry.load(skill_for_route(AgentRoute.RESEARCH)).instructions,
        ),
        comparison_agent=ComparisonAgent(cmp, comparison_instructions),
        brief_agent=BriefAgent(
            MockModelProvider(),
            registry.load(skill_for_route(AgentRoute.BRIEF)).instructions,
        ),
        search_provider=search,
    )
    asyncio.run(
        dispatcher.dispatch(DispatchRequest(user_request="Compare A and B."), CTX)
    )

    system_prompt = cmp.calls[0].system_prompt
    assert "# Comparison skill" in system_prompt
    assert "# Research skill" not in system_prompt
    assert "# Executive brief skill" not in system_prompt
    # search evidence lives in the *user* prompt, not the skill/system prompt
    assert SEARCH_MARK_URL in cmp.calls[0].user_prompt
    assert len(search.calls) == 1


def test_without_search_provider_context_passes_through_unchanged() -> None:
    orch = MockModelProvider(
        structured_responses=[_routing(AgentRoute.RESEARCH)]
    )
    res = MockModelProvider(structured_responses=[_research()])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(res),
        comparison_agent=ComparisonAgent(MockModelProvider()),
        brief_agent=BriefAgent(MockModelProvider()),
        search_provider=None,
    )
    asyncio.run(
        dispatcher.dispatch(
            DispatchRequest(user_request="Research X.", provided_context="only user"),
            CTX,
        )
    )
    prompt = res.calls[0].user_prompt
    assert "only user" in prompt
    assert "SEARCH EVIDENCE" not in prompt
