"""Only the selected specialist's skill body reaches its prompt.

Also proves skill wiring adds zero ModelProvider calls: a full skill-aware
dispatch is still exactly 2 calls.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest
from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import (
    BriefInput,
    BriefResponse,
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
    ResearchInput,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.agents.orchestrator import OrchestratorAgent
from app.providers.mock import MockModelProvider
from app.skills.local import LocalSkillRegistry
from app.skills.mapping import skill_for_route

CTX = AgentRuntimeContext(run_id="skill-isolation")

# Distinctive markers from each SKILL.md body heading.
RESEARCH_MARK = "# Research skill"
COMPARISON_MARK = "# Comparison skill"
BRIEF_MARK = "# Executive brief skill"


@pytest.fixture(scope="module")
def registry() -> LocalSkillRegistry:
    return LocalSkillRegistry()


def _instructions(registry: LocalSkillRegistry, route: AgentRoute) -> str:
    return registry.load(skill_for_route(route)).instructions


def test_research_agent_gets_only_research_skill(registry: LocalSkillRegistry) -> None:
    provider = MockModelProvider(
        structured_responses=[ResearchResponse(topic="t", summary="s")]
    )
    agent = ResearchAgent(provider, _instructions(registry, AgentRoute.RESEARCH))
    asyncio.run(agent.run(ResearchInput(user_request="x"), CTX))

    prompt = provider.calls[0].system_prompt
    assert RESEARCH_MARK in prompt
    assert COMPARISON_MARK not in prompt
    assert BRIEF_MARK not in prompt


def test_comparison_agent_gets_only_comparison_skill(
    registry: LocalSkillRegistry,
) -> None:
    provider = MockModelProvider(
        structured_responses=[
            ComparisonResponse(
                question="q",
                options=[ComparisonOption(name="A")],
                recommendation="A",
                rationale="r",
                confidence=0.5,
            )
        ]
    )
    agent = ComparisonAgent(provider, _instructions(registry, AgentRoute.COMPARISON))
    asyncio.run(agent.run(ComparisonInput(user_request="x"), CTX))

    prompt = provider.calls[0].system_prompt
    assert COMPARISON_MARK in prompt
    assert RESEARCH_MARK not in prompt
    assert BRIEF_MARK not in prompt


def test_brief_agent_gets_only_brief_skill(registry: LocalSkillRegistry) -> None:
    provider = MockModelProvider(
        structured_responses=[BriefResponse(title="T", executive_summary="E", key_points=["k"])]
    )
    agent = BriefAgent(provider, _instructions(registry, AgentRoute.BRIEF))
    asyncio.run(
        agent.run(BriefInput(user_request="x", provided_context="material"), CTX)
    )

    prompt = provider.calls[0].system_prompt
    assert BRIEF_MARK in prompt
    assert RESEARCH_MARK not in prompt
    assert COMPARISON_MARK not in prompt


def test_no_skill_reference_or_script_body_in_prompt(registry: LocalSkillRegistry) -> None:
    provider = MockModelProvider(
        structured_responses=[
            ComparisonResponse(
                question="q",
                options=[ComparisonOption(name="A")],
                recommendation="A",
                rationale="r",
                confidence=0.5,
            )
        ]
    )
    agent = ComparisonAgent(provider, _instructions(registry, AgentRoute.COMPARISON))
    asyncio.run(agent.run(ComparisonInput(user_request="x"), CTX))

    prompt = provider.calls[0].system_prompt
    assert "Six steps" not in prompt  # from comparison-framework.md reference
    assert "Preferred structure" not in prompt  # from brief-template.md reference


def test_skill_aware_dispatch_is_still_exactly_two_calls(
    registry: LocalSkillRegistry,
) -> None:
    orch_p = MockModelProvider(
        structured_responses=[
            RoutingDecision(route=AgentRoute.COMPARISON, reasoning="compare")
        ]
    )
    cmp_p = MockModelProvider(
        structured_responses=[
            ComparisonResponse(
                question="q",
                options=[ComparisonOption(name="A")],
                recommendation="A",
                rationale="r",
                confidence=0.5,
            )
        ]
    )
    res_p = MockModelProvider(structured_responses=[])
    brf_p = MockModelProvider(structured_responses=[])

    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch_p),
        research_agent=ResearchAgent(res_p, _instructions(registry, AgentRoute.RESEARCH)),
        comparison_agent=ComparisonAgent(
            cmp_p, _instructions(registry, AgentRoute.COMPARISON)
        ),
        brief_agent=BriefAgent(brf_p, _instructions(registry, AgentRoute.BRIEF)),
    )

    asyncio.run(
        dispatcher.dispatch(DispatchRequest(user_request="Compare A and B."), CTX)
    )

    assert len(orch_p.calls) == 1
    assert len(cmp_p.calls) == 1
    assert len(res_p.calls) == 0
    assert len(brf_p.calls) == 0
