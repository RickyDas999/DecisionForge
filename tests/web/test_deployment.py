"""Vercel-entrypoint + stateless-deployment tests. Mocks only; no network.

Covers: `api.index` is import-safe, the deployment bootstrap runs offline, the
stateless `NullRunRepository` mode still returns a full renderable result, the
2-LLM-call ceiling holds, and `/api/health` is safe.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.persistence import ExecutionEvent, RunRecord
from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import ComparisonOption, ComparisonResponse, ResearchResponse
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.persistence.null import NullRunRepository
from app.providers.mock import MockModelProvider
from app.service import DecisionForgeService
from app.web.app import create_app
from app.web.deployment import create_deployment_app


# --------------------------------------------------------------------------- #
# Vercel entrypoint
# --------------------------------------------------------------------------- #
def test_api_index_imports_and_exposes_fastapi_app(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.delenv("PERSISTENCE_ENABLED", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    sys.modules.pop("api.index", None)

    import api.index as entry

    assert isinstance(entry.app, FastAPI)


def test_deployment_mock_mode_never_builds_a_real_model_provider(monkeypatch) -> None:
    """Mock mode uses DemoModelProvider — the real factory (and the Anthropic SDK
    it would import) is never touched."""
    monkeypatch.setenv("MODEL_PROVIDER", "mock")
    monkeypatch.delenv("PERSISTENCE_ENABLED", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)

    calls: list[object] = []
    monkeypatch.setattr(
        "app.web.deployment.create_model_provider",
        lambda *a, **k: calls.append(1),
    )
    monkeypatch.setattr(
        "app.web.deployment.create_search_provider",
        lambda *a, **k: calls.append(1),
    )

    app = create_deployment_app()
    assert isinstance(app, FastAPI)
    assert calls == []  # neither real provider factory was invoked


def test_api_index_health_is_mock_and_stateless_by_default(monkeypatch) -> None:
    for var in ("MODEL_PROVIDER", "PERSISTENCE_ENABLED", "SEARCH_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    client = TestClient(create_deployment_app())
    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["model_provider"] == "mock"
    assert health["persistence_enabled"] is False
    assert health["max_llm_calls"] == 2
    # mock mode wires the offline demo search so the trace shows the step
    assert health["search_provider"] == "demo (offline)"
    assert health["search_enabled"] is True


def test_health_search_is_none_in_anthropic_mode_without_explicit_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-not-real")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-test-model")
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)

    class _StubProvider:
        messages = object()

    # don't build a real Anthropic client during construction
    monkeypatch.setattr(
        "app.web.deployment.create_model_provider", lambda *a, **k: _StubProvider()
    )
    health = TestClient(create_deployment_app()).get("/api/health").json()
    assert health["model_provider"] == "anthropic"
    assert health["search_provider"] == "none"
    assert health["search_enabled"] is False


def test_health_search_reports_duckduckgo_when_selected(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)  # mock
    monkeypatch.setenv("SEARCH_PROVIDER", "duckduckgo")
    health = TestClient(create_deployment_app()).get("/api/health").json()
    assert health["search_provider"] == "duckduckgo"
    assert health["search_enabled"] is True


def test_health_never_leaks_secrets(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-not-appear")
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    client = TestClient(create_deployment_app())
    body = client.get("/api/health").text
    assert "sk-ant" not in body


# --------------------------------------------------------------------------- #
# Deployment demo mode (offline DemoModelProvider)
# --------------------------------------------------------------------------- #
@pytest.fixture
def demo_client(monkeypatch) -> TestClient:
    for var in ("MODEL_PROVIDER", "PERSISTENCE_ENABLED", "SEARCH_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    return TestClient(create_deployment_app())


def test_demo_index_and_static(demo_client: TestClient) -> None:
    assert demo_client.get("/").status_code == 200
    assert "DecisionForge" in demo_client.get("/").text
    assert demo_client.get("/static/app.js").status_code == 200


@pytest.mark.parametrize(
    ("request_body", "expected_route"),
    [
        ({"user_request": "Research current vector databases."}, "research"),
        ({"user_request": "Compare PostgreSQL and MongoDB."}, "comparison"),
        (
            {
                "user_request": "Turn these findings into an executive brief.",
                "provided_context": "We evaluated two approaches over three weeks.",
            },
            "brief",
        ),
    ],
)
def test_demo_post_run_returns_full_renderable_result(
    demo_client: TestClient, request_body: dict, expected_route: str
) -> None:
    resp = demo_client.post("/api/runs", json=request_body)
    assert resp.status_code == 200
    body = resp.json()

    assert body["status"] == "completed"
    assert body["route"] == expected_route
    assert body["run_id"]
    assert body["routing_reasoning"]
    assert body["selected_specialist"]
    assert body["result"] is not None
    # the trace is in the POST response — no follow-up request required
    trace = [e["event_type"] for e in body["events"]]
    assert trace[0] == "run.started"
    assert trace[-1] == "run.completed"
    assert "route.selected" in trace


def test_demo_recent_runs_is_empty_when_stateless(demo_client: TestClient) -> None:
    demo_client.post("/api/runs", json={"user_request": "Research vector databases."})
    assert demo_client.get("/api/runs").json() == {"runs": []}


def test_demo_get_run_by_id_is_404_when_stateless(demo_client: TestClient) -> None:
    run_id = demo_client.post(
        "/api/runs", json={"user_request": "Research vector databases."}
    ).json()["run_id"]
    assert demo_client.get(f"/api/runs/{run_id}").status_code == 404


# --------------------------------------------------------------------------- #
# Stateless mode with countable mock providers — the 2-call ceiling
# --------------------------------------------------------------------------- #
@dataclass
class Rig:
    client: TestClient
    orch: MockModelProvider
    comparison: MockModelProvider
    research: MockModelProvider


def _stateless_rig() -> Rig:
    orch = MockModelProvider(
        structured_responses=[RoutingDecision(route=AgentRoute.COMPARISON, reasoning="cmp")]
    )
    cmp = MockModelProvider(
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
    res = MockModelProvider(structured_responses=[ResearchResponse(topic="t", summary="s")])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(res),
        comparison_agent=ComparisonAgent(cmp),
        brief_agent=BriefAgent(MockModelProvider()),
    )
    repo = NullRunRepository()
    app = create_app(DecisionForgeService(dispatcher, repo), repo)
    return Rig(TestClient(app), orch, cmp, res)


def test_stateless_run_is_two_model_calls_and_not_persisted() -> None:
    rig = _stateless_rig()
    resp = rig.client.post("/api/runs", json={"user_request": "Compare A and B."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["route"] == "comparison"

    assert len(rig.orch.calls) == 1
    assert len(rig.comparison.calls) == 1
    assert len(rig.research.calls) == 0
    assert len(rig.orch.calls) + len(rig.comparison.calls) + len(rig.research.calls) == 2

    # nothing was persisted
    assert rig.client.get("/api/runs").json() == {"runs": []}
    assert rig.client.get(f"/api/runs/{body['run_id']}").status_code == 404
    assert rig.client.get("/api/health").json()["persistence_enabled"] is False


def test_stateless_failure_still_maps_cleanly_without_retry() -> None:
    orch = MockModelProvider(
        structured_responses=[RoutingDecision(route=AgentRoute.RESEARCH, reasoning="r")]
    )
    bad_research = MockModelProvider(structured_responses=[{"nope": True}])
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(orch),
        research_agent=ResearchAgent(bad_research),
        comparison_agent=ComparisonAgent(MockModelProvider()),
        brief_agent=BriefAgent(MockModelProvider()),
    )
    repo = NullRunRepository()
    client = TestClient(create_app(DecisionForgeService(dispatcher, repo), repo))

    resp = client.post("/api/runs", json={"user_request": "Research X."})
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_type"] == "StructuredOutputError"
    assert "Traceback" not in body["detail"]
    assert len(orch.calls) == 1
    assert len(bad_research.calls) == 1  # one attempt, no retry


# --------------------------------------------------------------------------- #
# NullRunRepository unit behaviour
# --------------------------------------------------------------------------- #
def test_null_repository_writes_are_noops_and_reads_are_empty() -> None:
    repo = NullRunRepository()
    repo.create_run(RunRecord(run_id="r1", user_request="q"))
    repo.set_search_used("r1", True)
    repo.mark_completed("r1", result_json="{}")
    repo.append_event(
        ExecutionEvent(run_id="r1", event_type="run.started")  # type: ignore[arg-type]
    )
    assert repo.get_run("r1") is None
    assert repo.list_recent_runs() == []
    assert repo.get_events("r1") == []
