"""Construct a :class:`ModelProvider` from a :class:`ModelConfig`.

The factory performs no network calls. With the default config it returns a
:class:`MockModelProvider`, so nothing costs money unless the caller explicitly
selects Anthropic and supplies complete configuration.
"""

from __future__ import annotations

from app.providers.anthropic import AnthropicModelProvider
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.exceptions import ModelConfigurationError
from app.providers.mock import MockModelProvider
from app.providers.model import ModelProvider


def create_model_provider(config: ModelConfig | None = None) -> ModelProvider:
    """Return the provider named by ``config`` (defaulting to mock)."""
    config = config or ModelConfig()

    if config.provider is ModelProviderType.MOCK:
        return MockModelProvider()

    if config.provider is ModelProviderType.ANTHROPIC:
        if not config.api_key:
            raise ModelConfigurationError(
                "MODEL_PROVIDER=anthropic requires an API key (set ANTHROPIC_API_KEY)"
            )
        if not config.model:
            raise ModelConfigurationError(
                "MODEL_PROVIDER=anthropic requires a model (set ANTHROPIC_MODEL)"
            )
        return AnthropicModelProvider(
            api_key=config.api_key,
            model=config.model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

    raise ModelConfigurationError(  # pragma: no cover - enum is exhaustive today
        f"Unsupported model provider: {config.provider!r}"
    )
