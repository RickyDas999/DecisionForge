"""Tool contracts.

Agents may later be given tools (web search, HTTP fetch, ...). Phase 0 defines the
contract only; no concrete tool exists.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Uniform result envelope returned by every tool."""

    success: bool
    data: Any | None = None
    error: str | None = None


class BaseTool(ABC):
    """Abstract contract for a callable tool."""

    #: Stable identifier used when exposing the tool to an agent.
    name: str
    #: Short human-readable description of what the tool does.
    description: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Run the tool and return a :class:`ToolResult`."""
        raise NotImplementedError
