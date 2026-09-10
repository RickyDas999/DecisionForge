"""Tests for :class:`MockModelProvider`. No networking occurs."""

from __future__ import annotations

import asyncio

import pytest

from app.models.judging import JudgeResult
from app.models.planning import ResearchPlan, ResearchTrack
from app.providers.exceptions import MockResponseExhaustedError, StructuredOutputError
from app.providers.mock import MockModelProvider


def _plan() -> ResearchPlan:
    return ResearchPlan(
        normalized_question="PostgreSQL vs MongoDB?",
        decision_type="technology-selection",
        options=["PostgreSQL", "MongoDB"],
        research_tracks=[ResearchTrack(name="technical", objective="compare")],
    )


def test_generate_text_returns_configured_response() -> None:
    provider = MockModelProvider(text_responses=["hello world"])
    result = asyncio.run(
        provider.generate_text(system_prompt="sys", user_prompt="hi")
    )
    assert result == "hello world"


def test_multiple_text_responses_consumed_in_order() -> None:
    provider = MockModelProvider(text_responses=["first", "second"])
    first = asyncio.run(provider.generate_text(system_prompt="s", user_prompt="a"))
    second = asyncio.run(provider.generate_text(system_prompt="s", user_prompt="b"))
    assert (first, second) == ("first", "second")


def test_generate_structured_returns_matching_model() -> None:
    plan = _plan()
    provider = MockModelProvider(structured_responses=[plan])
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="s", user_prompt="u", response_model=ResearchPlan
        )
    )
    assert isinstance(result, ResearchPlan)
    assert result.options == ["PostgreSQL", "MongoDB"]


def test_generate_structured_accepts_dict_payload() -> None:
    payload = {
        "approved": True,
        "score": 0.88,
        "strengths": ["primary sources"],
        "weaknesses": [],
        "missing_information": [],
        "follow_up_queries": [],
    }
    provider = MockModelProvider(structured_responses=[payload])
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="s", user_prompt="u", response_model=JudgeResult
        )
    )
    assert isinstance(result, JudgeResult)
    assert result.approved is True
    assert result.score == 0.88


def test_incompatible_structured_response_raises() -> None:
    # Queue a JudgeResult but ask for a ResearchPlan.
    provider = MockModelProvider(
        structured_responses=[JudgeResult(approved=False, score=0.1)]
    )
    with pytest.raises(StructuredOutputError):
        asyncio.run(
            provider.generate_structured(
                system_prompt="s", user_prompt="u", response_model=ResearchPlan
            )
        )


def test_incompatible_dict_payload_raises() -> None:
    provider = MockModelProvider(structured_responses=[{"score": 5.0}])
    with pytest.raises(StructuredOutputError):
        asyncio.run(
            provider.generate_structured(
                system_prompt="s", user_prompt="u", response_model=JudgeResult
            )
        )


def test_exhausting_text_responses_raises() -> None:
    provider = MockModelProvider(text_responses=["only"])
    asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    with pytest.raises(MockResponseExhaustedError):
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))


def test_exhausting_structured_responses_raises() -> None:
    provider = MockModelProvider()
    with pytest.raises(MockResponseExhaustedError):
        asyncio.run(
            provider.generate_structured(
                system_prompt="s", user_prompt="u", response_model=ResearchPlan
            )
        )


def test_call_history_records_interactions() -> None:
    provider = MockModelProvider(
        text_responses=["t"],
        structured_responses=[_plan()],
    )
    asyncio.run(provider.generate_text(system_prompt="sys-a", user_prompt="user-a"))
    asyncio.run(
        provider.generate_structured(
            system_prompt="sys-b", user_prompt="user-b", response_model=ResearchPlan
        )
    )

    assert len(provider.calls) == 2

    text_call = provider.calls[0]
    assert text_call.operation == "generate_text"
    assert text_call.system_prompt == "sys-a"
    assert text_call.user_prompt == "user-a"
    assert text_call.response_model is None

    structured_call = provider.calls[1]
    assert structured_call.operation == "generate_structured"
    assert structured_call.system_prompt == "sys-b"
    assert structured_call.user_prompt == "user-b"
    assert structured_call.response_model is ResearchPlan
