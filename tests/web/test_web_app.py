"""FastAPI endpoint tests. MockModelProvider + MockSearchProvider + temp SQLite.

No network. The web layer adds no model calls: a successful POST /api/runs is
still exactly 2 (orchestrator + one specialist).
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.persistence.sqlite import SQLiteRunRepository
from app.providers.mock import MockModelProvider
from app.service import DecisionForgeService
from app.tools.search import MockSearchProvider, SearchProvider
from app.tools.exceptions import SearchProviderError
from app.web.app import create_app


def _routing(route: AgentRoute) -> RoutingDecision:
    return RoutingDecision(route=route, reasoning="because")


def _research() -> ResearchResponse:
    return ResearchResponse(topic="t", summary="s", key_findings=["kf"], limitations=["lim"])


def _comparison() -> ComparisonResponse:
    return ComparisonResponse(
        question="q",
        options=[ComparisonOption(name="A"), ComparisonOption(name="B")],
        recommendation="A",
        rationale="r",
        important_tradeoffs=["t"],
        confidence=0.5,
        limitations=["lim"],
    )


def _brief() -> BriefResponse:
    return BriefResponse(title="T", executive_summary="ES", key_points=["kp"])


def _search_response() -> SearchResponse:
    return SearchResponse(
        query="q",
        results=[
            SearchResult(
                title="Ev", url="https://ev.example/1", snippet="snip", source="ev.example"
            )
        ],
    )


class _FailingSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        raise SearchProviderError("search backend down")


@dataclass
class Rig:
    client: TestClient
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
    app = create_app(DecisionForgeService(dispatcher, repo), repo)
    return Rig(TestClient(app), repo, orch, res, cmp, brf, search)


def _model_calls(rig: Rig) -> int:
    return sum(
        len(p.calls) for p in (rig.orch, rig.research, rig.comparison, rig.brief)
    )


# --------------------------------------------------------------------------- #
# GET /
# --------------------------------------------------------------------------- #
def test_index_returns_html(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    resp = rig.client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "DecisionForge" in resp.text


def test_static_assets_served(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    assert rig.client.get("/static/app.js").status_code == 200
    assert rig.client.get("/static/styles.css").status_code == 200


# --------------------------------------------------------------------------- #
# POST /api/runs
# --------------------------------------------------------------------------- #
def test_research_run_succeeds_and_is_persisted(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    resp = rig.client.post("/api/runs", json={"user_request": "Research vector DBs."})
    assert resp.status_code == 200
    body = resp.json()

    # the POST response carries the full trace — no follow-up request needed
    assert [e["event_type"] for e in body["events"]] == [
        "run.started",
        "route.selected",
        "specialist.started",
        "specialist.completed",
        "run.completed",
    ]

    assert body["status"] == "completed"
    assert body["route"] == "research"
    assert body["selected_specialist"] == "ResearchAgent"
    assert body["search_used"] is False
    assert body["result"]["topic"] == "t"
    assert body["result"]["key_findings"] == ["kf"]

    # demo metadata for the frontend (deterministic — no model call)
    assert body["selected_skill"] == "research"
    assert body["llm_calls"] == 2
    assert body["llm_calls_max"] == 2
    assert body["routing_reasoning"]

    # persisted
    record = rig.repo.get_run(body["run_id"])
    assert record is not None and record.status.value == "completed"
    event_types = [e.event_type.value for e in rig.repo.get_events(body["run_id"])]
    assert event_types == [
        "run.started",
        "route.selected",
        "specialist.started",
        "specialist.completed",
        "run.completed",
    ]
    assert _model_calls(rig) == 2


def test_comparison_run_with_search_succeeds(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.COMPARISON),
        comparison=[_comparison()],
        search=MockSearchProvider(responses=[_search_response()]),
    )
    resp = rig.client.post("/api/runs", json={"user_request": "Compare A and B."})
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "comparison"
    assert body["search_used"] is True
    assert body["result"]["recommendation"] == "A"
    assert _model_calls(rig) == 2
    ets = [e.event_type.value for e in rig.repo.get_events(body["run_id"])]
    assert "search.started" in ets and "search.completed" in ets


def test_brief_run_with_context_succeeds_without_search(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.BRIEF),
        brief=[_brief()],
        search=MockSearchProvider(responses=[_search_response()]),
    )
    resp = rig.client.post(
        "/api/runs",
        json={"user_request": "Make a brief.", "provided_context": "source material"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["route"] == "brief"
    assert body["search_used"] is False
    assert body["result"]["title"] == "T"
    assert isinstance(rig.search, MockSearchProvider)
    assert rig.search.calls == []
    assert _model_calls(rig) == 2


# --------------------------------------------------------------------------- #
# Error paths
# --------------------------------------------------------------------------- #
def test_blank_request_returns_422(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    resp = rig.client.post("/api/runs", json={"user_request": "   "})
    assert resp.status_code == 422
    assert _model_calls(rig) == 0  # never reached the service


def test_brief_without_context_returns_400_and_persists_failed_run(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.BRIEF), brief=[_brief()])
    resp = rig.client.post("/api/runs", json={"user_request": "Make a brief."})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_type"] == "MissingBriefContextError"
    assert body["run_id"]

    record = rig.repo.get_run(body["run_id"])
    assert record.status.value == "failed"
    assert record.error and "MissingBriefContextError" in record.error
    ets = [e.event_type.value for e in rig.repo.get_events(body["run_id"])]
    assert ets == ["run.started", "route.selected", "run.failed"]
    assert len(rig.brief.calls) == 0  # no specialist call, no retry


def test_specialist_failure_returns_500_with_safe_body(tmp_path) -> None:
    rig = make_rig(
        tmp_path, _routing(AgentRoute.RESEARCH), research=[{"bad": True}]
    )
    resp = rig.client.post("/api/runs", json={"user_request": "Research X."})
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_type"] == "StructuredOutputError"
    assert "Traceback" not in body["detail"]
    assert "sk-ant" not in body["detail"]
    assert rig.repo.get_run(body["run_id"]).status.value == "failed"
    assert len(rig.orch.calls) == 1
    assert len(rig.research.calls) == 1  # one attempt, no retry


def test_search_failure_returns_500_and_persists_failed(tmp_path) -> None:
    rig = make_rig(
        tmp_path,
        _routing(AgentRoute.RESEARCH),
        research=[_research()],
        search=_FailingSearch(),
    )
    resp = rig.client.post("/api/runs", json={"user_request": "Research X."})
    assert resp.status_code == 500
    body = resp.json()
    assert body["error_type"] == "SearchProviderError"
    record = rig.repo.get_run(body["run_id"])
    assert record.status.value == "failed"
    assert record.route == "research"
    assert len(rig.research.calls) == 0  # no specialist, no fallback


# --------------------------------------------------------------------------- #
# GET /api/runs and /api/runs/{id}
# --------------------------------------------------------------------------- #
def test_recent_runs_lists_completed_runs(tmp_path) -> None:
    orch = MockModelProvider(
        structured_responses=[_routing(AgentRoute.RESEARCH), _routing(AgentRoute.COMPARISON)]
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
    client = TestClient(create_app(DecisionForgeService(dispatcher, repo), repo))

    client.post("/api/runs", json={"user_request": "Research X."})
    client.post("/api/runs", json={"user_request": "Compare A and B."})

    runs = client.get("/api/runs").json()["runs"]
    assert len(runs) == 2
    assert {r["route"] for r in runs} == {"research", "comparison"}
    assert all(r["status"] == "completed" for r in runs)
    assert all("request_preview" in r for r in runs)


def test_get_run_returns_run_and_ordered_events(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    run_id = rig.client.post(
        "/api/runs", json={"user_request": "Research X."}
    ).json()["run_id"]

    detail = rig.client.get(f"/api/runs/{run_id}").json()
    assert detail["run_id"] == run_id
    assert detail["result"]["summary"] == "s"
    ets = [e["event_type"] for e in detail["events"]]
    assert ets == [
        "run.started",
        "route.selected",
        "specialist.started",
        "specialist.completed",
        "run.completed",
    ]
    stamps = [e["timestamp"] for e in detail["events"]]
    assert stamps == sorted(stamps)


def test_unknown_run_returns_404(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    resp = rig.client.get("/api/runs/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error_type"] == "RunNotFound"


# --------------------------------------------------------------------------- #
# Demo frontend surface
# --------------------------------------------------------------------------- #
def test_index_page_has_demo_scaffolding(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    html = rig.client.get("/").text
    for needle in (
        "Research Agent",
        "Comparison Agent",
        "Brief Agent",
        'data-example="comparison"',
        "Technical details",
        "at most two LLM calls",
    ):
        assert needle in html


def test_health_reports_safe_config_only(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.RESEARCH), research=[_research()])
    health = rig.client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["max_llm_calls"] == 2
    assert health["persistence_enabled"] is True  # SQLite repo in this rig
    assert "api_key" not in str(health).lower()
    assert "sk-ant" not in str(health)


def test_brief_route_result_exposes_skill_and_no_search(tmp_path) -> None:
    rig = make_rig(tmp_path, _routing(AgentRoute.BRIEF), brief=[_brief()])
    body = rig.client.post(
        "/api/runs",
        json={"user_request": "Make a brief.", "provided_context": "material"},
    ).json()
    assert body["selected_skill"] == "executive-brief"
    assert body["search_used"] is False
    assert "search.started" not in [e["event_type"] for e in body["events"]]
    assert body["llm_calls"] == 2
