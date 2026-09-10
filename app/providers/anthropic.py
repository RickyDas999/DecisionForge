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

from app.providers.exceptions import (
    ModelConfigurationError,
    ModelResponseError,
    StructuredOutputError,
)
from app.providers.model import ModelProvider

# A single leading/trailing Markdown fence, optionally tagged ```json.
_JSON_FENCE_RE = re.compile(r"\A```(?:json)?\s*(.*?)\s*```\Z", re.DOTALL | re.IGNORECASE)

_STRUCTURED_INSTRUCTIONS = (
    "Respond with exactly one JSON object and nothing else: no prose, no "
    "explanation, and no Markdown code fences. The JSON object must validate "
    "against this JSON Schema:\n\n{schema}"
)


class AnthropicModelProvider(ModelProvider):
    """Generate text and structured output via the Anthropic Messages API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float | None = None,
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
        self._client = client if client is not None else _build_async_client(api_key)

    @property
    def model(self) -> str:
        return self._model

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        response = await self._client.messages.create(
            **self._base_request(system_prompt=system_prompt, user_prompt=user_prompt)
        )
        return _extract_text(response)

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        schema = json.dumps(response_model.model_json_schema(), indent=2, sort_keys=True)
        structured_system = (
            f"{system_prompt}\n\n"
            + _STRUCTURED_INSTRUCTIONS.format(schema=schema)
        )
        response = await self._client.messages.create(
            **self._base_request(
                system_prompt=structured_system, user_prompt=user_prompt
            )
        )

        text = _extract_text(response)
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

    def _base_request(self, *, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        if self._temperature is not None:
            request["temperature"] = self._temperature
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


def _strip_json_fence(text: str) -> str:
    """Return the JSON payload, unwrapping a single surrounding Markdown fence."""
    stripped = text.strip()
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped
