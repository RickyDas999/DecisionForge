"""Base agent contract.

Phase 0 defines only the abstract shape every LLM-backed agent will implement.
Concrete agents (Planner, Research, Judge, Analysis, Writer) arrive in later phases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

TInput = TypeVar("TInput")
TOutput = TypeVar("TOutput")


@dataclass
class AgentRuntimeContext:
    """Lightweight per-invocation context handed to an agent by the orchestrator.

    Intentionally minimal in Phase 0. Model clients, tools, databases, and skill
    registries are deliberately NOT placed here yet.
    """

    run_id: str
    iteration: int = 0


class BaseAgent(ABC, Generic[TInput, TOutput]):
    """Abstract contract for a single specialized agent.

    An agent receives a typed input and returns a typed output. It performs
    semantic work only; workflow mechanics (sequencing, loops, retries, timeouts)
    are owned by the deterministic orchestrator.
    """

    #: Human-readable identifier, used in events and logs.
    name: str

    @abstractmethod
    async def run(self, task_input: TInput, context: AgentRuntimeContext) -> TOutput:
        """Execute the agent's semantic task and return its typed output."""
        raise NotImplementedError
