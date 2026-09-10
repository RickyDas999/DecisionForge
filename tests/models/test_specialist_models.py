"""Validation tests for the current-architecture specialist models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.specialists import (
    BriefInput,
    BriefResponse,
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
    ResearchInput,
    ResearchResponse,
)


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_research_input_rejects_blank_user_request(blank: str) -> None:
    with pytest.raises(ValidationError):
        ResearchInput(user_request=blank)


def test_research_input_allows_optional_context() -> None:
    assert ResearchInput(user_request="explain x").provided_context is None
    assert ResearchInput(user_request="explain x", provided_context="c").provided_context == "c"


def test_research_response_defaults_are_independent_lists() -> None:
    a = ResearchResponse(topic="t", summary="s")
    b = ResearchResponse(topic="t", summary="s")
    a.key_findings.append("x")
    assert b.key_findings == []
    assert a.sources == [] and a.limitations == []


@pytest.mark.parametrize("blank", ["", "   "])
def test_comparison_input_rejects_blank_user_request(blank: str) -> None:
    with pytest.raises(ValidationError):
        ComparisonInput(user_request=blank)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
def test_comparison_response_rejects_out_of_range_confidence(bad: float) -> None:
    with pytest.raises(ValidationError):
        ComparisonResponse(
            question="q", recommendation="r", rationale="why", confidence=bad
        )


@pytest.mark.parametrize("ok", [0.0, 0.5, 1.0])
def test_comparison_response_accepts_in_range_confidence(ok: float) -> None:
    resp = ComparisonResponse(
        question="q", recommendation="r", rationale="why", confidence=ok
    )
    assert resp.confidence == ok
    assert resp.options == [] and resp.important_tradeoffs == []


def test_comparison_option_list_defaults() -> None:
    opt = ComparisonOption(name="X")
    assert opt.advantages == [] and opt.disadvantages == []


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_brief_input_rejects_blank_context(blank: str) -> None:
    with pytest.raises(ValidationError):
        BriefInput(user_request="make a brief", provided_context=blank)


def test_brief_input_rejects_blank_user_request() -> None:
    with pytest.raises(ValidationError):
        BriefInput(user_request="  ", provided_context="real material")


def test_brief_response_defaults() -> None:
    resp = BriefResponse(title="t", executive_summary="s")
    assert resp.key_points == []
    assert resp.action_items == []
    assert resp.recommendation is None
