"""Tests for :class:`BriefAgent`. MockModelProvider only; no network."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BRIEF_SYSTEM_PROMPT, BriefAgent
from app.models.specialists import BriefInput, BriefResponse
from app.providers.mock import MockModelProvider

REQUEST = "Create an executive brief for leadership."
CONTEXT = (
    "Our team tested two database approaches over three weeks. "
    "Approach A was faster to ship; approach B scaled better under load."
)


def _response() -> BriefResponse:
    return BriefResponse(
        title="Database Approach Decision",
        executive_summary="Two approaches were tested.",
        key_points=["A shipped faster", "B scaled better"],
        recommendation=None,
        action_items=["Pick a direction by Friday"],
    )


def _provider() -> MockModelProvider:
    return MockModelProvider(structured_responses=[_response()])


def _run(agent: BriefAgent, task_input: BriefInput) -> BriefResponse:
    return asyncio.run(agent.run(task_input, AgentRuntimeContext(run_id="t")))


def test_name_is_brief() -> None:
    assert BriefAgent(_provider()).name == "brief"


def test_run_returns_brief_response() -> None:
    result = _run(
        BriefAgent(_provider()),
        BriefInput(user_request=REQUEST, provided_context=CONTEXT),
    )
    assert isinstance(result, BriefResponse)


def test_response_model_is_brief_response() -> None:
    provider = _provider()
    _run(BriefAgent(provider), BriefInput(user_request=REQUEST, provided_context=CONTEXT))
    assert provider.calls[0].response_model is BriefResponse


def test_exactly_one_structured_call_and_no_text_call() -> None:
    provider = _provider()
    _run(BriefAgent(provider), BriefInput(user_request=REQUEST, provided_context=CONTEXT))
    assert len(provider.calls) == 1
    assert provider.calls[0].operation == "generate_structured"
    assert provider.text_responses == []


def test_user_request_appears_in_prompt() -> None:
    provider = _provider()
    _run(BriefAgent(provider), BriefInput(user_request=REQUEST, provided_context=CONTEXT))
    assert REQUEST in provider.calls[0].user_prompt


def test_provided_context_appears_in_prompt() -> None:
    provider = _provider()
    _run(BriefAgent(provider), BriefInput(user_request=REQUEST, provided_context=CONTEXT))
    assert CONTEXT in provider.calls[0].user_prompt


def test_empty_context_is_rejected() -> None:
    with pytest.raises(ValueError):
        BriefInput(user_request=REQUEST, provided_context="   ")


def test_missing_context_is_rejected() -> None:
    with pytest.raises(ValueError):
        BriefInput(user_request=REQUEST)  # type: ignore[call-arg]


def test_input_is_not_mutated() -> None:
    provider = _provider()
    task_input = BriefInput(user_request=REQUEST, provided_context=CONTEXT)
    snapshot = task_input.model_copy(deep=True)
    _run(BriefAgent(provider), task_input)
    assert task_input == snapshot


def test_system_prompt_forbids_inventing_facts_and_delegation() -> None:
    prompt = BRIEF_SYSTEM_PROMPT.lower()
    assert "do not invent facts" in prompt
    assert "only the information supplied" in prompt
    assert "do not call another agent" in prompt
