"""Search-result models for the deterministic tool layer.

These are current-architecture models. Search is a *tool* — it never involves an
LLM, an agent, or the dispatcher's routing decision.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.specialists import NonBlankStr


class SearchResult(BaseModel):
    """One result from a search provider."""

    title: NonBlankStr
    url: NonBlankStr
    snippet: NonBlankStr
    source: str | None = None


class SearchResponse(BaseModel):
    """The results for a single query."""

    query: NonBlankStr
    results: list[SearchResult] = Field(default_factory=list)
