"""Search-tool exceptions. Small and specific.

A search failure stops the request. It never triggers a retry, a fallback
provider, a re-route, or another agent.
"""

from __future__ import annotations


class SearchError(Exception):
    """Base class for search-tool failures."""


class SearchConfigurationError(SearchError):
    """Search is misconfigured (unknown provider, missing optional dependency,
    or a blank query)."""


class SearchProviderError(SearchError):
    """A configured search provider failed to return results."""


class MockSearchExhaustedError(SearchError):
    """The ``MockSearchProvider`` was asked for a response but none remain."""
