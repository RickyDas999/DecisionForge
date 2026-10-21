"""Current-architecture input/output models for the three leaf specialist agents.

These are new models for the single-hop design. They deliberately do **not**
reuse the legacy Phase 0 pipeline models (``ResearchPlan``, ``JudgeResult``,
``DecisionAnalysis``, ``FinalBrief`` and friends), whose semantics came from the
removed multi-stage architecture.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.common import NonBlankStr
from app.models.decision import DecisionModel, DecisionReport
from app.models.grounding import GroundingReport
from app.models.search import SearchResult


# --------------------------------------------------------------------------- #
# Research
# --------------------------------------------------------------------------- #
class ResearchInput(BaseModel):
    """Input to :class:`app.agents.research.ResearchAgent`."""

    user_request: NonBlankStr
    #: Optional deterministic evidence (e.g. future tool output). When absent the
    #: agent must not claim to have performed live research.
    provided_context: str | None = None
    #: The search results rendered into ``provided_context``, in order: ``Result n``
    #: is ``evidence[n - 1]``. Lets the agent verify citations in code.
    evidence: list[SearchResult] = Field(default_factory=list)


class ResearchResponse(BaseModel):
    """Structured output of the research specialist."""

    topic: str
    summary: str
    key_findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    #: URLs of the evidence the findings cite.
    sources: list[str] = Field(default_factory=list)
    #: Present in grounded mode: every finding's citation, checked in code.
    grounding: GroundingReport | None = None


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #
class ComparisonInput(BaseModel):
    """Input to :class:`app.agents.comparison.ComparisonAgent`."""

    user_request: NonBlankStr
    provided_context: str | None = None
    #: The search results rendered into ``provided_context`` (see ResearchInput).
    evidence: list[SearchResult] = Field(default_factory=list)


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
    #: Present when the decision engine produced this comparison: the model the
    #: LLM extracted and the engine's deterministic analysis of it.
    decision_model: DecisionModel | None = None
    decision_report: DecisionReport | None = None


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
