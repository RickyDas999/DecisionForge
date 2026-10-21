"""Tests for calibration metrics and their place in eval reports."""

from __future__ import annotations

import asyncio

import pytest

from app.evaluation.calibration import (
    CalibrationPoint,
    brier_score,
    expected_calibration_error,
    reliability_table,
    summarize,
)
from app.evaluation.golden import load_golden_set
from app.evaluation.harness import run_eval
from app.evaluation.report import to_dict, to_markdown
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider


def _p(conf: float, correct: bool, i: int = 0) -> CalibrationPoint:
    return CalibrationPoint(case_id=f"c{i}", confidence=conf, correct=correct)


def test_brier_score() -> None:
    assert brier_score([_p(1.0, True), _p(0.0, False)]) == 0.0
    assert brier_score([_p(0.5, True), _p(0.5, False)]) == pytest.approx(0.25)
    assert brier_score([]) is None


def test_perfectly_calibrated_buckets_have_zero_ece() -> None:
    points = [_p(0.9, i < 9, i) for i in range(10)]  # 90% confident, 90% right
    assert expected_calibration_error(points) == pytest.approx(0.0)


def test_overconfidence_shows_up_in_ece_and_table() -> None:
    points = [_p(0.95, i < 5, i) for i in range(10)]  # 95% confident, 50% right
    assert expected_calibration_error(points) == pytest.approx(0.45)
    (row,) = reliability_table(points)
    assert row["range"] == "0.8-1.0" and row["n"] == 10 and row["accuracy"] == 0.5


def test_confidence_of_one_lands_in_the_top_bucket() -> None:
    assert reliability_table([_p(1.0, True)])[0]["range"] == "0.8-1.0"


def test_summarize_empty() -> None:
    assert summarize([]) == {"n": 0, "brier": None, "ece": None, "bins": []}


def test_eval_report_includes_calibration() -> None:
    run = asyncio.run(run_eval(load_golden_set(), DemoModelProvider(), label="cal",
                               search_provider=DemoSearchProvider()))
    points = run.calibration_points()
    expected = {c.id for c in load_golden_set() if c.acceptable_recommendations}
    assert {p.case_id for p in points} <= expected and points
    cal = to_dict(run)["calibration"]
    assert cal["n"] == len(points) and 0.0 <= cal["brier"] <= 1.0
    md = to_markdown(run, baseline=to_dict(run))
    assert "## Calibration" in md and "Δ Brier =" in md
