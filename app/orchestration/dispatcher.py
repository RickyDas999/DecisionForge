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

An optional :class:`DispatchObserver` is notified at deterministic points; it is
observational only and never changes control flow or issues model calls.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest, DispatchResult
from app.models.routing import AgentRoute, RoutingInput
from app.models.specialists import BriefInput, ComparisonInput, ResearchInput
from app.orchestration.exceptions import MissingBriefContextError, UnexpectedRouteError
from app.orchestration.observer import NULL_OBSERVER, DispatchObserver
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
        *,
        observer: DispatchObserver | None = None,
    ) -> DispatchResult:
        obs = observer or NULL_OBSERVER

        # 1. Semantic routing — exactly one orchestrator call.
        routing_decision = await self.orchestrator.run(
            RoutingInput(user_request=request.user_request),
            context,
        )
        route = routing_decision.route
        obs.on_routing_completed(routing_decision)

        # 2. Deterministic specialist selection — exactly one specialist call.
        if route is AgentRoute.RESEARCH:
            agent_input: Any = ResearchInput(
                user_request=request.user_request,
                provided_context=await self._context_for(route, request, obs),
            )
            result = await self._run_specialist(
                self.research_agent, agent_input, route, context, obs
            )
        elif route is AgentRoute.COMPARISON:
            agent_input = ComparisonInput(
                user_request=request.user_request,
                provided_context=await self._context_for(route, request, obs),
            )
            result = await self._run_specialist(
                self.comparison_agent, agent_input, route, context, obs
            )
        elif route is AgentRoute.BRIEF:
            # BRIEF never searches. Context is required and used verbatim.
            if request.provided_context is None or not request.provided_context.strip():
                raise MissingBriefContextError()
            agent_input = BriefInput(
                user_request=request.user_request,
                provided_context=request.provided_context,
            )
            result = await self._run_specialist(
                self.brief_agent, agent_input, route, context, obs
            )
        else:  # pragma: no cover - AgentRoute is exhaustive
            raise UnexpectedRouteError(route)

        # 3. Deterministic result assembly.
        return DispatchResult(
            route=route,
            routing_reasoning=routing_decision.reasoning,
            result=result,
        )

    async def _run_specialist(
        self,
        agent: ResearchAgent | ComparisonAgent | BriefAgent,
        agent_input: Any,
        route: AgentRoute,
        context: AgentRuntimeContext,
        obs: DispatchObserver,
    ) -> Any:
        obs.on_specialist_started(route)
        result = await agent.run(agent_input, context)
        obs.on_specialist_completed(route)
        return result

    async def _context_for(
        self,
        route: AgentRoute,
        request: DispatchRequest,
        obs: DispatchObserver,
    ) -> str | None:
        """User context, optionally merged with one deterministic search pass.

        No search provider, or a non-search route -> the request's context is
        returned unchanged. A search failure propagates: the request stops with
        no specialist call, no retry, and no fallback.
        """
        if self.search_provider is None or not search_enabled_for_route(route):
            return request.provided_context

        obs.on_search_started(request.user_request)
        response = await self.search_provider.search(request.user_request)
        obs.on_search_completed(response)
        return combine_contexts(
            request.provided_context, build_search_context(response)
        )
