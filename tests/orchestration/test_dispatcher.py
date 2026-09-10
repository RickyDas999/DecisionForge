"""Tests for :class:`DecisionForgeDispatcher`.

Every agent is backed by its own ``MockModelProvider`` so call counts can be
asserted per agent. No real Anthropic calls occur.
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
from app.models.dispatch import DispatchRequest, DispatchResult
from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.orchestration.exceptions import MissingBriefContextError
from app.providers.exceptions import MockResponseExhaustedError, StructuredOutputError
from app.providers.mock import MockModelProvider

CTX = AgentRuntimeContext(run_id="dispatch-test")


def _routing(route: AgentRoute, reasoning: str = "because") -> RoutingDecision:
    return RoutingDecision(route=route, reasoning=reasoning)


def _research() -> ResearchResponse:
    return ResearchResponse(topic="t", summary="s", key_findings=["f"], limitations=["l"])


def _comparison() -> ComparisonResponse:
    return ComparisonResponse(
        question="q",
        options=[ComparisonOption(name="A"), ComparisonOption(name="B")],
        recommendation="A",
        rationale="why",
        important_tradeoffs=["x"],
        confidence=0.6,
        limitations=["no live data"],
    )


def _brief() -> BriefResponse:
    return BriefResponse(title="T", executive_summary="ES", key_points=["k"])


@dataclass
class Rig:
    dispatcher: DecisionForgeDispatcher
    orchestrator: MockModelProvider
    research: MockModelProvider
    comparison: MockModelProvider
    brief: MockModelProvider


def make_rig(
    routing_decision: RoutingDecision,
    *,
    research: list | None = None,
    comparison: list | None = None,
    brief: list | None = None,
) -> Rig:
    orch_p = MockModelProvider(structured_responses=[routing_decision])
    res_p = MockModelProvider(structured_responses=research or [])
    cmp_p = MockModelProvider(structured_responses=comparison or [])
    brf_p = MockModelProvider(structured_responses=brief or [])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch_p),
        research_agent=ResearchAgent(res_p),
        comparison_agent=ComparisonAgent(cmp_p),
        brief_agent=BriefAgent(brf_p),
    )
    return Rig(dispatcher, orch_p, res_p, cmp_p, brf_p)


def _dispatch(rig: Rig, request: DispatchRequest) -> DispatchResult:
    return asyncio.run(rig.dispatcher.dispatch(request, CTX))


# --------------------------------------------------------------------------- #
# Per-route call routing
# --------------------------------------------------------------------------- #
def test_research_route_calls_only_research() -> None:
    rig = make_rig(_routing(AgentRoute.RESEARCH), research=[_research()])
    result = _dispatch(rig, DispatchRequest(user_request="Explain vector DBs."))

    assert isinstance(result.result, ResearchResponse)
    assert len(rig.orchestrator.calls) == 1
    assert len(rig.research.calls) == 1
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0


def test_comparison_route_calls_only_comparison() -> None:
    rig = make_rig(_routing(AgentRoute.COMPARISON), comparison=[_comparison()])
    result = _dispatch(rig, DispatchRequest(user_request="Compare A and B."))

    assert isinstance(result.result, ComparisonResponse)
    assert len(rig.orchestrator.calls) == 1
    assert len(rig.comparison.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.brief.calls) == 0


def test_brief_route_with_context_calls_only_brief() -> None:
    rig = make_rig(_routing(AgentRoute.BRIEF), brief=[_brief()])
    result = _dispatch(
        rig,
        DispatchRequest(
            user_request="Make a brief.", provided_context="Real source material."
        ),
    )

    assert isinstance(result.result, BriefResponse)
    assert len(rig.orchestrator.calls) == 1
    assert len(rig.brief.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.comparison.calls) == 0


# --------------------------------------------------------------------------- #
# Result assembly
# --------------------------------------------------------------------------- #
def test_result_route_matches_routing_decision() -> None:
    rig = make_rig(_routing(AgentRoute.RESEARCH), research=[_research()])
    result = _dispatch(rig, DispatchRequest(user_request="x"))
    assert result.route is AgentRoute.RESEARCH


def test_routing_reasoning_is_preserved() -> None:
    rig = make_rig(
        _routing(AgentRoute.COMPARISON, "explicit compare of two options"),
        comparison=[_comparison()],
    )
    result = _dispatch(rig, DispatchRequest(user_request="x"))
    assert result.routing_reasoning == "explicit compare of two options"


def test_result_preserves_typed_specialist_response() -> None:
    expected = _comparison()
    rig = make_rig(_routing(AgentRoute.COMPARISON), comparison=[expected])
    result = _dispatch(rig, DispatchRequest(user_request="x"))
    assert isinstance(result.result, ComparisonResponse)
    assert result.result.recommendation == "A"
    assert result.result.confidence == 0.6


# --------------------------------------------------------------------------- #
# provided_context propagation
# --------------------------------------------------------------------------- #
def test_context_passed_to_research_agent() -> None:
    rig = make_rig(_routing(AgentRoute.RESEARCH), research=[_research()])
    _dispatch(
        rig,
        DispatchRequest(user_request="req", provided_context="EVIDENCE-R"),
    )
    assert "EVIDENCE-R" in rig.research.calls[0].user_prompt


def test_context_passed_to_comparison_agent() -> None:
    rig = make_rig(_routing(AgentRoute.COMPARISON), comparison=[_comparison()])
    _dispatch(
        rig,
        DispatchRequest(user_request="req", provided_context="EVIDENCE-C"),
    )
    assert "EVIDENCE-C" in rig.comparison.calls[0].user_prompt


def test_context_passed_to_brief_agent() -> None:
    rig = make_rig(_routing(AgentRoute.BRIEF), brief=[_brief()])
    _dispatch(
        rig,
        DispatchRequest(user_request="req", provided_context="EVIDENCE-B"),
    )
    assert "EVIDENCE-B" in rig.brief.calls[0].user_prompt


# --------------------------------------------------------------------------- #
# Brief missing-context behaviour
# --------------------------------------------------------------------------- #
def test_brief_route_without_context_raises_missing_brief_context_error() -> None:
    rig = make_rig(_routing(AgentRoute.BRIEF), brief=[_brief()])
    with pytest.raises(MissingBriefContextError):
        _dispatch(rig, DispatchRequest(user_request="Make a brief."))


def test_brief_route_blank_context_raises_missing_brief_context_error() -> None:
    rig = make_rig(_routing(AgentRoute.BRIEF), brief=[_brief()])
    with pytest.raises(MissingBriefContextError):
        _dispatch(
            rig,
            DispatchRequest(user_request="Make a brief.", provided_context="   "),
        )


def test_brief_missing_context_makes_one_orchestrator_call_and_no_specialist_call() -> None:
    rig = make_rig(_routing(AgentRoute.BRIEF), brief=[_brief()])
    with pytest.raises(MissingBriefContextError):
        _dispatch(rig, DispatchRequest(user_request="Make a brief."))

    assert len(rig.orchestrator.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0


# --------------------------------------------------------------------------- #
# Error propagation — no fallback, no extra agent calls
# --------------------------------------------------------------------------- #
def test_specialist_exception_propagates_without_other_agent_calls() -> None:
    # Research provider returns an invalid payload -> StructuredOutputError.
    rig = make_rig(_routing(AgentRoute.RESEARCH), research=[{"nope": True}])
    with pytest.raises(StructuredOutputError):
        _dispatch(rig, DispatchRequest(user_request="x"))

    assert len(rig.orchestrator.calls) == 1
    assert len(rig.research.calls) == 1
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0


def test_orchestrator_exception_propagates_without_specialist_call() -> None:
    rig = make_rig(_routing(AgentRoute.RESEARCH), research=[_research()])
    rig.orchestrator.structured_responses.clear()  # force exhaustion on routing
    with pytest.raises(MockResponseExhaustedError):
        _dispatch(rig, DispatchRequest(user_request="x"))

    assert len(rig.orchestrator.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.comparison.calls) == 0
    assert len(rig.brief.calls) == 0


# --------------------------------------------------------------------------- #
# The two-call maximum
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("route", "kwargs", "provider_attr", "context"),
    [
        (AgentRoute.RESEARCH, {"research": [_research()]}, "research", None),
        (AgentRoute.COMPARISON, {"comparison": [_comparison()]}, "comparison", None),
        (AgentRoute.BRIEF, {"brief": [_brief()]}, "brief", "source material"),
    ],
)
def test_successful_dispatch_makes_exactly_two_model_calls(
    route: AgentRoute, kwargs: dict, provider_attr: str, context: str | None
) -> None:
    rig = make_rig(_routing(route), **kwargs)
    _dispatch(
        rig,
        DispatchRequest(user_request="the request", provided_context=context),
    )

    selected = getattr(rig, provider_attr)
    others = [
        p
        for name, p in (
            ("research", rig.research),
            ("comparison", rig.comparison),
            ("brief", rig.brief),
        )
        if name != provider_attr
    ]

    total_calls = (
        len(rig.orchestrator.calls)
        + len(rig.research.calls)
        + len(rig.comparison.calls)
        + len(rig.brief.calls)
    )

    assert len(rig.orchestrator.calls) == 1
    assert len(selected.calls) == 1
    assert all(len(p.calls) == 0 for p in others)
    assert total_calls == 2  # never 3, never 4
