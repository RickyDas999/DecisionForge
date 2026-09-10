"""Run routing cases through the OrchestratorAgent and score them."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass

from app.agents.base import AgentRuntimeContext
from app.agents.orchestrator import OrchestratorAgent
from app.evaluation.cases import ROUTING_CASES, EvaluationCase
from app.models.routing import AgentRoute, RoutingInput
from app.providers.model import ModelProvider
from app.web.demo_provider import DemoModelProvider


@dataclass(frozen=True)
class CaseOutcome:
    case: EvaluationCase
    predicted_route: AgentRoute
    passed: bool


@dataclass
class EvalReport:
    outcomes: list[CaseOutcome]

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outcomes if o.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


async def evaluate_routing(
    cases: Sequence[EvaluationCase] = ROUTING_CASES,
    *,
    provider: ModelProvider | None = None,
) -> EvalReport:
    """Route every case and compare to its expectation.

    Default provider is the offline ``DemoModelProvider`` — zero network. Pass a
    real provider (e.g. ``AnthropicModelProvider``) to measure actual routing.
    """
    agent = OrchestratorAgent(provider or DemoModelProvider())
    context = AgentRuntimeContext(run_id="routing-eval")
    outcomes: list[CaseOutcome] = []
    for case in cases:
        decision = await agent.run(
            RoutingInput(user_request=case.user_request), context
        )
        outcomes.append(
            CaseOutcome(
                case=case,
                predicted_route=decision.route,
                passed=decision.route is case.expected_route,
            )
        )
    return EvalReport(outcomes)


def evaluate_routing_sync(
    cases: Sequence[EvaluationCase] = ROUTING_CASES,
    *,
    provider: ModelProvider | None = None,
) -> EvalReport:
    return asyncio.run(evaluate_routing(cases, provider=provider))
