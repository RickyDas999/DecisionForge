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


# -- cost controls -----------------------------------------------------------

from app.providers.usage import (  # noqa: E402
    BudgetExceededError,
    CallSource,
    LifetimeSpend,
    RunBudget,
    UsageLedger,
    metered,
)


def _billed_message(text: str, input_tokens: int, output_tokens: int, stop: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop,
    )


def test_live_call_is_recorded_in_active_ledger() -> None:
    provider, _ = _provider(_billed_message("ok", 1000, 200), model="claude-haiku-5-5", max_tokens=800)
    ledger = UsageLedger()
    with metered(ledger):
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    (call,) = ledger.calls
    assert call.source is CallSource.LIVE
    assert (call.input_tokens, call.output_tokens) == (1000, 200)
    assert call.cost_usd == pytest.approx(0.0002)


def test_over_budget_call_is_never_sent() -> None:
    provider, client = _provider(_billed_message("ok", 1, 1), max_tokens=100_000)
    with metered(UsageLedger(RunBudget(max_usd=0.001))):
        with pytest.raises(BudgetExceededError):
            asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    assert client.messages.last_request is None


def test_lifetime_cap_blocks_and_accumulates(tmp_path) -> None:
    spend = LifetimeSpend(tmp_path / "spend.json", limit_usd=0.0006)
    provider, client = _provider(
        _billed_message("ok", 1000, 200), model="claude-haiku-5-5",
        max_tokens=800, lifetime_spend=spend,
    )
    asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    assert spend.total_usd == pytest.approx(0.0002)
    # next worst case (~0.0004) on top of 0.0002 spent exceeds 0.0006
    client.messages.last_request = None
    with pytest.raises(BudgetExceededError):
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u" * 300))
    assert client.messages.last_request is None


def test_low_effort_and_thinking_off_sent_to_haiku_5_5() -> None:
    provider, client = _provider(
        _billed_message("ok", 1, 1), model="claude-haiku-5-5",
        effort="low", disable_thinking=True,
    )
    asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    req = client.messages.last_request
    assert req["output_config"] == {"effort": "low"}
    assert req["thinking"] == {"type": "disabled"}


def test_effort_and_thinking_omitted_for_haiku_4_5() -> None:
    provider, client = _provider(
        _billed_message("ok", 1, 1), model="claude-haiku-4-5",
        effort="low", disable_thinking=True,
    )
    asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    req = client.messages.last_request
    assert "output_config" not in req and "thinking" not in req


def test_truncated_response_raises_with_diagnostics() -> None:
    message = _billed_message('{\n  "a": [\n    1,', 10, 800, stop="max_tokens")
    message.content.insert(0, SimpleNamespace(type="thinking", thinking=""))
    provider, _ = _provider(message)
    with pytest.raises(ModelResponseError) as excinfo:
        asyncio.run(provider.generate_text(system_prompt="s", user_prompt="u"))
    text = str(excinfo.value)
    assert "800 output tokens" in text
    assert "blocks: thinking, text" in text
    assert "2 line breaks" in text


def test_structured_schema_is_compact() -> None:
    provider, client = _provider(_billed_message('{"approved": true, "score": 0.5}', 1, 1))
    asyncio.run(provider.generate_structured(
        system_prompt="s", user_prompt="u", response_model=JudgeResult
    ))
    assert '": ' not in client.messages.last_request["system"].split("JSON Schema:")[1]


def test_structured_prompt_asks_for_minified_single_line_json() -> None:
    provider, client = _provider(_billed_message('{"approved": true, "score": 0.5}', 1, 1))
    asyncio.run(provider.generate_structured(
        system_prompt="s", user_prompt="u", response_model=JudgeResult
    ))
    assert "minified JSON object on a single line" in client.messages.last_request["system"]
