"""Agent contracts, the OrchestratorAgent, and the three leaf specialist agents.

Delegation graph:

    OrchestratorAgent
    /       |        \\
Research  Comparison  Brief   (leaf agents — never delegate)

The deterministic dispatcher that turns a ``RoutingDecision`` into exactly one
specialist call is not implemented yet.
"""

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.agents.brief import BRIEF_SYSTEM_PROMPT, BriefAgent
from app.agents.comparison import COMPARISON_SYSTEM_PROMPT, ComparisonAgent
from app.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    OrchestratorAgent,
    build_user_prompt,
)
from app.agents.research import RESEARCH_SYSTEM_PROMPT, ResearchAgent

__all__ = [
    "BRIEF_SYSTEM_PROMPT",
    "COMPARISON_SYSTEM_PROMPT",
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "RESEARCH_SYSTEM_PROMPT",
    "AgentRuntimeContext",
    "BaseAgent",
    "BriefAgent",
    "ComparisonAgent",
    "OrchestratorAgent",
    "ResearchAgent",
    "build_user_prompt",
]
