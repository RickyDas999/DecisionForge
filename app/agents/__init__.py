"""Agent contracts and the OrchestratorAgent.

The three specialist agents (research, comparison, brief) are not implemented yet.
"""

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.agents.orchestrator import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    OrchestratorAgent,
    build_user_prompt,
)

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "AgentRuntimeContext",
    "BaseAgent",
    "OrchestratorAgent",
    "build_user_prompt",
]
