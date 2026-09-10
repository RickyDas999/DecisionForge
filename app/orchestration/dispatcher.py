"""The deterministic single-hop dispatcher.

The complete DecisionForge request path:

    DispatchRequest
        -> OrchestratorAgent.run()               (1 LLM call: routing)
        -> [RESEARCH/COMPARISON only] SearchProvider.search()   (0 LLM calls)
        -> exactly one specialist .run()          (1 LLM call: the work)
        -> DispatchResult

Everything except the two ``agent.run()`` calls is plain deterministic Python.
The optional search step adds network I/O but **no** model call. There is no
fallback route, no retry, no loop, and no parallelism.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest, DispatchResult
from app.models.routing import AgentRoute, RoutingInput
from app.models.specialists import BriefInput, ComparisonInput, ResearchInput
from app.orchestration.exceptions import MissingBriefContextError, UnexpectedRouteError
from app.tools.context import build_search_context, combine_contexts
from app.tools.policy import search_enabled_for_route
from app.tools.search import SearchProvider


class DecisionForgeDispatcher:
    """Runs one request: orchestrator picks a route, one specialist does the work.

    Agent instances are injected. The dispatcher never constructs agents or
    providers and never reads the environment. If ``search_provider`` is given,
    the RESEARCH and COMPARISON routes gather external evidence before the
    specialist call; BRIEF never does.
    """

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        research_agent: ResearchAgent,
        comparison_agent: ComparisonAgent,
        brief_agent: BriefAgent,
        search_provider: SearchProvider | None = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.research_agent = research_agent
        self.comparison_agent = comparison_agent
        self.brief_agent = brief_agent
        self.search_provider = search_provider

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
                    provided_context=await self._context_for(route, request),
                ),
                context,
            )
        elif route is AgentRoute.COMPARISON:
            result = await self.comparison_agent.run(
                ComparisonInput(
                    user_request=request.user_request,
                    provided_context=await self._context_for(route, request),
                ),
                context,
            )
        elif route is AgentRoute.BRIEF:
            # BRIEF never searches. Context is required and used verbatim.
            if request.provided_context is None or not request.provided_context.strip():
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

    async def _context_for(
        self, route: AgentRoute, request: DispatchRequest
    ) -> str | None:
        """User context, optionally merged with one deterministic search pass.

        No search provider, or a non-search route -> the request's context is
        returned unchanged. A search failure propagates: the request stops with
        no specialist call, no retry, and no fallback.
        """
        if self.search_provider is None or not search_enabled_for_route(route):
            return request.provided_context

        response = await self.search_provider.search(request.user_request)
        return combine_contexts(
            request.provided_context, build_search_context(response)
        )
