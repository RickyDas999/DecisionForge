"""The golden evaluation set: hand-written cases with deterministic expectations.

Cases live in ``evals/golden_set.json`` (data, not code) so they can grow without
touching Python. Every expectation is checkable by string matching against the
structured result: no LLM judge is needed to score them.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.models.routing import AgentRoute

#: Repository-root ``evals/golden_set.json``.
DEFAULT_GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "golden_set.json"


class GoldenCase(BaseModel):
    """One request and what a good answer must contain."""

    id: str
    request: str
    provided_context: str | None = None
    expected_route: AgentRoute
    #: Option names the result must compare (comparison cases).
    expected_options: list[str] = Field(default_factory=list)
    #: Any one of these in the recommendation passes; empty = any recommendation.
    acceptable_recommendations: list[str] = Field(default_factory=list)
    #: Rubric terms a complete answer should mention.
    must_mention: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


def load_golden_set(path: str | Path = DEFAULT_GOLDEN_PATH) -> list[GoldenCase]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [GoldenCase.model_validate(c) for c in data["cases"]]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"duplicate case ids in {path}")
    return cases
