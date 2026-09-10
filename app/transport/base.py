"""Transport contract.

Keeps future orchestration independent of whether an agent runs in-process or over
HTTP. Concrete clients (LocalAgentClient, HttpAgentClient) are later phases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class AgentClient(ABC):
    """Abstract transport for invoking a named agent with a typed payload."""

    @abstractmethod
    async def invoke(self, agent_name: str, payload: BaseModel) -> BaseModel:
        """Invoke ``agent_name`` with ``payload`` and return its typed response."""
        raise NotImplementedError
