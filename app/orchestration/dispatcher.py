"""The deterministic single-hop dispatcher.

This is the first complete DecisionForge request path:

    DispatchRequest
        -> OrchestratorAgent.run()          (1 LLM call: routing)
        -> exactly one specialist .run()     (1 LLM call: the work)
        -> DispatchResult

Everything except the two ``agent.run()`` calls is plain deterministic Python.
There is no fallback route, no retry, no loop, and no parallelism.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest, DispatchResult
from app.models.routing import AgentRoute, RoutingInput
from app.models.specialists import (
    BriefInput,
    ComparisonInput,
    ResearchInput,
)
from app.orchestration.exceptions import MissingBriefContextError, UnexpectedRouteError


class DecisionForgeDispatcher:
    """Runs one request: orchestrator picks a route, one specialist does the work.

    Agent instances are injected. The dispatcher never constructs agents or
    providers and never reads the environment.
    """

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        research_agent: ResearchAgent,
        comparison_agent: ComparisonAgent,
        brief_agent: BriefAgent,
    ) -> None:
        self.orchestrator = orchestrator
        self.research_agent = research_agent
        self.comparison_agent = comparison_agent
        self.brief_agent = brief_agent

    async def dispatch(
        self,
        request: DispatchRequest,
        context: AgentRuntimeContext,
    ) -> DispatchResult:
        # 1. Semantic routing — exactly one orchestrator call.
        routing_decision = await self.orchestrator.run(
            RoutingInput(user_request=request.user_request),
            context,
        )
        route = routing_decision.route

        # 2. Deterministic specialist selection — exactly one specialist call.
        if route is AgentRoute.RESEARCH:
            result = await self.research_agent.run(
                ResearchInput(
                    user_request=request.user_request,
                    provided_context=request.provided_context,
                ),
                context,
            )
        elif route is AgentRoute.COMPARISON:
            result = await self.comparison_agent.run(
                ComparisonInput(
                    user_request=request.user_request,
                    provided_context=request.provided_context,
                ),
                context,
            )
        elif route is AgentRoute.BRIEF:
            if request.provided_context is None or not request.provided_context.strip():
                # The orchestrator call already happened; we stop here.
                raise MissingBriefContextError()
            result = await self.brief_agent.run(
                BriefInput(
                    user_request=request.user_request,
                    provided_context=request.provided_context,
                ),
                context,
            )
        else:  # pragma: no cover - AgentRoute is exhaustive
            raise UnexpectedRouteError(route)

        # 3. Deterministic result assembly.
        return DispatchResult(
            route=route,
            routing_reasoning=routing_decision.reasoning,
            result=result,
        )
