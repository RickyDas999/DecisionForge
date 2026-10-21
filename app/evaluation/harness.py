"""Run the golden set end to end through the real pipeline and score it.

Each case goes through :class:`DecisionForgeService` exactly as a web request
would (routing, optional search, one specialist, metering), so the eval measures
the system, not an agent in isolation. The provider decides what that costs:

* ``DemoModelProvider`` — offline canned answers; validates the harness ($0).
* ``ReplayModelProvider`` in ``replay`` mode — recorded real answers ($0).
* a live provider — real answers, capped per run and by the lifetime limit.
"""

from __future__ import annotations

import json
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.evaluation.calibration import CalibrationPoint, summarize
from app.evaluation.golden import GoldenCase
from app.evaluation.metrics import METRICS, Metric, PipelineOutcome
from app.models.dispatch import DispatchRequest
from app.models.persistence import EventType, ExecutionEvent
from app.models.routing import AgentRoute
from app.persistence.null import NullRunRepository
from app.providers.model import ModelProvider
from app.providers.usage import RunBudget
from app.runtime import create_dispatcher
from app.service import DecisionForgeService
from app.skills.base import SkillRegistry
from app.tools.search import SearchProvider


class _CapturingRepository(NullRunRepository):
    """Stores nothing durable but keeps events, so failed runs still report cost."""

    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    def append_event(self, event: ExecutionEvent) -> None:
        self.events.append(event)


@dataclass(frozen=True)
class CaseResult:
    case: GoldenCase
    outcome: PipelineOutcome
    scores: dict[str, float | None]


@dataclass
class EvalRun:
    label: str
    results: list[CaseResult]
    metric_names: list[str]
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def metric_summary(self) -> dict[str, dict[str, float | int | None]]:
        """Per metric: mean over the cases it applies to, and how many that is."""
        summary: dict[str, dict[str, float | int | None]] = {}
        for name in self.metric_names:
            values = [r.scores[name] for r in self.results if r.scores.get(name) is not None]
            summary[name] = {
                "mean": round(statistics.fmean(values), 4) if values else None,
                "n": len(values),
            }
        return summary

    def calibration_points(self) -> list[CalibrationPoint]:
        """Confidence vs. correctness for cases with a clear-cut right answer."""
        points = []
        for r in self.results:
            correct = r.scores.get("recommendation_match")
            report = (r.outcome.result or {}).get("decision_report")
            if correct is None or not report:
                continue
            points.append(CalibrationPoint(
                case_id=r.case.id,
                confidence=float(report["win_probability"]),
                correct=correct == 1.0,
            ))
        return points

    def calibration(self) -> dict[str, Any]:
        return summarize(self.calibration_points())

    def totals(self) -> dict[str, Any]:
        outs = [r.outcome for r in self.results]
        latencies = [o.latency_ms for o in outs]
        return {
            "cases": len(outs),
            "errors": sum(1 for o in outs if o.error),
            "llm_calls": sum(o.llm_calls for o in outs),
            "cost_usd": round(sum(o.cost_usd for o in outs), 6),
            "list_cost_usd": round(sum(o.list_cost_usd for o in outs), 6),
            "mean_list_cost_per_case_usd": round(
                statistics.fmean(o.list_cost_usd for o in outs), 6
            ) if outs else 0.0,
            "p50_latency_ms": round(statistics.median(latencies), 1) if latencies else 0.0,
        }


def _usage_from(events: list[ExecutionEvent]) -> dict[str, Any]:
    for event in reversed(events):
        if event.event_type in (EventType.RUN_COMPLETED, EventType.RUN_FAILED):
            return event.metadata.get("usage") or {}
    return {}


async def run_case(
    service: DecisionForgeService, repo: _CapturingRepository, case: GoldenCase
) -> PipelineOutcome:
    repo.events.clear()
    request = DispatchRequest(user_request=case.request, provided_context=case.provided_context)
    start = time.perf_counter()
    route: AgentRoute | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    try:
        outcome = await service.run(request)
        route = outcome.record.route
        result = _result_payload(outcome.record.result_json)
    except Exception as exc:  # one failing case must not stop the eval
        error = f"{type(exc).__name__}: {exc}"
        routed = [e for e in repo.events if e.event_type is EventType.ROUTE_SELECTED]
        if routed:
            route = AgentRoute(routed[0].metadata["route"])
    latency_ms = (time.perf_counter() - start) * 1000
    usage = _usage_from(repo.events)
    return PipelineOutcome(
        route=route,
        result=result,
        error=error,
        cost_usd=float(usage.get("cost_usd", 0.0)),
        list_cost_usd=float(usage.get("list_cost_usd", 0.0)),
        llm_calls=int(usage.get("calls", 0)),
        latency_ms=latency_ms,
    )


def _result_payload(result_json: str | None) -> dict[str, Any] | None:
    if not result_json:
        return None
    data = json.loads(result_json)
    return data.get("result") if isinstance(data, dict) else None


async def run_eval(
    cases: Sequence[GoldenCase],
    provider: ModelProvider,
    *,
    label: str,
    search_provider: SearchProvider | None = None,
    skill_registry: SkillRegistry | None = None,
    run_budget: RunBudget | None = None,
    metrics: Sequence[Metric] = METRICS,
    decision_engine: bool = True,
    adaptive_samples: bool = True,
) -> EvalRun:
    """Run ``cases`` sequentially (no parallel model calls) and score each."""
    repo = _CapturingRepository()
    service = DecisionForgeService(
        create_dispatcher(
            provider,
            skill_registry,
            search_provider,
            decision_engine=decision_engine,
            adaptive_samples=adaptive_samples,
        ),
        repo,
        run_budget=run_budget,
    )
    results: list[CaseResult] = []
    for case in cases:
        outcome = await run_case(service, repo, case)
        scores = {m.name: m.score(case, outcome) for m in metrics}
        results.append(CaseResult(case=case, outcome=outcome, scores=scores))
    return EvalRun(label=label, results=results, metric_names=[m.name for m in metrics])
