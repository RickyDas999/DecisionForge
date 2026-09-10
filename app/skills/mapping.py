"""Static, deterministic route -> skill mapping.

The orchestrator has already made the semantic routing decision, so the relevant
skill is fixed by the route. No LLM is involved in skill selection.
"""

from __future__ import annotations

from app.models.routing import AgentRoute

ROUTE_SKILLS: dict[AgentRoute, str] = {
    AgentRoute.RESEARCH: "research",
    AgentRoute.COMPARISON: "comparison",
    AgentRoute.BRIEF: "executive-brief",
}


def skill_for_route(route: AgentRoute) -> str:
    """Return the skill name for ``route`` (raises ``KeyError`` on an unknown route)."""
    return ROUTE_SKILLS[route]
