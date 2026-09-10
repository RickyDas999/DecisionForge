"""Tiny construction helper: wire the four agents into a dispatcher.

This is not a dependency-injection framework — just the one line of assembly that
demos and (later) an application entry point need. Tests that want to count calls
per agent construct agents with separate providers instead of using this helper.
"""

from __future__ import annotations

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.providers.model import ModelProvider


def create_dispatcher(model_provider: ModelProvider) -> DecisionForgeDispatcher:
    """Build a dispatcher whose four agents all share ``model_provider``."""
    return DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(model_provider),
        research_agent=ResearchAgent(model_provider),
        comparison_agent=ComparisonAgent(model_provider),
        brief_agent=BriefAgent(model_provider),
    )
