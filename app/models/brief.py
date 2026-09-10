"""Final decision brief models produced by the future WriterAgent.

The brief is structured rather than plain Markdown so later phases can validate,
render, persist, and export it. Markdown rendering is a later concern.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.analysis import AlternativesAnalysis, DecisionAnalysis, RiskAnalysis
from app.models.research import ResearchResult, Source


class BriefInput(BaseModel):
    """Everything the writer needs to assemble the final brief."""

    question: str
    research_summary: list[ResearchResult] = Field(default_factory=list)
    analysis: DecisionAnalysis
    risk_analysis: RiskAnalysis
    alternatives_analysis: AlternativesAnalysis


class FinalBrief(BaseModel):
    """Structured decision brief, the terminal artifact of a run."""

    title: str
    executive_summary: str
    recommendation: str
    rationale: str
    risks: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
