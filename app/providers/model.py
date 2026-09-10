"""Model-provider contract.

Agents depend on this abstraction rather than on any specific LLM vendor. Future
providers (MockProvider, AnthropicProvider, LocalProvider) implement it. Phase 0
ships none of them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class ModelProvider(ABC):
    """Abstract text + structured generation interface."""

    @abstractmethod
    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return free-form text for the given prompts."""
        raise NotImplementedError

    @abstractmethod
    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        """Return an instance of ``response_model`` parsed from the model output."""
        raise NotImplementedError
