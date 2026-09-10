"""Tiny construction helper: wire the four agents into a dispatcher.

Not a dependency-injection framework — just the one line of assembly that demos
and (later) an application entry point need. Tests that want to count calls per
agent construct agents with separate providers instead of using this helper.

When a ``SkillRegistry`` is supplied, each specialist is built **skill-aware**:
its (and only its) activated ``SKILL.md`` body is injected into its system
prompt. This is deterministic file I/O — no extra model calls.
"""

from __future__ import annotations

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.routing import AgentRoute
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.providers.model import ModelProvider
from app.skills.base import SkillRegistry
from app.skills.local import LocalSkillRegistry
from app.skills.mapping import skill_for_route


def create_dispatcher(
    model_provider: ModelProvider,
    skill_registry: SkillRegistry | None = None,
) -> DecisionForgeDispatcher:
    """Build a dispatcher whose four agents share ``model_provider``.

    If ``skill_registry`` is given, each specialist receives its route's activated
    skill instructions and nothing else.
    """

    def instructions_for(route: AgentRoute) -> str | None:
        if skill_registry is None:
            return None
        return skill_registry.load(skill_for_route(route)).instructions

    return DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(model_provider),
        research_agent=ResearchAgent(
            model_provider, instructions_for(AgentRoute.RESEARCH)
        ),
        comparison_agent=ComparisonAgent(
            model_provider, instructions_for(AgentRoute.COMPARISON)
        ),
        brief_agent=BriefAgent(model_provider, instructions_for(AgentRoute.BRIEF)),
    )


def create_local_skill_registry() -> LocalSkillRegistry:
    """A :class:`LocalSkillRegistry` rooted at the repo's ``skills/`` directory."""
    return LocalSkillRegistry()
