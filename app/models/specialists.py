"""Current-architecture input/output models for the three leaf specialist agents.

These are new models for the single-hop design. They deliberately do **not**
reuse the legacy Phase 0 pipeline models (``ResearchPlan``, ``JudgeResult``,
``DecisionAnalysis``, ``FinalBrief`` and friends), whose semantics came from the
removed multi-stage architecture.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


#: A string field that must contain at least one non-whitespace character.
NonBlankStr = Annotated[str, AfterValidator(_require_nonblank)]


# --------------------------------------------------------------------------- #
# Research
# --------------------------------------------------------------------------- #
class ResearchInput(BaseModel):
    """Input to :class:`app.agents.research.ResearchAgent`."""

    user_request: NonBlankStr
    #: Optional deterministic evidence (e.g. future tool output). When absent the
    #: agent must not claim to have performed live research.
    provided_context: str | None = None


class ResearchResponse(BaseModel):
    """Structured output of the research specialist."""

    topic: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    #: Empty in Phase 3 — no real search tool exists yet.
    sources: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #
class ComparisonInput(BaseModel):
    """Input to :class:`app.agents.comparison.ComparisonAgent`."""

    user_request: NonBlankStr
    provided_context: str | None = None


class ComparisonOption(BaseModel):
    """One option under consideration in a comparison."""

    name: str
    advantages: list[str] = Field(default_factory=list)
    disadvantages: list[str] = Field(default_factory=list)


class ComparisonResponse(BaseModel):
    """Structured output of the comparison specialist."""

    question: str
    options: list[ComparisonOption] = Field(default_factory=list)
    recommendation: str
    rationale: str
    important_tradeoffs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    limitations: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Brief
# --------------------------------------------------------------------------- #
class BriefInput(BaseModel):
    """Input to :class:`app.agents.brief.BriefAgent`.

    Unlike research and comparison, ``provided_context`` is **required**: the
    brief specialist transforms supplied material, it does not gather it.
    """

    user_request: NonBlankStr
    provided_context: NonBlankStr


class BriefResponse(BaseModel):
    """Structured output of the executive-brief specialist."""

    title: str
    executive_summary: str
    key_points: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    action_items: list[str] = Field(default_factory=list)
