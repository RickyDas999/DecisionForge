"""Deterministic evaluation demo — routing accuracy + specialist contract checks.

Offline: uses ``DemoModelProvider`` and canned responses. Zero network, zero cost.

    python scripts/eval_demo.py

This validates the evaluation *plumbing* and the demo router's consistency on
representative prompts. It does not measure real Claude intelligence — pass a real
provider to ``evaluate_routing`` for that.
"""

from __future__ import annotations

from app.evaluation.cases import ROUTING_CASES
from app.evaluation.contracts import (
    check_brief_response,
    check_comparison_response,
    check_research_response,
)
from app.evaluation.runner import evaluate_routing_sync
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)


def _routing_section() -> None:
    print("=" * 64)
    print("ROUTING EVALUATION  (OrchestratorAgent + DemoModelProvider, offline)")
    print("=" * 64)
    report = evaluate_routing_sync(ROUTING_CASES)
    for outcome in report.outcomes:
        mark = "PASS" if outcome.passed else "FAIL"
        print(
            f"  [{mark}] {outcome.case.name:<28} "
            f"expected={outcome.case.expected_route.value:<10} "
            f"got={outcome.predicted_route.value}"
        )
    print(
        f"\n  total={report.total}  passed={report.passed}  failed={report.failed}  "
        f"accuracy={report.accuracy:.0%}"
    )


def _contracts_section() -> None:
    print("\n" + "=" * 64)
    print("SPECIALIST CONTRACT CHECKS  (deterministic, no LLM judge)")
    print("=" * 64)

    good_research = ResearchResponse(
        topic="vector databases",
        summary="A short but non-empty summary.",
        key_findings=["finding one"],
        sources=["https://example.com/a"],
        limitations=["offline demo"],
    )
    bad_research = ResearchResponse(
        topic="x", summary="   ", key_findings=[], sources=["not-a-url"]
    )
    good_comparison = ComparisonResponse(
        question="A vs B",
        options=[ComparisonOption(name="A"), ComparisonOption(name="B")],
        recommendation="Pick A.",
        rationale="A fits the stated context.",
        confidence=0.7,
    )
    bad_comparison = ComparisonResponse(
        question="A vs B", options=[], recommendation="  ", rationale="  ", confidence=0.5
    )
    good_brief = BriefResponse(
        title="Decision", executive_summary="Two options were trialled.", key_points=["k"]
    )
    bad_brief = BriefResponse(title="  ", executive_summary="  ", key_points=[])

    checks = [
        ("research (valid)", check_research_response(good_research)),
        ("research (invalid)", check_research_response(bad_research)),
        ("comparison (valid)", check_comparison_response(good_comparison)),
        ("comparison (invalid)", check_comparison_response(bad_comparison)),
        ("brief (valid)", check_brief_response(good_brief)),
        ("brief (invalid)", check_brief_response(bad_brief)),
    ]
    for name, problems in checks:
        if problems:
            print(f"  [FAIL] {name:<22} -> {', '.join(problems)}")
        else:
            print(f"  [ OK ] {name:<22} -> contract satisfied")


def main() -> int:
    _routing_section()
    _contracts_section()
    print("\nModelProvider network calls: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
