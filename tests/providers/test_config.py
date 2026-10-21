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


def test_cost_defaults_are_cheap() -> None:
    config = ModelConfig.from_env({})
    assert config.resolved_model == "claude-haiku-5-5"
    assert config.max_tokens == 800
    assert config.effort == "low"
    assert config.disable_thinking is True
    assert config.run_budget.max_usd == 0.002
    assert config.run_budget.max_calls == 3
    assert config.spend_limit_usd == 0.03


def test_cost_settings_from_env() -> None:
    config = ModelConfig.from_env({
        "ANTHROPIC_EFFORT": "none",
        "ANTHROPIC_DISABLE_THINKING": "false",
        "RUN_BUDGET_USD": "0.01",
        "RUN_MAX_LLM_CALLS": "5",
        "SPEND_LIMIT_USD": "0.10",
        "REPLAY_MODE": "replay",
        "REPLAY_CASSETTE": "x.json",
    })
    assert config.effort is None
    assert config.disable_thinking is False
    assert config.run_budget.max_usd == 0.01
    assert config.run_budget.max_calls == 5
    assert config.spend_limit_usd == 0.10
    assert config.replay_mode.value == "replay"
    assert config.replay_cassette == "x.json"


@pytest.mark.parametrize("name,value", [("ANTHROPIC_EFFORT", "turbo"), ("REPLAY_MODE", "maybe")])
def test_bad_cost_settings_raise(name: str, value: str) -> None:
    with pytest.raises(ModelConfigurationError):
        ModelConfig.from_env({name: value})
