"""Deterministic evaluation plumbing.

The main harness (``run_eval``) runs the golden set in ``evals/golden_set.json``
end to end through the real pipeline and scores every case with the
deterministic metrics in :mod:`app.evaluation.metrics`; reports go to
``evals/reports/``. The original lighter checks remain:

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
from app.evaluation.golden import GoldenCase, load_golden_set
from app.evaluation.harness import CaseResult, EvalRun, run_eval
from app.evaluation.metrics import METRICS, Metric, PipelineOutcome
from app.evaluation.report import load_report, save_report, to_markdown
from app.evaluation.runner import (
    CaseOutcome,
    EvalReport,
    evaluate_routing,
    evaluate_routing_sync,
)

__all__ = [
    "METRICS",
    "ROUTING_CASES",
    "CaseOutcome",
    "CaseResult",
    "EvalReport",
    "EvalRun",
    "EvaluationCase",
    "GoldenCase",
    "Metric",
    "PipelineOutcome",
    "load_golden_set",
    "load_report",
    "run_eval",
    "save_report",
    "to_markdown",
    "check_brief_response",
    "check_comparison_response",
    "check_research_response",
    "evaluate_routing",
    "evaluate_routing_sync",
]
