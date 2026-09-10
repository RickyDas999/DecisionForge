"""Planning domain models produced by the future PlannerAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlannerInput(BaseModel):
    """Raw decision question submitted by the user."""

    question: str


class ResearchTrack(BaseModel):
    """One independent line of research within a research plan."""

    name: str
    objective: str
    suggested_queries: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    """Normalized decision plus the set of parallelizable research tracks."""

    normalized_question: str
    decision_type: str
    options: list[str] = Field(default_factory=list)
    research_tracks: list[ResearchTrack] = Field(default_factory=list)
