"""Routing models for the single-hop orchestrator.

The OrchestratorAgent classifies a user request into exactly one of three
specialist routes. Deterministic Python (a later phase) dispatches on the result.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class AgentRoute(str, Enum):
    """The three specialist routes the orchestrator may select.

    There are exactly three. There is deliberately no ``unknown`` route: the
    orchestrator must commit to the dominant user intent.
    """

    RESEARCH = "research"
    COMPARISON = "comparison"
    BRIEF = "brief"


class RoutingInput(BaseModel):
    """Input to the OrchestratorAgent: the raw user request."""

    user_request: str = Field(min_length=1)

    @field_validator("user_request")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_request must not be empty or whitespace")
        return value


class RoutingDecision(BaseModel):
    """The orchestrator's structured routing decision.

    ``reasoning`` is a short, shareable classification rationale for debugging
    (e.g. "The user is explicitly comparing two databases"). It is not a private
    chain-of-thought trace and must not be treated as one.
    """

    route: AgentRoute
    reasoning: str
