"""Tests for ``create_model_provider``. No networking occurs."""

from __future__ import annotations

import pytest

import app.providers.anthropic as anthropic_module
from app.providers.anthropic import AnthropicModelProvider
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.exceptions import ModelConfigurationError
from app.providers.factory import create_model_provider
from app.providers.mock import MockModelProvider

FAKE_KEY = "sk-ant-fake-not-real"
FAKE_MODEL = "claude-test-model"


class _StubAsyncClient:
    """Records construction; exposes an inert ``messages`` attribute."""

    instances: list["_StubAsyncClient"] = []

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.messages = object()
        _StubAsyncClient.instances.append(self)


@pytest.fixture
def stub_anthropic_client(monkeypatch: pytest.MonkeyPatch):
    """Replace the real ``AsyncAnthropic`` builder with a network-free stub."""
    _StubAsyncClient.instances.clear()
    monkeypatch.setattr(
        anthropic_module, "_build_async_client", _StubAsyncClient, raising=True
    )
    return _StubAsyncClient


def test_default_config_builds_mock_provider() -> None:
    assert isinstance(create_model_provider(), MockModelProvider)


def test_explicit_mock_config_builds_mock_provider() -> None:
    provider = create_model_provider(ModelConfig(provider=ModelProviderType.MOCK))
    assert isinstance(provider, MockModelProvider)


def test_anthropic_without_api_key_raises() -> None:
    config = ModelConfig(provider=ModelProviderType.ANTHROPIC, model=FAKE_MODEL)
    with pytest.raises(ModelConfigurationError):
        create_model_provider(config)


def test_anthropic_without_model_raises() -> None:
    config = ModelConfig(provider=ModelProviderType.ANTHROPIC, api_key=FAKE_KEY)
    with pytest.raises(ModelConfigurationError):
        create_model_provider(config)


def test_anthropic_with_full_config_builds_provider(stub_anthropic_client) -> None:
    config = ModelConfig(
        provider=ModelProviderType.ANTHROPIC,
        api_key=FAKE_KEY,
        model=FAKE_MODEL,
        max_tokens=1234,
    )
    provider = create_model_provider(config)

    assert isinstance(provider, AnthropicModelProvider)
    assert provider.model == FAKE_MODEL
    # Exactly one client was constructed, with the configured key, and it never
    # made a request (there is no real transport behind the stub).
    assert len(stub_anthropic_client.instances) == 1
    assert stub_anthropic_client.instances[0].api_key == FAKE_KEY


def test_anthropic_provider_accepts_injected_client() -> None:
    class _Client:
        messages = object()

    provider = AnthropicModelProvider(
        api_key=FAKE_KEY, model=FAKE_MODEL, client=_Client()
    )
    assert provider.model == FAKE_MODEL


def test_from_env_default_then_factory_is_mock() -> None:
    provider = create_model_provider(ModelConfig.from_env(env={}))
    assert isinstance(provider, MockModelProvider)


def test_from_env_anthropic_then_factory_builds_anthropic(stub_anthropic_client) -> None:
    config = ModelConfig.from_env(
        env={
            "MODEL_PROVIDER": "anthropic",
            "ANTHROPIC_API_KEY": FAKE_KEY,
            "ANTHROPIC_MODEL": FAKE_MODEL,
        }
    )
    provider = create_model_provider(config)
    assert isinstance(provider, AnthropicModelProvider)
    assert provider.model == FAKE_MODEL
