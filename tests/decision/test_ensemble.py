"""Tests for merging two decision-model samples."""

from __future__ import annotations

import pytest

from app.decision.ensemble import disagreement, merge_models
from app.models.decision import Criterion, DecisionModel, Score


def _model(scores, criteria=(("Cost", 0.5), ("Speed", 0.5)), options=("A", "B")) -> DecisionModel:
    return DecisionModel(
        question="A or B?",
        options=list(options),
        criteria=[Criterion(name=n, weight=w) for n, w in criteria],
        scores=[Score(option=o, criterion=c, low=lo, high=hi) for o, c, lo, hi in scores],
        assumptions=["small team"],
    )


FIRST = _model([("A", "Cost", 6, 8), ("B", "Cost", 4, 5), ("A", "Speed", 5, 6), ("B", "Speed", 7, 8)])


def test_shared_cells_take_the_envelope() -> None:
    second = _model([("A", "Cost", 3, 7), ("B", "Cost", 4, 5)])
    merged = merge_models(FIRST, second)
    cell = next(s for s in merged.scores if s.option == "A" and s.criterion == "Cost")
    assert (cell.low, cell.high) == (3, 8)
    assert len(merged.scores) == 4  # nothing lost, nothing duplicated


def test_weights_average_with_missing_as_zero() -> None:
    second = _model([("A", "Ecosystem", 5, 6)], criteria=(("Cost", 0.3), ("Ecosystem", 0.7)))
    weights = {c.name: c.weight for c in merge_models(FIRST, second).criteria}
    assert weights == {"Cost": pytest.approx(0.4), "Speed": pytest.approx(0.25),
                       "Ecosystem": pytest.approx(0.35)}


def test_second_sample_cannot_add_options_and_fills_gaps() -> None:
    first = _model([("A", "Cost", 6, 8)])
    second = _model([("B", "Cost", 2, 3), ("C", "Cost", 9, 10)], options=("A", "B", "C"))
    merged = merge_models(first, second)
    assert merged.options == ["A", "B"]
    assert {(s.option, s.criterion) for s in merged.scores} == {("A", "Cost"), ("B", "Cost")}


def test_names_match_case_insensitively_and_assumptions_dedupe() -> None:
    second = _model([("a", "COST", 7, 9)])
    merged = merge_models(FIRST, second)
    assert merged.assumptions == ["small team"]
    cell = next(s for s in merged.scores if s.option == "A" and s.criterion == "Cost")
    assert (cell.low, cell.high) == (6, 9)


def test_disagreement() -> None:
    assert disagreement(FIRST, FIRST) == 0.0
    shifted = _model([("A", "Cost", 9, 10), ("B", "Cost", 4, 5)])  # A/Cost mid 7 -> 9.5
    assert disagreement(FIRST, shifted) == pytest.approx(0.125)  # (0.25 + 0) / 2
    assert disagreement(FIRST, _model([("A", "Other", 1, 2)], criteria=(("Other", 1.0),))) is None
