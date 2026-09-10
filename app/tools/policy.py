"""Static, deterministic policy for whether search runs on a route.

Research and Comparison benefit from current external evidence. Brief is a pure
transformation of user-supplied material and must never search automatically.
No LLM is consulted.
"""

from __future__ import annotations

from app.models.routing import AgentRoute

SEARCH_ENABLED_ROUTES: frozenset[AgentRoute] = frozenset(
    {AgentRoute.RESEARCH, AgentRoute.COMPARISON}
)


def search_enabled_for_route(route: AgentRoute) -> bool:
    """True for RESEARCH and COMPARISON; False for BRIEF."""
    return route in SEARCH_ENABLED_ROUTES
