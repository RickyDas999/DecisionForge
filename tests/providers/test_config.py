"""Tests for :class:`ModelConfig` and ``ModelConfig.from_env``."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.providers.config import DEFAULT_MAX_TOKENS, ModelConfig, ModelProviderType
from app.providers.exceptions import ModelConfigurationError

FAKE_KEY = "sk-ant-fake-not-real"


def test_default_config_is_mock() -> None:
    config = ModelConfig()
    assert config.provider is ModelProviderType.MOCK
    assert config.model is None
    assert config.api_key is None
    assert config.max_tokens == DEFAULT_MAX_TOKENS
    assert config.temperature is None


def test_from_env_with_no_variables_is_mock() -> None:
    config = ModelConfig.from_env(env={})
    assert config.provider is ModelProviderType.MOCK
    assert config.api_key is None


def test_from_env_anthropic_reads_credentials() -> None:
    config = ModelConfig.from_env(
        env={
            "MODEL_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": FAKE_KEY,
            "ANTHROPIC_MODEL": "claude-test-model",
            "ANTHROPIC_MAX_TOKENS": "2048",
            "ANTHROPIC_TEMPERATURE": "0.4",
        }
    )
    assert config.provider is ModelProviderType.ANTHROPIC
    assert config.api_key == FAKE_KEY
    assert config.model == "claude-test-model"
    assert config.max_tokens == 2048
    assert config.temperature == 0.4


def test_from_env_provider_is_case_insensitive() -> None:
    config = ModelConfig.from_env(env={"MODEL_PROVIDER": "  ANTHROPIC "})
    assert config.provider is ModelProviderType.ANTHROPIC


def test_from_env_unknown_provider_raises() -> None:
    with pytest.raises(ModelConfigurationError):
        ModelConfig.from_env(env={"MODEL_PROVIDER": "openai"})


def test_from_env_does_not_validate_anthropic_completeness() -> None:
    # from_env only reads; the factory enforces that a key + model are present.
    config = ModelConfig.from_env(env={"MODEL_PROVIDER": "anthropic"})
    assert config.provider is ModelProviderType.ANTHROPIC
    assert config.api_key is None
    assert config.model is None


def test_from_env_bad_max_tokens_raises() -> None:
    with pytest.raises(ModelConfigurationError):
        ModelConfig.from_env(env={"ANTHROPIC_MAX_TOKENS": "lots"})


def test_direct_construction_rejects_unknown_provider() -> None:
    with pytest.raises(ValidationError):
        ModelConfig(provider="not-a-provider")


def test_max_tokens_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        ModelConfig(max_tokens=0)
