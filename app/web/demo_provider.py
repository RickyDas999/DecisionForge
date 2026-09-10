"""A deterministic, offline stand-in for Claude, used only by the web demo.

The default web app cannot use ``MockModelProvider`` directly (that needs one
queued response per call, keyed to a route we don't know ahead of time). This
provider returns plausible canned structured output based on the requested
``response_model`` and a light keyword read of the request.

It is **not** an LLM and **not** the real orchestrator. The architecture is
unchanged: OrchestratorAgent still calls ``generate_structured(RoutingDecision)``
(call #1) and the selected specialist calls ``generate_structured(...)`` (call
#2) — exactly two model calls. This class just makes those two calls return
demo data.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.providers.model import ModelProvider
from app.tools.search import MockSearchProvider

_COMPARISON_HINTS = (" vs ", " vs.", "compare ", " versus ", " or ")
_BRIEF_HINTS = ("brief", "memo", "summari", "leadership", "executive")


def _route_for(text: str) -> RoutingDecision:
    lowered = f" {text.lower()} "
    if any(hint in lowered for hint in _COMPARISON_HINTS):
        return RoutingDecision(
            route=AgentRoute.COMPARISON,
            reasoning="Demo router: the request compares alternatives.",
        )
    if any(hint in lowered for hint in _BRIEF_HINTS):
        return RoutingDecision(
            route=AgentRoute.BRIEF,
            reasoning="Demo router: the request asks to transform supplied material.",
        )
    return RoutingDecision(
        route=AgentRoute.RESEARCH,
        reasoning="Demo router: the request asks to investigate a topic.",
    )


class DemoModelProvider(ModelProvider):
    """Offline canned-response provider for the local web demo."""

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("DemoModelProvider only supports structured output")

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        if response_model is RoutingDecision:
            return _route_for(user_prompt)

        if response_model is ResearchResponse:
            return ResearchResponse(
                topic="Demo research topic",
                summary=(
                    "This is a deterministic demo response. No live or web research "
                    "was performed; it is generated offline by DemoModelProvider."
                ),
                key_findings=[
                    "Demo finding 1 — replace by configuring a real model provider.",
                    "Demo finding 2 — the request text was received and routed.",
                ],
                limitations=[
                    "Offline demo output; not based on real evidence.",
                    "Configure MODEL_PROVIDER=anthropic for real answers.",
                ],
                sources=[],
            )

        if response_model is ComparisonResponse:
            return ComparisonResponse(
                question="Demo comparison",
                options=[
                    ComparisonOption(
                        name="Option A",
                        advantages=["Demo advantage"],
                        disadvantages=["Demo disadvantage"],
                    ),
                    ComparisonOption(
                        name="Option B",
                        advantages=["Demo advantage"],
                        disadvantages=["Demo disadvantage"],
                    ),
                ],
                recommendation="Demo recommendation (offline).",
                rationale="Deterministic demo rationale — not real analysis.",
                important_tradeoffs=["Demo tradeoff"],
                confidence=0.5,
                limitations=["Offline demo output; configure a real provider."],
            )

        if response_model is BriefResponse:
            return BriefResponse(
                title="Demo Executive Brief",
                executive_summary=(
                    "Deterministic demo brief generated offline from the supplied "
                    "context."
                ),
                key_points=["Demo key point 1", "Demo key point 2"],
                recommendation=None,
                action_items=["Demo action item"],
            )

        raise NotImplementedError(  # pragma: no cover
            f"DemoModelProvider has no canned response for {response_model.__name__}"
        )


class DemoSearchProvider(MockSearchProvider):
    """Offline canned search results, so the demo shows the search step running.

    No network. Used by the demo web app for RESEARCH / COMPARISON requests.
    """

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        self.responses = [
            SearchResponse(
                query=query,
                results=[
                    SearchResult(
                        title="Illustrative source A (offline demo)",
                        url="https://example.com/a",
                        snippet=(
                            "A short deterministic snippet. Set "
                            "SEARCH_PROVIDER=duckduckgo + install the '[search]' "
                            "extra for real web results."
                        ),
                        source="example.com",
                    ),
                    SearchResult(
                        title="Illustrative source B (offline demo)",
                        url="https://example.com/b",
                        snippet="A second deterministic snippet for the demo.",
                        source="example.com",
                    ),
                ],
            )
        ]
        return await super().search(query, max_results=max_results)
