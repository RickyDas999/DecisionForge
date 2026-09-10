"""Judge domain models produced by the future JudgeAgent.

``JudgeResult`` is deliberately machine-readable: deterministic orchestration code
branches on ``approved`` and feeds ``follow_up_queries`` back into the bounded
research loop.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.planning import ResearchPlan
from app.models.research import ResearchResult


class JudgeInput(BaseModel):
    """Everything the judge needs to assess evidence quality."""

    question: str
    plan: ResearchPlan
    research_results: list[ResearchResult] = Field(default_factory=list)


class JudgeResult(BaseModel):
    """Structured verdict on the gathered evidence."""

    approved: bool
    score: float = Field(ge=0.0, le=1.0)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    follow_up_queries: list[str] = Field(default_factory=list)
