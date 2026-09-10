"""Deterministic in-memory model provider for tests, demos, and local development.

It never touches the network. Responses are queued up front and consumed in
order; every call is recorded so tests can assert on what an agent asked for.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.providers.exceptions import MockResponseExhaustedError, StructuredOutputError
from app.providers.model import ModelProvider

#: A queued structured response may be a Pydantic model instance or a raw dict.
StructuredResponse = BaseModel | dict[str, Any]


@dataclass
class MockCall:
    """One recorded interaction with the mock provider."""

    operation: str  # "generate_text" or "generate_structured"
    system_prompt: str
    user_prompt: str
    response_model: type[BaseModel] | None = None


class MockModelProvider(ModelProvider):
    """A ``ModelProvider`` that replays pre-configured responses.

    Example::

        provider = MockModelProvider(
            text_responses=["first", "second"],
            structured_responses=[ResearchPlan(...), {"approved": True, "score": 0.9}],
        )

    Each call consumes the next queued response of the matching kind and appends
    a :class:`MockCall` to :attr:`calls`.
    """

    def __init__(
        self,
        *,
        text_responses: Sequence[str] | None = None,
        structured_responses: Sequence[StructuredResponse] | None = None,
    ) -> None:
        self.text_responses: list[str] = list(text_responses or [])
        self.structured_responses: list[StructuredResponse] = list(
            structured_responses or []
        )
        self.calls: list[MockCall] = []

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append(MockCall("generate_text", system_prompt, user_prompt))
        if not self.text_responses:
            raise MockResponseExhaustedError(
                "MockModelProvider has no queued text responses left"
            )
        return self.text_responses.pop(0)

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        self.calls.append(
            MockCall("generate_structured", system_prompt, user_prompt, response_model)
        )
        if not self.structured_responses:
            raise MockResponseExhaustedError(
                "MockModelProvider has no queued structured responses left"
            )

        raw = self.structured_responses.pop(0)

        if isinstance(raw, response_model):
            return raw

        if isinstance(raw, BaseModel):
            payload: Any = raw.model_dump()
        elif isinstance(raw, dict):
            payload = raw
        else:  # pragma: no cover - guarded by the StructuredResponse type
            raise StructuredOutputError(
                f"Queued structured response has unsupported type {type(raw)!r}"
            )

        try:
            return response_model.model_validate(payload)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"Queued structured response does not match {response_model.__name__}"
            ) from exc
