"""Calibration: does a stated win probability match how often the winner is right?

Per-case metrics say whether an answer was good. Calibration asks whether the
system's *confidence* means anything. It uses comparison cases with a clear-cut
acceptable answer: the prediction is the winner's ``win_probability`` and the
outcome is whether that winner was acceptable.

* **Brier score**: mean squared gap between confidence and outcome (0 is
  perfect; always answering 50% scores 0.25).
* **ECE** (expected calibration error): bucket predictions by confidence and
  average ``|accuracy - confidence|`` over buckets, weighted by bucket size.

With a handful of cases these are noisy; they become meaningful as the golden
set grows. They are reported, not gated on.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: Equal-width confidence buckets for ECE and the reliability table.
DEFAULT_BINS = 5


@dataclass(frozen=True)
class CalibrationPoint:
    case_id: str
    confidence: float
    correct: bool


def brier_score(points: Sequence[CalibrationPoint]) -> float | None:
    if not points:
        return None
    return sum((p.confidence - float(p.correct)) ** 2 for p in points) / len(points)


def _bucket(confidence: float, bins: int) -> int:
    return min(int(confidence * bins), bins - 1)


def reliability_table(points: Sequence[CalibrationPoint], bins: int = DEFAULT_BINS) -> list[dict[str, Any]]:
    """One row per non-empty bucket: range, count, mean confidence, accuracy."""
    rows = []
    for b in range(bins):
        members = [p for p in points if _bucket(p.confidence, bins) == b]
        if not members:
            continue
        rows.append({
            "range": f"{b / bins:.1f}-{(b + 1) / bins:.1f}",
            "n": len(members),
            "mean_confidence": sum(p.confidence for p in members) / len(members),
            "accuracy": sum(p.correct for p in members) / len(members),
        })
    return rows


def expected_calibration_error(points: Sequence[CalibrationPoint], bins: int = DEFAULT_BINS) -> float | None:
    if not points:
        return None
    return sum(
        row["n"] / len(points) * abs(row["accuracy"] - row["mean_confidence"])
        for row in reliability_table(points, bins)
    )


def summarize(points: Sequence[CalibrationPoint], bins: int = DEFAULT_BINS) -> dict[str, Any]:
    brier, ece = brier_score(points), expected_calibration_error(points, bins)
    return {
        "n": len(points),
        "brier": None if brier is None else round(brier, 4),
        "ece": None if ece is None else round(ece, 4),
        "bins": [
            {**row, "mean_confidence": round(row["mean_confidence"], 3),
             "accuracy": round(row["accuracy"], 3)}
            for row in reliability_table(points, bins)
        ],
    }
