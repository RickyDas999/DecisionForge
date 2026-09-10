"""Tests for :class:`AnthropicModelProvider`.

Every Anthropic interaction is faked. The real ``anthropic`` SDK is never
imported and no network request is made: a stub async client is injected through
the provider's ``client`` argument.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.judging import JudgeResult
from app.providers.anthropic import AnthropicModelProvider
from app.providers.exceptions import ModelResponseError, StructuredOutputError

FAKE_KEY = "sk-ant-fake-key-not-real"
FAKE_MODEL = "claude-test-model"


class _FakeMessages:
    def __init__(self, outcome: Any) -> None:
        self._outcome = outcome
        self.last_request: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.last_request = kwargs
        if isinstance(self._outcome, BaseException):
            raise self._outcome
        return self._outcome


class _FakeAnthropicClient:
    """Stands in for ``anthropic.AsyncAnthropic``."""

    def __init__(self, outcome: Any) -> None:
        self.messages = _FakeMessages(outcome)


def _message(*text_blocks: str) -> SimpleNamespace:
    blocks = [SimpleNamespace(type="text", text=t) for t in text_blocks]
    return SimpleNamespace(content=blocks)


def _provider(outcome: Any, **overrides: Any) -> tuple[AnthropicModelProvider, _FakeAnthropicClient]:
    client = _FakeAnthropicClient(outcome)
    kwargs: dict[str, Any] = {
        "api_key": FAKE_KEY,
        "model": FAKE_MODEL,
        "client": client,
    }
    kwargs.update(overrides)
    return AnthropicModelProvider(**kwargs), client


def test_generate_text_extracts_text() -> None:
    provider, _ = _provider(_message("Hello, ", "world."))
    result = asyncio.run(
        provider.generate_text(system_prompt="be terse", user_prompt="greet")
    )
    assert result == "Hello, world."


def test_request_carries_system_user_and_model() -> None:
    provider, client = _provider(_message("ok"), temperature=0.3, max_tokens=123)
    asyncio.run(provider.generate_text(system_prompt="SYSTEM", user_prompt="USER"))

    req = client.messages.last_request
    assert req["model"] == FAKE_MODEL
    assert req["system"] == "SYSTEM"
    assert req["messages"] == [{"role": "user", "content": "USER"}]
    assert req["max_tokens"] == 123
    assert req["temperature"] == 0.3


def test_temperature_omitted_when_not_configured() -> None:
    provider, client = _provider(_message("ok"))
    asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    assert "temperature" not in client.messages.last_request


def test_generate_structured_parses_raw_json() -> None:
    raw = '{"approved": true, "score": 0.7}'
    provider, _ = _provider(_message(raw))
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="s", user_prompt="u", response_model=JudgeResult
        )
    )
    assert isinstance(result, JudgeResult)
    assert result.approved is True
    assert result.score == 0.7


def test_generate_structured_parses_fenced_json() -> None:
    fenced = '```json\n{"approved": false, "score": 0.2}\n```'
    provider, _ = _provider(_message(fenced))
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="s", user_prompt="u", response_model=JudgeResult
        )
    )
    assert isinstance(result, JudgeResult)
    assert result.approved is False


def test_generate_structured_parses_bare_fence() -> None:
    fenced = '```\n{"approved": true, "score": 1.0}\n```'
    provider, _ = _provider(_message(fenced))
    result = asyncio.run(
        provider.generate_structured(
            system_prompt="s", user_prompt="u", response_model=JudgeResult
        )
    )
    assert result.score == 1.0


def test_structured_request_includes_schema() -> None:
    provider, client = _provider(_message('{"approved": true, "score": 0.5}'))
    asyncio.run(
        provider.generate_structured(
            system_prompt="ROLE", user_prompt="u", response_model=JudgeResult
        )
    )
    system_text = client.messages.last_request["system"]
    assert system_text.startswith("ROLE")
    assert "JSON Schema" in system_text
    assert '"follow_up_queries"' in system_text  # a JudgeResult field name


def test_malformed_json_raises_structured_output_error() -> None:
    provider, _ = _provider(_message("{not valid json"))
    with pytest.raises(StructuredOutputError):
        asyncio.run(
            provider.generate_structured(
                system_prompt="s", user_prompt="u", response_model=JudgeResult
            )
        )


def test_structurally_invalid_json_raises_structured_output_error() -> None:
    # Valid JSON, but score is out of the 0..1 range required by JudgeResult.
    provider, _ = _provider(_message('{"approved": true, "score": 9.9}'))
    with pytest.raises(StructuredOutputError):
        asyncio.run(
            provider.generate_structured(
                system_prompt="s", user_prompt="u", response_model=JudgeResult
            )
        )


def test_response_without_text_raises_model_response_error() -> None:
    provider, _ = _provider(SimpleNamespace(content=[]))
    with pytest.raises(ModelResponseError):
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))


def test_response_with_only_nontext_blocks_raises_model_response_error() -> None:
    provider, _ = _provider(
        SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="...")])
    )
    with pytest.raises(ModelResponseError):
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))


def test_constructor_makes_no_request() -> None:
    client = _FakeAnthropicClient(_message("unused"))
    AnthropicModelProvider(api_key=FAKE_KEY, model=FAKE_MODEL, client=client)
    assert client.messages.last_request is None
