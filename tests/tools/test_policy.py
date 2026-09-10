"""The route -> search policy is static: Research/Comparison yes, Brief no."""

from __future__ import annotations

from app.models.routing import AgentRoute
from app.tools.policy import SEARCH_ENABLED_ROUTES, search_enabled_for_route


def test_research_and_comparison_are_search_eligible() -> None:
    assert search_enabled_for_route(AgentRoute.RESEARCH) is True
    assert search_enabled_for_route(AgentRoute.COMPARISON) is True


def test_brief_is_never_search_eligible() -> None:
    assert search_enabled_for_route(AgentRoute.BRIEF) is False


def test_exactly_two_routes_enabled() -> None:
    assert SEARCH_ENABLED_ROUTES == frozenset(
        {AgentRoute.RESEARCH, AgentRoute.COMPARISON}
    )
