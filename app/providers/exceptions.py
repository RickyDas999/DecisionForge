"""Provider-layer exceptions.

Kept deliberately small and specific so callers (and later orchestration retry
policy) can branch on the failure kind instead of parsing strings.
"""

from __future__ import annotations


class ModelProviderError(Exception):
    """Base class for every model-provider failure."""


class ModelConfigurationError(ModelProviderError):
    """Configuration is missing or invalid for the selected provider.

    Examples: Anthropic selected without an API key or model; an unknown provider
    string; the ``anthropic`` package not installed when it is required.
    """


class ModelResponseError(ModelProviderError):
    """The provider returned a response with no usable content."""


class StructuredOutputError(ModelProviderError):
    """A structured response could not be parsed or validated.

    Raised for JSON parse errors and for Pydantic validation failures against the
    requested ``response_model``. The original exception is preserved as
    ``__cause__``.
    """


class MockResponseExhaustedError(ModelProviderError):
    """The ``MockModelProvider`` was asked for a response but none remain queued."""
