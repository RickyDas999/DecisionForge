"""Shared run state passed between deterministic orchestration stages.

``RunState`` is a plain typed data container in Phase 0. It is deliberately not a
service or repository yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from app.models.analysis import AlternativesAnalysis, DecisionAnalysis, RiskAnalysis
from app.models.brief import FinalBrief
from app.models.judging import JudgeResult
from app.models.planning import ResearchPlan
from app.models.research import ResearchResult


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    """Lifecycle status of a single decision run."""

    CREATED = "created"
    PLANNING = "planning"
    RESEARCHING = "researching"
    JUDGING = "judging"
    ANALYZING = "analyzing"
    WRITING = "writing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class RunState(BaseModel):
    """Deterministic shared workflow state for one run."""

    run_id: str
    original_query: str
    status: RunStatus = RunStatus.CREATED
    research_iteration: int = 0

    research_plan: ResearchPlan | None = None
    research_results: list[ResearchResult] = Field(default_factory=list)
    judge_result: JudgeResult | None = None
    analysis: DecisionAnalysis | None = None
    risk_analysis: RiskAnalysis | None = None
    alternatives_analysis: AlternativesAnalysis | None = None
    final_brief: FinalBrief | None = None

    errors: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
