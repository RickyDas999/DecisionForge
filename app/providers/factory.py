"""Construct a :class:`ModelProvider` from a :class:`ModelConfig`.

The factory performs no network calls. With the default config it returns a
:class:`MockModelProvider`, so nothing costs money unless the caller explicitly
selects Anthropic and supplies an API key. Real calls default to the cheapest
model and are capped by a lifetime spend limit (``SPEND_LIMIT_USD``).
"""

from __future__ import annotations

from app.providers.anthropic import AnthropicModelProvider
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.exceptions import ModelConfigurationError
from app.providers.mock import MockModelProvider
from app.providers.model import ModelProvider
from app.providers.replay import ReplayMode, ReplayModelProvider
from app.providers.usage import LifetimeSpend


def create_model_provider(config: ModelConfig | None = None) -> ModelProvider:
    """Return the provider named by ``config`` (defaulting to mock).

    With ``replay_mode`` set, the provider is wrapped in a
    :class:`ReplayModelProvider`. ``replay`` mode needs no inner provider (and so
    no API key): every answer comes from the cassette.
    """
    config = config or ModelConfig()

    if config.replay_mode is ReplayMode.OFF:
        return _base_provider(config)
    inner = None if config.replay_mode is ReplayMode.REPLAY else _base_provider(config)
    return ReplayModelProvider(
        inner,
        config.replay_cassette,
        mode=config.replay_mode,
        model=config.resolved_model,
    )


def _base_provider(config: ModelConfig) -> ModelProvider:
    if config.provider is ModelProviderType.MOCK:
        return MockModelProvider()

    if config.provider is ModelProviderType.ANTHROPIC:
        if not config.api_key:
            raise ModelConfigurationError(
                "MODEL_PROVIDER=anthropic requires an API key (set ANTHROPIC_API_KEY)"
            )
        return AnthropicModelProvider(
            api_key=config.api_key,
            model=config.resolved_model,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            effort=config.effort,
            disable_thinking=config.disable_thinking,
            lifetime_spend=LifetimeSpend(
                config.spend_ledger_path, config.spend_limit_usd
            ),
        )

    raise ModelConfigurationError(  # pragma: no cover - enum is exhaustive today
        f"Unsupported model provider: {config.provider!r}"
    )
