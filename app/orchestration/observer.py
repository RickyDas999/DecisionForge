"""A tiny, purely-observational hook for the dispatcher.

The dispatcher calls these methods at deterministic points so an outer layer
(e.g. persistence) can record what happened. Observers do **no** semantic work,
make **no** model calls, and cannot change control flow. The default
implementation is a no-op.
"""

from __future__ import annotations

from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse


class DispatchObserver:
    """No-op base. Override the hooks you care about."""

    def on_routing_completed(self, decision: RoutingDecision) -> None:
        """Called once, right after the orchestrator returns."""

    def on_search_started(self, query: str) -> None:
        """Called before a search request (RESEARCH / COMPARISON only)."""

    def on_search_completed(self, response: SearchResponse) -> None:
        """Called after a successful search request."""

    def on_specialist_started(self, route: AgentRoute) -> None:
        """Called just before the single specialist model call."""

    def on_specialist_completed(self, route: AgentRoute) -> None:
        """Called just after the specialist returns."""


#: Shared instance used when no observer is supplied.
NULL_OBSERVER = DispatchObserver()
