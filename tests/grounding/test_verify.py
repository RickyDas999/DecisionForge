"""Tests for the deterministic citation verifier."""

from __future__ import annotations

import pytest

from app.grounding import verify_findings
from app.models.grounding import Finding, FindingStatus
from app.models.search import SearchResult

EVIDENCE = [
    SearchResult(title="Agent loops in production", url="https://a.example/1",
                 snippet="Most teams cap agent loops at a fixed number of tool calls to bound cost."),
    SearchResult(title="Evaluating agents", url="https://b.example/2",
                 snippet="Offline evals with golden sets catch regressions before release."),
]


def _status(finding: Finding) -> FindingStatus:
    return verify_findings([finding], EVIDENCE).findings[0].status


def test_verbatim_quote_ignoring_case_and_punctuation() -> None:
    f = Finding(claim="Loops are capped.", source=1,
                quote="cap agent loops at a fixed number of tool calls")
    assert _status(f) is FindingStatus.VERIFIED
    f2 = Finding(claim="x", source=2, quote="OFFLINE EVALS, with golden sets")
    assert _status(f2) is FindingStatus.VERIFIED


def test_near_verbatim_quote_is_accepted() -> None:
    f = Finding(claim="x", source=2, quote="offline evals with golden sets catch most regressions")
    assert _status(f) is FindingStatus.VERIFIED  # 7 of 8 words present


@pytest.mark.parametrize("finding,reason", [
    (Finding(claim="x", source=3, quote="anything at all here"), "only 2 were shown"),
    (Finding(claim="x", source=1, quote="bound cost"), "too short"),
    (Finding(claim="x", source=1, quote="golden sets catch regressions"), "not found in Result 1"),
])
def test_unsupported_citations_say_why(finding: Finding, reason: str) -> None:
    checked = verify_findings([finding], EVIDENCE).findings[0]
    assert checked.status is FindingStatus.UNSUPPORTED
    assert reason in checked.reason


def test_uncited_finding_is_model_knowledge() -> None:
    assert _status(Finding(claim="General point.")) is FindingStatus.MODEL_KNOWLEDGE


def test_report_rates() -> None:
    report = verify_findings([
        Finding(claim="a", source=1, quote="cap agent loops at a fixed number"),
        Finding(claim="b", source=2, quote="golden sets catch regressions"),
        Finding(claim="c", source=2, quote="this text appears nowhere at all"),
        Finding(claim="d"),
    ], EVIDENCE)
    assert (report.verified, report.unsupported, report.model_knowledge) == (2, 1, 1)
    assert report.groundedness == 0.5
    assert report.citation_precision == pytest.approx(2 / 3)
    assert report.evidence_count == 2


def test_no_citations_means_no_precision() -> None:
    report = verify_findings([Finding(claim="d")], EVIDENCE)
    assert report.citation_precision is None and report.groundedness == 0.0


def test_drop_invalid_sources_clears_only_out_of_range_citations() -> None:
    from app.grounding import drop_invalid_sources
    from app.models.decision import Criterion, DecisionModel, Score

    model = DecisionModel(
        question="q", options=["A", "B"], criteria=[Criterion(name="c", weight=1.0)],
        scores=[Score(option="A", criterion="c", low=1, high=2, source=2),
                Score(option="B", criterion="c", low=1, high=2, source=3)],
    )
    cleaned, removed = drop_invalid_sources(model, evidence_count=2)
    assert removed == 1
    assert [s.source for s in cleaned.scores] == [2, None]
