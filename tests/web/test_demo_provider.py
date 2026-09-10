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
    assert body["result"]["question"] == "Demo comparison"
