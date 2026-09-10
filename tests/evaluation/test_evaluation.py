"""Tests for the deterministic evaluation plumbing. Offline; no network."""

from __future__ import annotations

import asyncio

from app.evaluation.cases import ROUTING_CASES, EvaluationCase
from app.evaluation.contracts import (
    check_brief_response,
    check_comparison_response,
    check_research_response,
)
from app.evaluation.runner import evaluate_routing, evaluate_routing_sync
from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.providers.mock import MockModelProvider


# --------------------------------------------------------------------------- #
# Cases
# --------------------------------------------------------------------------- #
def test_cases_cover_all_three_routes_evenly() -> None:
    by_route: dict[AgentRoute, int] = {r: 0 for r in AgentRoute}
    for case in ROUTING_CASES:
        by_route[case.expected_route] += 1
    assert by_route == {r: 3 for r in AgentRoute}
    assert all(
        (c.provided_context is not None) == (c.expected_route is AgentRoute.BRIEF)
        for c in ROUTING_CASES
    )


# --------------------------------------------------------------------------- #
# Routing runner
# --------------------------------------------------------------------------- #
def test_default_routing_eval_is_offline_and_reports_accuracy() -> None:
    report = evaluate_routing_sync()  # DemoModelProvider, no network
    assert report.total == len(ROUTING_CASES)
    assert report.passed + report.failed == report.total
    assert 0.0 <= report.accuracy <= 1.0
    # the demo router should get every representative prompt right
    assert report.accuracy == 1.0


def test_runner_detects_failures_with_a_wrong_provider() -> None:
    # a provider that always routes RESEARCH -> comparison/brief cases fail
    always_research = MockModelProvider(
        structured_responses=[
            RoutingDecision(route=AgentRoute.RESEARCH, reasoning="forced")
            for _ in ROUTING_CASES
        ]
    )
    report = asyncio.run(evaluate_routing(ROUTING_CASES, provider=always_research))
    assert report.passed == 3  # only the 3 genuine research cases
    assert report.failed == 6
    assert report.accuracy == 3 / 9


def test_runner_accepts_a_custom_case_list() -> None:
    cases = [
        EvaluationCase("c", "Compare X and Y for our team.", AgentRoute.COMPARISON)
    ]
    report = evaluate_routing_sync(cases)
    assert report.total == 1 and report.passed == 1


# --------------------------------------------------------------------------- #
# Contract checks
# --------------------------------------------------------------------------- #
def test_valid_responses_pass_their_contracts() -> None:
    assert check_research_response(
        ResearchResponse(
            topic="t",
            summary="a real summary",
            key_findings=["f"],
            sources=["https://example.com/x"],
        )
    ) == []
    assert check_comparison_response(
        ComparisonResponse(
            question="q",
            options=[ComparisonOption(name="A")],
            recommendation="Pick A",
            rationale="because",
            confidence=0.6,
        )
    ) == []
    assert check_brief_response(
        BriefResponse(title="T", executive_summary="S", key_points=["k"])
    ) == []


def test_research_contract_flags_empty_summary_no_findings_and_bad_sources() -> None:
    problems = check_research_response(
        ResearchResponse(topic="t", summary="   ", key_findings=[], sources=["nope"])
    )
    assert any("summary" in p for p in problems)
    assert any("key findings" in p for p in problems)
    assert any("URL" in p for p in problems)


def test_comparison_contract_flags_missing_pieces() -> None:
    problems = check_comparison_response(
        ComparisonResponse(
            question="q", options=[], recommendation="  ", rationale="  ", confidence=0.5
        )
    )
    assert any("options" in p for p in problems)
    assert any("recommendation" in p for p in problems)
    assert any("rationale" in p for p in problems)


def test_brief_contract_flags_missing_pieces() -> None:
    problems = check_brief_response(
        BriefResponse(title="  ", executive_summary="  ", key_points=[])
    )
    assert len(problems) == 3
