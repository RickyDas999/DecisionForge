"""Decision-model contracts: what the LLM extracts and what the engine computes.

The comparison specialist does not write a verdict. It translates the request
into a :class:`DecisionModel` (options, weighted criteria, and a low/high score
range per option and criterion). Deterministic code in :mod:`app.decision` then
scores it, simulates the uncertainty, and finds the weights at which the answer
flips, producing a :class:`DecisionReport`.

Field names are short because every key in the model's JSON is a paid output
token.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Criterion(BaseModel):
    """One thing that matters for this decision, phrased so higher is better."""

    name: str = Field(min_length=1)
    #: Relative importance; the engine normalizes weights to sum to 1.
    weight: float = Field(gt=0.0, le=1.0)


class Score(BaseModel):
    """How well one option does on one criterion, as a 0-10 range."""

    option: str
    criterion: str
    low: float = Field(ge=0.0, le=10.0)
    high: float = Field(ge=0.0, le=10.0)
    #: A few words on why (shown to the user next to the score).
    note: str = ""
    #: The number of the search result supporting this score; ``None`` means the
    #: model's general knowledge.
    source: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _ordered(self) -> "Score":
        # A small model occasionally swaps the bounds; the intent is unambiguous.
        if self.low > self.high:
            self.low, self.high = self.high, self.low
        return self


class DecisionModel(BaseModel):
    """The structured decision the LLM extracts from a request and its evidence."""

    question: str
    options: list[str] = Field(min_length=2, max_length=5)
    criteria: list[Criterion] = Field(min_length=1, max_length=6)
    scores: list[Score] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def _distinct_options(cls, options: list[str]) -> list[str]:
        cleaned = [o.strip() for o in options if o.strip()]
        if len({o.lower() for o in cleaned}) != len(cleaned) or len(cleaned) < 2:
            raise ValueError("options must be at least two distinct names")
        return cleaned


class OptionResult(BaseModel):
    option: str
    #: Weighted score using the midpoint of every range (0-10).
    expected_score: float
    #: Share of simulations in which this option ranked first.
    win_probability: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)


class FlipPoint(BaseModel):
    """The weight on one criterion at which a different option would win."""

    criterion: str
    current_weight: float
    flip_weight: float
    new_winner: str
    direction: Literal["increase", "decrease"]


class DecisionReport(BaseModel):
    """What the deterministic engine concluded from a :class:`DecisionModel`."""

    winner: str
    verdict: Literal["robust", "leaning", "toss-up"]
    win_probability: float = Field(ge=0.0, le=1.0)
    ranking: list[OptionResult]
    #: Ordered by how little the weight has to move (most fragile first).
    flip_points: list[FlipPoint] = Field(default_factory=list)
    weights: dict[str, float]
    simulations: int
    #: Option/criterion pairs the model did not score (treated as fully uncertain).
    gaps: list[str] = Field(default_factory=list)
    #: How many scores cite a search result.
    cited_scores: int = 0
    total_scores: int = 0
    #: Independent extractions merged into the analysed model.
    samples: int = Field(default=1, ge=1)
    #: Mean midpoint gap between samples on a 0-1 scale (``None`` for one sample).
    disagreement: float | None = None
    #: Score citations removed because they named a result that was never shown.
    invalid_citations: int = Field(default=0, ge=0)
