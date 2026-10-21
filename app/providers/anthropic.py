"""Anthropic-backed :class:`ModelProvider`.

The ``anthropic`` SDK is confined to this module. Nothing here runs at import
time and the constructor makes no network request. The rest of DecisionForge
depends only on :class:`app.providers.model.ModelProvider`.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.providers.config import DEFAULT_MAX_TOKENS
from app.providers.exceptions import (
    ModelConfigurationError,
    ModelResponseError,
    StructuredOutputError,
)
from app.providers.model import ModelProvider
from app.providers.usage import (
    CallSource,
    LifetimeSpend,
    active_ledger,
    cost_usd,
    estimate_tokens,
)

# A single leading/trailing Markdown fence, optionally tagged ```json.
_JSON_FENCE_RE = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.DOTALL | re.IGNORECASE)

_STRUCTURED_INSTRUCTIONS = (
    "Respond with exactly one JSON object and nothing else: no prose, no "
    "explanation, and no Markdown code fences. The JSON object must validate "
    "against this JSON Schema:\n\n{schema}"
)

#: Models that reject ``output_config.effort`` (it is sent to every other model).
_NO_EFFORT_MODELS = frozenset({"claude-haiku-4-5"})

#: Models on which ``thinking: {type: "disabled"}`` is accepted at low effort.
#: Elsewhere thinking is left at the model default (some models reject disabling it).
_THINKING_OFF_MODELS = frozenset({"claude-haiku-5-5", "claude-sonnet-5", "claude-opus-5"})


class AnthropicModelProvider(ModelProvider):
    """Generate text and structured output via the Anthropic Messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float | None = None,
        effort: str | None = None,
        disable_thinking: bool = False,
        lifetime_spend: LifetimeSpend | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ModelConfigurationError("AnthropicModelProvider requires an api_key")
        if not model:
            raise ModelConfigurationError("AnthropicModelProvider requires a model")
        if max_tokens < 1:
            raise ModelConfigurationError("max_tokens must be a positive integer")

        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._effort = effort
        self._disable_thinking = disable_thinking
        self._lifetime_spend = lifetime_spend
        self._client = client if client is not None else _build_async_client(api_key)

    @property
    def model(self) -> str:
        return self._model

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return await self._call("generate_text", system_prompt, user_prompt)

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        # Compact separators: the schema is resent on every call, so whitespace
        # is paid-for input tokens.
        schema = json.dumps(
            response_model.model_json_schema(), separators=(",", ":"), sort_keys=True
        )
        structured_system = (
            f"{system_prompt}\n\n"
            + _STRUCTURED_INSTRUCTIONS.format(schema=schema)
        )
        text = await self._call("generate_structured", structured_system, user_prompt)
        payload = _strip_json_fence(text)

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(
                f"Anthropic response was not valid JSON: {exc}"
            ) from exc

        try:
            return response_model.model_validate(data)
        except ValidationError as exc:
            raise StructuredOutputError(
                f"Anthropic JSON did not match {response_model.__name__}"
            ) from exc

    async def _call(self, operation: str, system_prompt: str, user_prompt: str) -> str:
        """One metered Messages API request; returns the response text.

        Before sending, the worst case (estimated input + full ``max_tokens``) is
        checked against the active run budget and the lifetime spend cap; either
        raises :class:`BudgetExceededError` and nothing is sent. Afterwards the
        real token usage is recorded.
        """
        estimated_input = estimate_tokens(system_prompt, user_prompt)
        worst_case = cost_usd(self._model, estimated_input, self._max_tokens)
        ledger = active_ledger()
        if ledger is not None:
            ledger.check(
                model=self._model,
                input_tokens=estimated_input,
                max_output_tokens=self._max_tokens,
            )
        if self._lifetime_spend is not None:
            self._lifetime_spend.check(worst_case)

        response = await self._client.messages.create(
            **self._base_request(system_prompt=system_prompt, user_prompt=user_prompt)
        )

        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", None) or estimated_input
        output_tokens = getattr(usage, "output_tokens", None) or self._max_tokens
        if ledger is not None:
            ledger.record(
                operation=operation,
                model=self._model,
                source=CallSource.LIVE,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        if self._lifetime_spend is not None:
            self._lifetime_spend.add(cost_usd(self._model, input_tokens, output_tokens))

        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ModelResponseError(
                f"response hit max_tokens={self._max_tokens} and was truncated "
                f"({_truncation_details(response, output_tokens)})"
            )
        return _extract_text(response)

    def _base_request(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self._temperature is not None:
            request["temperature"] = self._temperature
        if self._effort is not None and self._model not in _NO_EFFORT_MODELS:
            request["output_config"] = {"effort": self._effort}
        if self._disable_thinking and self._model in _THINKING_OFF_MODELS:
            request["thinking"] = {"type": "disabled"}
        return request


def _build_async_client(api_key: str) -> Any:
    try:
        from anthropic import AsyncAnthropic
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without the extra
        raise ModelConfigurationError(
            "The 'anthropic' package is not installed. Install it with "
            "`pip install -e \".[anthropic]\"` to use the Anthropic provider."
        ) from exc
    return AsyncAnthropic(api_key=api_key)


def _extract_text(response: Any) -> str:
    """Pull the concatenated text blocks out of an Anthropic message response."""
    content = getattr(response, "content", None)
    if not content:
        raise ModelResponseError("Anthropic response contained no content blocks")

    parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            if text:
                parts.append(text)

    if not parts:
        raise ModelResponseError("Anthropic response contained no usable text")
    return "".join(parts)


def _truncation_details(response: Any, output_tokens: int) -> str:
    """Where a truncated response's tokens went, without echoing its content."""
    blocks = getattr(response, "content", None) or []
    types = [getattr(b, "type", "?") for b in blocks]
    text = "".join(getattr(b, "text", "") or "" for b in blocks if getattr(b, "type", None) == "text")
    return (
        f"{output_tokens} output tokens; blocks: {', '.join(types) or 'none'}; "
        f"text: {len(text)} chars, {text.count(chr(10))} line breaks"
    )


def _strip_json_fence(text: str) -> str:
    """Return the JSON payload, unwrapping a single surrounding Markdown fence."""
    stripped = text.strip()
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped
