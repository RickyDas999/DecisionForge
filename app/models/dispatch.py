"""Input/output models for the deterministic single-hop dispatcher.

``DispatchRequest`` -> one OrchestratorAgent call -> exactly one specialist call
-> ``DispatchResult``. No additional LLM calls, no fallback, no retry.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.models.routing import AgentRoute
from app.models.specialists import (
    BriefResponse,
    ComparisonResponse,
    NonBlankStr,
    ResearchResponse,
)

#: The typed result produced by whichever specialist was selected.
SpecialistResponse = ResearchResponse | ComparisonResponse | BriefResponse


class DispatchRequest(BaseModel):
    """A single end-to-end DecisionForge request."""

    user_request: NonBlankStr
    #: Optional evidence / source material. Required in practice only for the
    #: brief route (the dispatcher enforces that deterministically).
    provided_context: str | None = None


class DispatchResult(BaseModel):
    """The outcome of a completed dispatch."""

    route: AgentRoute
    routing_reasoning: str
    result: SpecialistResponse
