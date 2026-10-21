"""Deterministic decision engine: scoring, simulation, and flip analysis.

The LLM supplies a :class:`app.models.decision.DecisionModel`; everything here is
plain NumPy with no model calls, so it is free, fast, and reproducible.
"""

from app.decision.engine import analyze
from app.decision.summary import to_comparison_response

__all__ = ["analyze", "to_comparison_response"]
