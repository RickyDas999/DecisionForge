"""Tests for :class:`ComparisonAgent`. MockModelProvider only; no network."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.comparison import COMPARISON_SYSTEM_PROMPT, ComparisonAgent
from app.models.specialists import (
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
)
from app.providers.mock import MockModelProvider

REQUEST = "Compare PostgreSQL and MongoDB for a small SaaS application."
CONTEXT = "Team note: strong SQL skills, modest scale, relational data."


def _response() -> ComparisonResponse:
    return ComparisonResponse(
        question=REQUEST,
        options=[
            ComparisonOption(name="PostgreSQL", advantages=["ACID"], disadvantages=[]),
            ComparisonOption(name="MongoDB", advantages=["flexible"], disadvantages=[]),
        ],
        recommendation="PostgreSQL",
        rationale="Relational data, strong SQL skills.",
        important_tradeoffs=["schema rigidity vs flexibility"],
        confidence=0.7,
        limitations=["no current benchmarks supplied"],
    )


def _provider() -> MockModelProvider:
    return MockModelProvider(structured_responses=[_response()])


def _run(agent: ComparisonAgent, task_input: ComparisonInput) -> ComparisonResponse:
    return asyncio.run(agent.run(task_input, AgentRuntimeContext(run_id="t")))


def test_name_is_comparison() -> None:
    assert ComparisonAgent(_provider()).name == "comparison"


def test_run_returns_comparison_response() -> None:
    result = _run(ComparisonAgent(_provider()), ComparisonInput(user_request=REQUEST))
    assert isinstance(result, ComparisonResponse)


def test_response_model_is_comparison_response() -> None:
    provider = _provider()
    _run(ComparisonAgent(provider), ComparisonInput(user_request=REQUEST))
    assert provider.calls[0].response_model is ComparisonResponse


def test_exactly_one_structured_call_and_no_text_call() -> None:
    provider = _provider()
    _run(ComparisonAgent(provider), ComparisonInput(user_request=REQUEST))
    assert len(provider.calls) == 1
    assert provider.calls[0].operation == "generate_structured"
    assert provider.text_responses == []


def test_user_request_appears_in_prompt() -> None:
    provider = _provider()
    _run(ComparisonAgent(provider), ComparisonInput(user_request=REQUEST))
    assert REQUEST in provider.calls[0].user_prompt


def test_provided_context_appears_when_supplied() -> None:
    provider = _provider()
    _run(
        ComparisonAgent(provider),
        ComparisonInput(user_request=REQUEST, provided_context=CONTEXT),
    )
    assert CONTEXT in provider.calls[0].user_prompt


def test_confidence_bounds_are_enforced() -> None:
    with pytest.raises(ValueError):
        ComparisonResponse(
            question="q",
            recommendation="r",
            rationale="why",
            confidence=1.5,
        )
    with pytest.raises(ValueError):
        ComparisonResponse(
            question="q",
            recommendation="r",
            rationale="why",
            confidence=-0.1,
        )


def test_input_is_not_mutated() -> None:
    provider = _provider()
    task_input = ComparisonInput(user_request=REQUEST, provided_context=CONTEXT)
    snapshot = task_input.model_copy(deep=True)
    _run(ComparisonAgent(provider), task_input)
    assert task_input == snapshot


def test_blank_request_is_rejected() -> None:
    with pytest.raises(ValueError):
        ComparisonInput(user_request="  \n ")


def test_system_prompt_prohibits_delegation() -> None:
    prompt = COMPARISON_SYSTEM_PROMPT.lower()
    assert "do not call another agent" in prompt
    assert "do not delegate" in prompt
    assert "do not create a multi-stage workflow" in prompt
