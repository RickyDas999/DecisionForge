"""Search provider abstraction and implementations.

A ``SearchProvider`` is a plain async function object that turns a query string
into a :class:`SearchResponse`. It knows nothing about ``ModelProvider``, agents,
Anthropic, skills, or the dispatcher. It performs no LLM calls.

- :class:`MockSearchProvider` — deterministic, offline, used by every test.
- :class:`DuckDuckGoSearchProvider` — optional, no-key, real. Imports the
  ``ddgs`` package lazily; nothing happens at import time or in ``__init__``.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from app.models.search import SearchResponse, SearchResult
from app.tools.exceptions import (
    MockSearchExhaustedError,
    SearchConfigurationError,
    SearchProviderError,
)

DEFAULT_MAX_RESULTS = 5


def _validate_query(query: str) -> str:
    if not isinstance(query, str) or not query.strip():
        raise SearchConfigurationError("search query must not be blank")
    return query.strip()


class SearchProvider(ABC):
    """Turn a query into a :class:`SearchResponse`. No LLM, no agents."""

    @abstractmethod
    async def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> SearchResponse:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mock
# --------------------------------------------------------------------------- #
@dataclass
class SearchCall:
    """One recorded call to a search provider."""

    query: str
    max_results: int


class MockSearchProvider(SearchProvider):
    """Replays queued :class:`SearchResponse` objects. Zero network I/O."""

    def __init__(self, *, responses: Sequence[SearchResponse] | None = None) -> None:
        self.responses: list[SearchResponse] = list(responses or [])
        self.calls: list[SearchCall] = []

    async def search(
        self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS
    ) -> SearchResponse:
        _validate_query(query)
        self.calls.append(SearchCall(query=query, max_results=max_results))
        if not self.responses:
            raise MockSearchExhaustedError(
                "MockSearchProvider has no queued responses left"
            )
        return self.responses.pop(0)


# --------------------------------------------------------------------------- #
# Real (optional, no-key)
# --------------------------------------------------------------------------- #
class DuckDuckGoSearchProvider(SearchProvider):
    """Free, no-key search via the ``ddgs`` package (lazy import).

    Construction does no work and makes no network request. The ``ddgs`` import
    and the network call happen only inside :meth:`search`.
    """

    def __init__(self, *, region: str = "wt-wt", safesearch: str = "moderate") -> None:
        self._region = region
        self._safesearch = safesearch

    async def search(
        self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS
    ) -> SearchResponse:
        cleaned = _validate_query(query)

        try:
            from ddgs import DDGS  # type: ignore[import-not-found]
        except ModuleNotFoundError as exc:
            raise SearchConfigurationError(
                "the 'ddgs' package is not installed; install it with "
                "`pip install -e \".[search]\"` to use DuckDuckGoSearchProvider"
            ) from exc

        try:
            raw = DDGS().text(
                cleaned,
                region=self._region,
                safesearch=self._safesearch,
                max_results=max_results,
            )
        except Exception as exc:  # ddgs raises a variety of runtime errors
            raise SearchProviderError(f"DuckDuckGo search failed: {exc}") from exc

        results = [
            _result_from_ddgs_item(item)
            for item in list(raw or [])
            if _usable_ddgs_item(item)
        ]
        return SearchResponse(query=cleaned, results=results[:max_results])


def _usable_ddgs_item(item: Mapping[str, object]) -> bool:
    title = str(item.get("title") or "").strip()
    url = str(item.get("href") or item.get("url") or "").strip()
    body = str(item.get("body") or item.get("snippet") or "").strip()
    return bool(title and url and body)


def _result_from_ddgs_item(item: Mapping[str, object]) -> SearchResult:
    url = str(item.get("href") or item.get("url") or "").strip()
    return SearchResult(
        title=str(item.get("title")).strip(),
        url=url,
        snippet=str(item.get("body") or item.get("snippet")).strip(),
        source=urlparse(url).netloc or None,
    )


# --------------------------------------------------------------------------- #
# Config + factory
# --------------------------------------------------------------------------- #
class SearchProviderType(str, Enum):
    MOCK = "mock"
    DUCKDUCKGO = "duckduckgo"


class SearchConfig(BaseModel):
    """Selects the search provider. Defaults to offline mock."""

    provider: SearchProviderType = SearchProviderType.MOCK
    max_results: int = Field(default=DEFAULT_MAX_RESULTS, ge=1, le=10)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SearchConfig":
        """Read ``SEARCH_PROVIDER`` (default ``mock``). Never enables real search
        implicitly."""
        source = os.environ if env is None else env
        raw = (source.get("SEARCH_PROVIDER") or "mock").strip().lower() or "mock"
        try:
            provider = SearchProviderType(raw)
        except ValueError as exc:
            allowed = ", ".join(p.value for p in SearchProviderType)
            raise SearchConfigurationError(
                f"Unknown SEARCH_PROVIDER {raw!r}; expected one of: {allowed}"
            ) from exc
        return cls(provider=provider)


def create_search_provider(config: SearchConfig | None = None) -> SearchProvider:
    """Build the configured provider. Makes no network call."""
    config = config or SearchConfig()
    if config.provider is SearchProviderType.MOCK:
        return MockSearchProvider()
    if config.provider is SearchProviderType.DUCKDUCKGO:
        return DuckDuckGoSearchProvider()
    raise SearchConfigurationError(  # pragma: no cover - enum is exhaustive
        f"Unsupported search provider: {config.provider!r}"
    )
