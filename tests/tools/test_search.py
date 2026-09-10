"""Tests for the search provider layer. Mock only; zero network."""

from __future__ import annotations

import asyncio
import sys

import pytest

from app.models.search import SearchResponse, SearchResult
from app.tools.exceptions import (
    MockSearchExhaustedError,
    SearchConfigurationError,
)
from app.tools.search import (
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchConfig,
    SearchProviderType,
    create_search_provider,
)


def _response(query: str = "q", n: int = 2) -> SearchResponse:
    return SearchResponse(
        query=query,
        results=[
            SearchResult(
                title=f"Title {i}",
                url=f"https://example.com/{i}",
                snippet=f"Snippet {i}",
                source="example.com",
            )
            for i in range(1, n + 1)
        ],
    )


def test_mock_returns_configured_response() -> None:
    provider = MockSearchProvider(responses=[_response("vector databases")])
    result = asyncio.run(provider.search("vector databases"))
    assert result.query == "vector databases"
    assert len(result.results) == 2


def test_mock_consumes_responses_in_order() -> None:
    provider = MockSearchProvider(responses=[_response("a"), _response("b")])
    first = asyncio.run(provider.search("a"))
    second = asyncio.run(provider.search("b"))
    assert first.query == "a"
    assert second.query == "b"


def test_mock_records_call_history() -> None:
    provider = MockSearchProvider(responses=[_response()])
    asyncio.run(provider.search("compare X and Y", max_results=3))
    assert len(provider.calls) == 1
    assert provider.calls[0].query == "compare X and Y"
    assert provider.calls[0].max_results == 3


def test_mock_exhaustion_raises() -> None:
    provider = MockSearchProvider()
    with pytest.raises(MockSearchExhaustedError):
        asyncio.run(provider.search("q"))


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_blank_query_is_rejected(blank: str) -> None:
    provider = MockSearchProvider(responses=[_response()])
    with pytest.raises(SearchConfigurationError):
        asyncio.run(provider.search(blank))
    # a rejected query is not recorded as a call
    assert provider.calls == []


def test_duckduckgo_construction_makes_no_network_call() -> None:
    before = set(sys.modules)
    provider = DuckDuckGoSearchProvider()
    assert isinstance(provider, DuckDuckGoSearchProvider)
    # constructing it must not import ddgs or make any request
    assert "ddgs" not in sys.modules or "ddgs" in before


def test_duckduckgo_missing_dependency_raises_configuration_error() -> None:
    # ddgs is not installed in the test environment; calling search() should
    # fail loudly with a configuration error, not a network error.
    if "ddgs" in sys.modules:  # pragma: no cover - only if someone installed it
        pytest.skip("ddgs is installed in this environment")
    provider = DuckDuckGoSearchProvider()
    with pytest.raises(SearchConfigurationError):
        asyncio.run(provider.search("anything"))


def test_default_config_and_factory_are_mock() -> None:
    assert SearchConfig().provider is SearchProviderType.MOCK
    assert isinstance(create_search_provider(), MockSearchProvider)


def test_from_env_default_is_mock() -> None:
    assert SearchConfig.from_env(env={}).provider is SearchProviderType.MOCK


def test_from_env_duckduckgo_is_not_auto_enabled_without_selection() -> None:
    # Only an explicit SEARCH_PROVIDER=duckduckgo selects real search.
    assert SearchConfig.from_env(env={"OTHER": "x"}).provider is SearchProviderType.MOCK
    cfg = SearchConfig.from_env(env={"SEARCH_PROVIDER": "duckduckgo"})
    assert cfg.provider is SearchProviderType.DUCKDUCKGO


def test_from_env_unknown_provider_raises() -> None:
    with pytest.raises(SearchConfigurationError):
        SearchConfig.from_env(env={"SEARCH_PROVIDER": "serpapi"})


def test_factory_duckduckgo_builds_without_network() -> None:
    provider = create_search_provider(
        SearchConfig(provider=SearchProviderType.DUCKDUCKGO)
    )
    assert isinstance(provider, DuckDuckGoSearchProvider)
