"""Analysis domain models produced by the future AnalysisAgent.

One reusable agent implementation runs in three modes (primary, risk,
alternatives). No separate RiskAgent / AlternativesAgent classes exist.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.models.research import ResearchResult


class AnalysisMode(str, Enum):
    """The mode an AnalysisAgent instance operates in."""

    PRIMARY = "primary"
    RISK = "risk"
    ALTERNATIVES = "alternatives"


class AnalysisInput(BaseModel):
    """Input for the primary decision analysis pass."""

    question: str
    options: list[str] = Field(default_factory=list)
    research_results: list[ResearchResult] = Field(default_factory=list)


class OptionAssessment(BaseModel):
    """Assessment of a single option under consideration."""

    option: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    best_for: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)


class DecisionAnalysis(BaseModel):
    """Primary decision analysis output."""

    option_assessments: list[OptionAssessment] = Field(default_factory=list)
    recommendation: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class SecondaryAnalysisInput(BaseModel):
    """Input for the risk and alternatives analysis passes."""

    question: str
    recommendation: str
    research_results: list[ResearchResult] = Field(default_factory=list)


class RiskAnalysis(BaseModel):
    """Risk-mode analysis output."""

    risks: list[str] = Field(default_factory=list)
    failure_modes: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)


class AlternativesAnalysis(BaseModel):
    """Alternatives / counterargument-mode analysis output."""

    alternatives: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    when_recommendation_may_be_wrong: list[str] = Field(default_factory=list)
