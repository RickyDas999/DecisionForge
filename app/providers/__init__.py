"""Model-provider abstraction and its concrete implementations.

Future agents depend only on :class:`ModelProvider`. The default provider is the
cost-free :class:`MockModelProvider`; :class:`AnthropicModelProvider` is used only
when explicitly selected.
"""

from app.providers.anthropic import AnthropicModelProvider
from app.providers.config import DEFAULT_MAX_TOKENS, ModelConfig, ModelProviderType
from app.providers.exceptions import (
    MockResponseExhaustedError,
    ModelConfigurationError,
    ModelProviderError,
    ModelResponseError,
    StructuredOutputError,
)
from app.providers.factory import create_model_provider
from app.providers.mock import MockCall, MockModelProvider
from app.providers.model import ModelProvider

__all__ = [
    "DEFAULT_MAX_TOKENS",
    "AnthropicModelProvider",
    "MockCall",
    "MockModelProvider",
    "MockResponseExhaustedError",
    "ModelConfig",
    "ModelConfigurationError",
    "ModelProvider",
    "ModelProviderError",
    "ModelProviderType",
    "ModelResponseError",
    "StructuredOutputError",
    "create_model_provider",
]
