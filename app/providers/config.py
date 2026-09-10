"""Model-provider configuration.

Configuration must be constructible with **no credentials** so the whole project
runs and tests in mock mode for free. Anthropic-specific requirements are
enforced later, when the Anthropic provider is actually constructed
(see ``app/providers/factory.py``), not here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel, Field

from app.env import load_dotenv
from app.providers.exceptions import ModelConfigurationError

#: Default token ceiling for a single generation when none is configured.
DEFAULT_MAX_TOKENS = 4096


class ModelProviderType(str, Enum):
    """Selectable model-provider backends."""

    MOCK = "mock"
    ANTHROPIC = "anthropic"


class ModelConfig(BaseModel):
    """Provider selection plus optional tuning values.

    The default constructs a mock configuration; no environment variables and no
    API key are required.
    """

    provider: ModelProviderType = ModelProviderType.MOCK
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        use_dotenv: bool = True,
    ) -> "ModelConfig":
        """Build a config from environment variables.

        Reads ``MODEL_PROVIDER`` (default ``mock``), ``ANTHROPIC_API_KEY``,
        ``ANTHROPIC_MODEL``, and the optional tuning values
        ``ANTHROPIC_MAX_TOKENS`` and ``ANTHROPIC_TEMPERATURE``.

        When ``env`` is not given, the nearest ``.env`` file at or above the
        current working directory is loaded into ``os.environ`` first (real
        environment variables are never overwritten). Pass an explicit ``env``
        mapping, or ``use_dotenv=False``, to skip that.

        With no variables set, this returns a mock configuration and never
        raises. An unrecognised ``MODEL_PROVIDER`` value raises
        ``ModelConfigurationError``.
        """
        if env is None:
            if use_dotenv:
                load_dotenv()
            source: Mapping[str, str] = os.environ
        else:
            source = env

        raw_provider = (source.get("MODEL_PROVIDER") or "mock").strip().lower() or "mock"
        try:
            provider = ModelProviderType(raw_provider)
        except ValueError as exc:
            allowed = ", ".join(p.value for p in ModelProviderType)
            raise ModelConfigurationError(
                f"Unknown MODEL_PROVIDER {raw_provider!r}; expected one of: {allowed}"
            ) from exc

        api_key = source.get("ANTHROPIC_API_KEY") or None
        model = source.get("ANTHROPIC_MODEL") or None

        max_tokens = _parse_int(source.get("ANTHROPIC_MAX_TOKENS"), DEFAULT_MAX_TOKENS)
        temperature = _parse_float(source.get("ANTHROPIC_TEMPERATURE"))

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
        )


def _parse_int(raw: str | None, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ModelConfigurationError(
            f"ANTHROPIC_MAX_TOKENS must be an integer, got {raw!r}"
        ) from exc


def _parse_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ModelConfigurationError(
            f"ANTHROPIC_TEMPERATURE must be a number, got {raw!r}"
        ) from exc
