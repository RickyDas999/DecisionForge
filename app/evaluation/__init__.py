"""Deterministic evaluation plumbing.

Two independent checks, both offline:

* ``evaluate_routing`` — runs representative prompts through the OrchestratorAgent
  and reports routing accuracy. With the default ``DemoModelProvider`` this
  validates the *plumbing* (and the demo router's consistency), not real model
  intelligence; pass a real provider to measure that.
* ``check_*_response`` — deterministic structural contract checks on the three
  specialist response models. No LLM judge.
"""

from app.evaluation.cases import ROUTING_CASES, EvaluationCase
from app.evaluation.contracts import (
    check_brief_response,
    check_comparison_response,
    check_research_response,
)
from app.evaluation.runner import (
    CaseOutcome,
    EvalReport,
    evaluate_routing,
    evaluate_routing_sync,
)

__all__ = [
    "ROUTING_CASES",
    "CaseOutcome",
    "EvalReport",
    "EvaluationCase",
    "check_brief_response",
    "check_comparison_response",
    "check_research_response",
    "evaluate_routing",
    "evaluate_routing_sync",
]
