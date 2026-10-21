"""The research agent's grounded mode: cited findings verified in code."""

from __future__ import annotations

import asyncio

from app.agents.base import AgentRuntimeContext
from app.agents.research import ResearchAgent
from app.models.grounding import Finding, GroundedResearch
from app.models.search import SearchResult
from app.models.specialists import ResearchInput
from app.providers.mock import MockModelProvider

EVIDENCE = [
    SearchResult(title="Agent loops", url="https://a.example/loops",
                 snippet="Teams cap agent loops at a fixed number of tool calls to bound cost."),
    SearchResult(title="Agent evals", url="https://b.example/evals",
                 snippet="Golden-set evals catch regressions before release."),
]

RESEARCH = GroundedResearch(
    topic="Agentic workflows",
    summary="Production agents are bounded and evaluated.",
    findings=[
        Finding(claim="Loops are capped to control cost.", source=1,
                quote="cap agent loops at a fixed number of tool calls"),
        Finding(claim="Evals use golden sets.", source=2,
                quote="Golden-set evals catch regressions"),
        Finding(claim="Agents always use vector memory.", source=2,
                quote="every agent uses vector memory"),
        Finding(claim="Tool schemas should be explicit."),
    ],
    open_questions=["How large should a golden set be?"],
)


def _run(evidence=EVIDENCE):
    provider = MockModelProvider(structured_responses=[RESEARCH])
    agent = ResearchAgent(provider, grounded=True)
    response = asyncio.run(agent.run(
        ResearchInput(user_request="Research agentic workflows", evidence=evidence),
        AgentRuntimeContext(run_id="t"),
    ))
    return provider, response


def test_one_call_for_grounded_research_without_urls_in_the_prompt() -> None:
    provider, _ = _run()
    assert len(provider.calls) == 1
    assert provider.calls[0].response_model is GroundedResearch
    assert "Never write URLs" in provider.calls[0].system_prompt


def test_only_verified_findings_keep_citations_and_sources_come_from_code() -> None:
    _, response = _run()
    assert response.key_findings == [
        "Loops are capped to control cost. [1]",
        "Evals use golden sets. [2]",
        "Tool schemas should be explicit. (general knowledge)",
    ]
    assert response.sources == ["https://a.example/loops", "https://b.example/evals"]
    assert any("vector memory" in note and "not found in Result 2" in note
               for note in response.limitations)
    assert "How large should a golden set be?" in response.limitations
    g = response.grounding
    assert (g.verified, g.unsupported, g.model_knowledge) == (2, 1, 1)


def test_without_evidence_every_citation_is_unsupported_and_flagged() -> None:
    _, response = _run(evidence=[])
    assert response.sources == []
    assert response.grounding.verified == 0
    assert any("No search evidence" in note for note in response.limitations)
