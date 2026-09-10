"""Deterministic tool layer.

Tools are ordinary Python. They make zero LLM calls and invoke zero agents. The
search tool gathers external evidence *before* the single specialist call and
feeds it in through ``provided_context``.
"""

from app.tools.base import BaseTool, ToolResult
from app.tools.context import (
    MAX_CONTEXT_CHARS,
    MAX_RESULTS,
    MAX_SNIPPET_CHARS,
    build_search_context,
    combine_contexts,
)
from app.tools.exceptions import (
    MockSearchExhaustedError,
    SearchConfigurationError,
    SearchError,
    SearchProviderError,
)
from app.tools.policy import SEARCH_ENABLED_ROUTES, search_enabled_for_route
from app.tools.search import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchCall,
    SearchConfig,
    SearchProvider,
    SearchProviderType,
    create_search_provider,
)

__all__ = [
    "MAX_CONTEXT_CHARS",
    "MAX_RESULTS",
    "MAX_SNIPPET_CHARS",
    "SEARCH_ENABLED_ROUTES",
    "BaseTool",
    "DuckDuckGoSearchProvider",
    "MockSearchExhaustedError",
    "MockSearchProvider",
    "SearchCall",
    "SearchConfig",
    "SearchConfigurationError",
    "SearchError",
    "SearchProvider",
    "SearchProviderError",
    "SearchProviderType",
    "ToolResult",
    "build_search_context",
    "combine_contexts",
    "create_search_provider",
    "search_enabled_for_route",
]
