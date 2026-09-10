"""Research domain models produced by the future ResearchAgent instances."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.planning import ResearchTrack


class Source(BaseModel):
    """A single referenced source."""

    title: str
    url: str
    publisher: str | None = None
    published_at: datetime | None = None


class ResearchFinding(BaseModel):
    """A discrete claim backed by evidence and one or more sources."""

    claim: str
    evidence: str
    source_urls: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)


class ResearchTask(BaseModel):
    """A unit of work assigned to a single research track."""

    question: str
    track: ResearchTrack
    follow_up_queries: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    """Aggregated output of one research track."""

    track_name: str
    summary: str
    findings: list[ResearchFinding] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
