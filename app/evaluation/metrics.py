"""Deterministic per-case metrics.

Each metric maps ``(case, outcome)`` to a score in ``[0, 1]``, or ``None`` when it
does not apply (e.g. option recall on a research case, or anything on a failed
run). Later slices append metrics (groundedness, calibration, injection
resistance) to :data:`METRICS`; the harness and report pick them up unchanged.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.evaluation.contracts import (
    check_brief_response,
    check_comparison_response,
    check_research_response,
)
from app.evaluation.golden import GoldenCase
from app.models.routing import AgentRoute
from app.models.specialists import BriefResponse, ComparisonResponse, ResearchResponse

_CONTRACTS: dict[AgentRoute, tuple[type, Callable[[Any], list[str]]]] = {
    AgentRoute.RESEARCH: (ResearchResponse, check_research_response),
    AgentRoute.COMPARISON: (ComparisonResponse, check_comparison_response),
    AgentRoute.BRIEF: (BriefResponse, check_brief_response),
}


@dataclass(frozen=True)
class PipelineOutcome:
    """What one pipeline run produced for one case."""

    route: AgentRoute | None
    #: The specialist's structured result as plain JSON data.
    result: dict[str, Any] | None
    error: str | None
    cost_usd: float
    list_cost_usd: float
    llm_calls: int
    latency_ms: float


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    score: Callable[[GoldenCase, PipelineOutcome], float | None]


def _text(value: Any) -> str:
    """Lower-cased flat text of a result, for substring matching."""
    return json.dumps(value, ensure_ascii=False).lower()


def route_accuracy(case: GoldenCase, out: PipelineOutcome) -> float | None:
    if out.route is None:
        return 0.0
    return 1.0 if out.route is case.expected_route else 0.0


def contract_pass(case: GoldenCase, out: PipelineOutcome) -> float | None:
    """The result validates and meets its route's semantic minimums."""
    if out.result is None or out.route is None:
        return 0.0
    model, check = _CONTRACTS[out.route]
    try:
        parsed = model.model_validate(out.result)
    except ValueError:
        return 0.0
    return 0.0 if check(parsed) else 1.0


def option_recall(case: GoldenCase, out: PipelineOutcome) -> float | None:
    """Fraction of the expected options the result actually compares."""
    if not case.expected_options:
        return None
    if out.result is None:
        return 0.0
    names = out.result.get("options")
    haystack = _text(names if names else out.result)
    found = sum(1 for opt in case.expected_options if opt.lower() in haystack)
    return found / len(case.expected_options)


def recommendation_match(case: GoldenCase, out: PipelineOutcome) -> float | None:
    """The recommendation names an acceptable option (only where one is clear)."""
    if not case.acceptable_recommendations:
        return None
    if out.result is None:
        return 0.0
    rec = str(out.result.get("recommendation") or "").lower()
    return 1.0 if any(a.lower() in rec for a in case.acceptable_recommendations) else 0.0


def rubric_coverage(case: GoldenCase, out: PipelineOutcome) -> float | None:
    """Fraction of rubric terms the answer mentions anywhere."""
    if not case.must_mention:
        return None
    if out.result is None:
        return 0.0
    text = _text(out.result)
    return sum(1 for term in case.must_mention if term.lower() in text) / len(case.must_mention)


METRICS: list[Metric] = [
    Metric("route_accuracy", "routed to the expected specialist", route_accuracy),
    Metric("contract_pass", "result validates and meets its contract", contract_pass),
    Metric("option_recall", "expected options compared", option_recall),
    Metric("recommendation_match", "recommendation is an acceptable option", recommendation_match),
    Metric("rubric_coverage", "rubric terms mentioned", rubric_coverage),
]
