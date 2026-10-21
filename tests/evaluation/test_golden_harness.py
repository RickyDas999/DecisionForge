"""Tests for the golden set, the deterministic metrics, the harness, and reports."""

from __future__ import annotations

import asyncio

import pytest

from app.evaluation.golden import GoldenCase, load_golden_set
from app.evaluation.harness import run_eval
from app.evaluation.metrics import (
    PipelineOutcome,
    contract_pass,
    option_recall,
    recommendation_match,
    route_accuracy,
    rubric_coverage,
)
from app.evaluation.report import load_report, save_report, to_markdown
from app.models.routing import AgentRoute
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider

CASE = GoldenCase(
    id="c",
    request="Postgres or Mongo?",
    expected_route=AgentRoute.COMPARISON,
    expected_options=["PostgreSQL", "MongoDB"],
    acceptable_recommendations=["PostgreSQL"],
    must_mention=["schema", "transaction"],
)


def _outcome(result: dict | None, route: AgentRoute | None = AgentRoute.COMPARISON) -> PipelineOutcome:
    return PipelineOutcome(route=route, result=result, error=None, cost_usd=0.0,
                           list_cost_usd=0.0, llm_calls=2, latency_ms=1.0)


GOOD = {
    "question": "Postgres or Mongo?",
    "options": [{"name": "PostgreSQL", "advantages": ["transactions"], "disadvantages": []},
                {"name": "MongoDB", "advantages": ["flexible schema"], "disadvantages": []}],
    "recommendation": "PostgreSQL",
    "rationale": "relational fit",
    "confidence": 0.7,
}


def test_golden_set_loads_and_covers_every_route() -> None:
    cases = load_golden_set()
    assert len(cases) >= 30
    assert {c.expected_route for c in cases} == set(AgentRoute)
    assert all(c.provided_context for c in cases if c.expected_route is AgentRoute.BRIEF)


def test_metrics_on_a_good_comparison() -> None:
    out = _outcome(GOOD)
    assert route_accuracy(CASE, out) == 1.0
    assert contract_pass(CASE, out) == 1.0
    assert option_recall(CASE, out) == 1.0
    assert recommendation_match(CASE, out) == 1.0
    assert rubric_coverage(CASE, out) == 1.0


def test_metrics_on_partial_and_failed_results() -> None:
    partial = dict(GOOD, options=[GOOD["options"][0]], recommendation="MongoDB")
    out = _outcome(partial)
    assert option_recall(CASE, out) == 0.5
    assert recommendation_match(CASE, out) == 0.0

    failed = _outcome(None, route=None)
    assert route_accuracy(CASE, failed) == 0.0
    assert contract_pass(CASE, failed) == 0.0
    assert rubric_coverage(CASE, failed) == 0.0


def test_inapplicable_metrics_return_none() -> None:
    research = GoldenCase(id="r", request="x", expected_route=AgentRoute.RESEARCH)
    out = _outcome({"topic": "t", "summary": "s"}, route=AgentRoute.RESEARCH)
    assert option_recall(research, out) is None
    assert recommendation_match(research, out) is None
    assert rubric_coverage(research, out) is None


def test_contract_fails_on_wrong_shape() -> None:
    assert contract_pass(CASE, _outcome({"unexpected": True})) == 0.0


def test_harness_runs_golden_set_offline_and_reports(tmp_path) -> None:
    cases = load_golden_set()
    run = asyncio.run(run_eval(cases, DemoModelProvider(), label="t",
                               search_provider=DemoSearchProvider()))
    assert len(run.results) == len(cases)
    totals = run.totals()
    assert totals["cost_usd"] == 0.0
    assert 0 < totals["mean_list_cost_per_case_usd"] < 0.002
    summary = run.metric_summary()
    assert summary["option_recall"]["n"] == sum(1 for c in cases if c.expected_options)
    # A failing case (e.g. a brief routed without context) is scored, not raised.
    assert all(r.outcome.error is None or r.scores["contract_pass"] == 0.0 for r in run.results)

    json_path, md_path = save_report(run, tmp_path)
    again = asyncio.run(run_eval(cases[:3], DemoModelProvider(), label="t2"))
    md = to_markdown(again, baseline=load_report(json_path))
    assert "Δ vs t" in md
    assert md_path.read_text().startswith("# Eval report: t")


def test_failed_case_keeps_route_and_cost() -> None:
    # A research-worded request with "summarize" is routed to BRIEF by the demo
    # router and then fails for lack of context; the harness still records it.
    case = GoldenCase(id="z", request="Summarize what zero-trust networking means.",
                      expected_route=AgentRoute.RESEARCH)
    run = asyncio.run(run_eval([case], DemoModelProvider(), label="z"))
    out = run.results[0].outcome
    assert out.error and "MissingBriefContext" in out.error
    assert out.route is AgentRoute.BRIEF
    assert out.llm_calls == 1
    assert out.list_cost_usd > 0


@pytest.mark.parametrize("bad", ['{"version":1,"cases":[{"id":"a","request":"x","expected_route":"research"},'
                                 '{"id":"a","request":"y","expected_route":"research"}]}'])
def test_duplicate_ids_rejected(tmp_path, bad: str) -> None:
    path = tmp_path / "g.json"
    path.write_text(bad)
    with pytest.raises(ValueError):
        load_golden_set(path)


def test_recommendation_uses_engine_winner_not_text() -> None:
    tossup = dict(GOOD, recommendation="No clear winner: PostgreSQL vs MongoDB",
                  decision_report={"winner": "MongoDB", "total_scores": 4, "gaps": []})
    assert recommendation_match(CASE, _outcome(tossup)) == 0.0


def test_decision_completeness() -> None:
    from app.evaluation.metrics import decision_completeness

    partial = dict(GOOD, decision_report={"winner": "x", "total_scores": 3, "gaps": ["a / b"]})
    assert decision_completeness(CASE, _outcome(partial)) == 0.75
    assert decision_completeness(CASE, _outcome(GOOD)) is None


def test_grounding_metrics() -> None:
    from app.evaluation.metrics import citation_precision, groundedness

    research = GoldenCase(id="r", request="x", expected_route=AgentRoute.RESEARCH)
    grounded = _outcome({"topic": "t", "summary": "s",
                         "grounding": {"groundedness": 0.5, "citation_precision": 0.75}},
                        route=AgentRoute.RESEARCH)
    assert groundedness(research, grounded) == 0.5
    assert citation_precision(research, grounded) == 0.75
    uncited = _outcome({"grounding": {"groundedness": 0.0, "citation_precision": None}},
                       route=AgentRoute.RESEARCH)
    assert citation_precision(research, uncited) is None
    assert groundedness(CASE, _outcome(GOOD)) is None  # comparisons have no findings


def test_pick_balanced_covers_every_route_deterministically() -> None:
    from app.evaluation.golden import pick_balanced

    cases = load_golden_set()
    picked = pick_balanced(cases)
    routes = [c.expected_route for c in picked]
    assert routes.count(AgentRoute.COMPARISON) == 2
    assert routes.count(AgentRoute.RESEARCH) == 2
    assert routes.count(AgentRoute.BRIEF) == 1
    assert all(c.acceptable_recommendations for c in picked
               if c.expected_route is AgentRoute.COMPARISON)
    assert pick_balanced(cases) == picked
    assert pick_balanced(cases, {AgentRoute.BRIEF: 3}) == \
        [c for c in cases if c.expected_route is AgentRoute.BRIEF][:3]
