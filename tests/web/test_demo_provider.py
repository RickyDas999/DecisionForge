"""The web demo provider is deterministic and offline (no network, no Anthropic)."""

from __future__ import annotations

import asyncio

import pytest

from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import (
    BriefResponse,
    ComparisonResponse,
    ResearchResponse,
)
from app.web.bootstrap import create_demo_app, create_demo_service
from app.web.demo_provider import DemoModelProvider


def _structured(model):
    return asyncio.run(
        DemoModelProvider().generate_structured(
            system_prompt="s", user_prompt="Compare PostgreSQL and MongoDB.", response_model=model
        )
    )


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("Research current vector databases", AgentRoute.RESEARCH),
        ("Compare PostgreSQL and MongoDB", AgentRoute.COMPARISON),
        ("Should we use AWS or GCP", AgentRoute.COMPARISON),
        ("Turn this into an executive brief", AgentRoute.BRIEF),
        ("Summarize the following for leadership", AgentRoute.BRIEF),
    ],
)
def test_demo_router_is_deterministic(prompt: str, expected: AgentRoute) -> None:
    decision = asyncio.run(
        DemoModelProvider().generate_structured(
            system_prompt="s", user_prompt=prompt, response_model=RoutingDecision
        )
    )
    assert isinstance(decision, RoutingDecision)
    assert decision.route is expected


def test_demo_provider_returns_valid_specialist_models() -> None:
    assert isinstance(_structured(ResearchResponse), ResearchResponse)
    cmp = _structured(ComparisonResponse)
    assert isinstance(cmp, ComparisonResponse)
    assert 0.0 <= cmp.confidence <= 1.0
    assert isinstance(_structured(BriefResponse), BriefResponse)


def test_demo_provider_has_no_generate_text() -> None:
    with pytest.raises(NotImplementedError):
        asyncio.run(
            DemoModelProvider().generate_text(system_prompt="s", user_prompt="u")
        )


def test_demo_app_end_to_end_is_offline(tmp_path) -> None:
    from fastapi.testclient import TestClient

    service, repo = create_demo_service(db_path=str(tmp_path / "demo.db"))
    app = create_demo_app(db_path=str(tmp_path / "demo2.db"))
    client = TestClient(app)

    resp = client.post(
        "/api/runs",
        json={"user_request": "Compare PostgreSQL and MongoDB for a SaaS startup."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "comparison"
    assert body["status"] == "completed"
    result = body["result"]
    assert [o["name"] for o in result["options"]] == ["PostgreSQL", "MongoDB"]
    report = result["decision_report"]
    assert report["winner"] in {"PostgreSQL", "MongoDB"}
    assert result["confidence"] == report["win_probability"]


def test_demo_second_opinion_differs_from_first() -> None:
    from app.agents.comparison import SECOND_OPINION_NOTE
    from app.models.decision import DecisionModel

    prompt = "Comparison request:\nAWS or GCP?\n\nSupplied context: none."
    provider = DemoModelProvider()
    first = asyncio.run(provider.generate_structured(
        system_prompt="s", user_prompt=prompt, response_model=DecisionModel))
    second = asyncio.run(provider.generate_structured(
        system_prompt="s", user_prompt=prompt + SECOND_OPINION_NOTE, response_model=DecisionModel))
    assert first.options == second.options == ["AWS", "GCP"]
    assert first.scores != second.scores


def test_demo_grounded_research_quotes_real_evidence() -> None:
    from app.agents.base import AgentRuntimeContext
    from app.agents.research import ResearchAgent, _build_user_prompt
    from app.models.specialists import ResearchInput
    from app.tools.context import build_search_context, rendered_results
    from app.web.demo_provider import DemoSearchProvider

    response = asyncio.run(DemoSearchProvider().search("agentic workflows"))
    task = ResearchInput(user_request="Research agentic workflows",
                         provided_context=build_search_context(response),
                         evidence=rendered_results(response))
    assert "Result 1" in _build_user_prompt(task)
    result = asyncio.run(ResearchAgent(DemoModelProvider(), grounded=True).run(
        task, AgentRuntimeContext(run_id="t")))
    g = result.grounding
    assert g.verified == len(task.evidence)  # every real quote verifies
    assert g.unsupported == 1 and g.model_knowledge == 1  # the deliberate cases
    assert result.sources == [r.url for r in task.evidence]
