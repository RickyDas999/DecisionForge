"""The route -> skill mapping is static and has exactly three entries."""

from __future__ import annotations

from app.models.routing import AgentRoute
from app.skills.mapping import ROUTE_SKILLS, skill_for_route


def test_mapping_has_exactly_three_entries() -> None:
    assert set(ROUTE_SKILLS) == set(AgentRoute)
    assert len(ROUTE_SKILLS) == 3


def test_each_route_maps_to_its_skill() -> None:
    assert skill_for_route(AgentRoute.RESEARCH) == "research"
    assert skill_for_route(AgentRoute.COMPARISON) == "comparison"
    assert skill_for_route(AgentRoute.BRIEF) == "executive-brief"


def test_no_legacy_route_names() -> None:
    assert set(ROUTE_SKILLS.values()) == {"research", "comparison", "executive-brief"}
    for banned in ("planner", "judge", "analysis", "writer", "risk", "alternatives"):
        assert banned not in ROUTE_SKILLS.values()
