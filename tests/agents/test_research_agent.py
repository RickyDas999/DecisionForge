"""Tests for :class:`ResearchAgent`. MockModelProvider only; no network."""

from __future__ import annotations

import asyncio

import pytest

from app.agents.base import AgentRuntimeContext
from app.agents.research import RESEARCH_SYSTEM_PROMPT, ResearchAgent
from app.models.specialists import ResearchInput, ResearchResponse
from app.providers.mock import MockModelProvider

REQUEST = "Explain the main open-source vector databases."
CONTEXT = "Evidence: pgvector, Milvus, and Qdrant are widely deployed as of 2024."


def _response() -> ResearchResponse:
    return ResearchResponse(
        topic="vector databases",
        summary="An overview.",
        key_findings=["finding"],
        limitations=["no live search performed"],
        sources=[],
    )


def _provider() -> MockModelProvider:
    return MockModelProvider(structured_responses=[_response()])


def _run(agent: ResearchAgent, task_input: ResearchInput) -> ResearchResponse:
    return asyncio.run(agent.run(task_input, AgentRuntimeContext(run_id="t")))


def test_name_is_research() -> None:
    assert ResearchAgent(_provider()).name == "research"


def test_run_returns_research_response() -> None:
    result = _run(ResearchAgent(_provider()), ResearchInput(user_request=REQUEST))
    assert isinstance(result, ResearchResponse)


def test_response_model_is_research_response() -> None:
    provider = _provider()
    _run(ResearchAgent(provider), ResearchInput(user_request=REQUEST))
    assert provider.calls[0].response_model is ResearchResponse


def test_exactly_one_structured_call_and_no_text_call() -> None:
    provider = _provider()
    _run(ResearchAgent(provider), ResearchInput(user_request=REQUEST))
    assert len(provider.calls) == 1
    assert provider.calls[0].operation == "generate_structured"
    assert provider.text_responses == []


def test_user_request_appears_in_prompt() -> None:
    provider = _provider()
    _run(ResearchAgent(provider), ResearchInput(user_request=REQUEST))
    assert REQUEST in provider.calls[0].user_prompt


def test_provided_context_appears_when_supplied() -> None:
    provider = _provider()
    _run(
        ResearchAgent(provider),
        ResearchInput(user_request=REQUEST, provided_context=CONTEXT),
    )
    assert CONTEXT in provider.calls[0].user_prompt


def test_prompt_notes_absence_of_context_when_missing() -> None:
    provider = _provider()
    _run(ResearchAgent(provider), ResearchInput(user_request=REQUEST))
    assert "none supplied" in provider.calls[0].user_prompt.lower()


def test_input_is_not_mutated() -> None:
    provider = _provider()
    task_input = ResearchInput(user_request=REQUEST, provided_context=CONTEXT)
    snapshot = task_input.model_copy(deep=True)
    _run(ResearchAgent(provider), task_input)
    assert task_input == snapshot


def test_blank_request_is_rejected() -> None:
    with pytest.raises(ValueError):
        ResearchInput(user_request="   ")


def test_system_prompt_forbids_fake_research_and_delegation() -> None:
    prompt = RESEARCH_SYSTEM_PROMPT.lower()
    assert "do not claim" in prompt and "live" in prompt
    assert "do not fabricate citations" in prompt
    assert "do not call another agent" in prompt
