"""Tests for :class:`OrchestratorAgent`. Every test uses ``MockModelProvider``.

No real Anthropic calls occur.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    OrchestratorAgent,
    build_user_prompt,
)
from app.models.routing import AgentRoute, RoutingDecision, RoutingInput
from app.providers.exceptions import StructuredOutputError
from app.providers.mock import MockModelProvider

RESEARCH_REQUEST = "Research current open-source vector databases."
COMPARISON_REQUEST = "Compare PostgreSQL and MongoDB for a small startup."
BRIEF_REQUEST = (
    "Using the findings below, write an executive brief for leadership: "
    "vector DB adoption is rising, three vendors dominate, cost varies widely."
)


def _context() -> AgentRuntimeContext:
    return AgentRuntimeContext(run_id="test-run")


def _run(agent: OrchestratorAgent, routing_input: RoutingInput) -> RoutingDecision:
    return asyncio.run(agent.run(routing_input, _context()))


def _provider(route: AgentRoute) -> MockModelProvider:
    return MockModelProvider(
        structured_responses=[
            RoutingDecision(route=route, reasoning="classified for the test")
        ]
    )


def test_name_is_orchestrator() -> None:
    assert OrchestratorAgent(_provider(AgentRoute.RESEARCH)).name == "orchestrator"


def test_research_request_routes_to_research() -> None:
    agent = OrchestratorAgent(_provider(AgentRoute.RESEARCH))
    decision = _run(agent, RoutingInput(user_request=RESEARCH_REQUEST))
    assert decision.route is AgentRoute.RESEARCH


def test_comparison_request_routes_to_comparison() -> None:
    agent = OrchestratorAgent(_provider(AgentRoute.COMPARISON))
    decision = _run(agent, RoutingInput(user_request=COMPARISON_REQUEST))
    assert decision.route is AgentRoute.COMPARISON


def test_brief_request_routes_to_brief() -> None:
    agent = OrchestratorAgent(_provider(AgentRoute.BRIEF))
    decision = _run(agent, RoutingInput(user_request=BRIEF_REQUEST))
    assert decision.route is AgentRoute.BRIEF


def test_uses_generate_structured_with_routing_decision_model() -> None:
    provider = _provider(AgentRoute.RESEARCH)
    agent = OrchestratorAgent(provider)
    _run(agent, RoutingInput(user_request=RESEARCH_REQUEST))

    assert len(provider.calls) == 1
    call = provider.calls[0]
    assert call.operation == "generate_structured"
    assert call.response_model is RoutingDecision


def test_user_request_appears_in_user_prompt() -> None:
    provider = _provider(AgentRoute.COMPARISON)
    agent = OrchestratorAgent(provider)
    _run(agent, RoutingInput(user_request=COMPARISON_REQUEST))

    assert COMPARISON_REQUEST in provider.calls[0].user_prompt


def test_system_prompt_is_used() -> None:
    provider = _provider(AgentRoute.RESEARCH)
    agent = OrchestratorAgent(provider)
    _run(agent, RoutingInput(user_request=RESEARCH_REQUEST))

    assert provider.calls[0].system_prompt == ORCHESTRATOR_SYSTEM_PROMPT


def test_does_not_mutate_routing_input() -> None:
    provider = _provider(AgentRoute.RESEARCH)
    agent = OrchestratorAgent(provider)
    routing_input = RoutingInput(user_request=RESEARCH_REQUEST)
    snapshot = routing_input.model_copy(deep=True)

    _run(agent, routing_input)

    assert routing_input == snapshot
    assert routing_input.user_request == RESEARCH_REQUEST


def test_route_is_a_valid_agent_route() -> None:
    agent = OrchestratorAgent(_provider(AgentRoute.BRIEF))
    decision = _run(agent, RoutingInput(user_request=BRIEF_REQUEST))
    assert isinstance(decision.route, AgentRoute)


def test_invalid_route_from_model_raises_structured_output_error() -> None:
    provider = MockModelProvider(
        structured_responses=[{"route": "planner", "reasoning": "not a real route"}]
    )
    agent = OrchestratorAgent(provider)
    with pytest.raises(StructuredOutputError):
        _run(agent, RoutingInput(user_request=RESEARCH_REQUEST))


def test_exactly_one_structured_call_and_no_text_call() -> None:
    provider = _provider(AgentRoute.RESEARCH)
    agent = OrchestratorAgent(provider)
    _run(agent, RoutingInput(user_request=RESEARCH_REQUEST))

    assert len(provider.calls) == 1
    assert all(c.operation == "generate_structured" for c in provider.calls)
    assert provider.text_responses == []  # never consulted


def test_empty_request_is_rejected_before_any_model_call() -> None:
    with pytest.raises(ValueError):
        RoutingInput(user_request="   ")


# --------------------------------------------------------------------------- #
# Prompt constraint checks (behavioural intent, not exact prose)
# --------------------------------------------------------------------------- #
def test_system_prompt_communicates_core_constraints() -> None:
    prompt = ORCHESTRATOR_SYSTEM_PROMPT.lower()
    assert "exactly one" in prompt
    assert "do not answer" in prompt
    assert "do not perform the specialist" in prompt
    assert "do not create multi-agent workflows" in prompt
    for route in ("research", "comparison", "brief"):
        assert route in prompt


def test_build_user_prompt_contains_request_and_no_answer_instruction() -> None:
    built = build_user_prompt("some request text")
    assert "some request text" in built
    assert "select exactly one route" in built.lower()
