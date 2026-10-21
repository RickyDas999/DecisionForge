"""Tests for search record/replay."""

from __future__ import annotations

import asyncio

import pytest

from app.models.search import SearchResponse, SearchResult
from app.providers.replay import ReplayMode
from app.tools.search import MockSearchProvider
from app.tools.search_replay import ReplaySearchProvider, SearchCassetteMissError


def _response(query: str) -> SearchResponse:
    return SearchResponse(query=query, results=[
        SearchResult(title="T", url="https://e.com/1", snippet="live snippet")
    ])


def test_auto_records_then_replay_serves_without_network(tmp_path) -> None:
    path = tmp_path / "search.json"
    inner = MockSearchProvider(responses=[_response("agents")])
    recorded = asyncio.run(ReplaySearchProvider(inner, path).search("agents"))
    assert len(inner.calls) == 1

    replay = ReplaySearchProvider(None, path, mode=ReplayMode.REPLAY)
    assert asyncio.run(replay.search("agents")) == recorded


def test_replay_miss_and_result_count_are_part_of_the_key(tmp_path) -> None:
    path = tmp_path / "search.json"
    asyncio.run(ReplaySearchProvider(MockSearchProvider(responses=[_response("q")]), path).search("q"))
    replay = ReplaySearchProvider(None, path, mode=ReplayMode.REPLAY)
    with pytest.raises(SearchCassetteMissError):
        asyncio.run(replay.search("other"))
    with pytest.raises(SearchCassetteMissError):
        asyncio.run(replay.search("q", max_results=3))


def test_record_mode_refreshes(tmp_path) -> None:
    path = tmp_path / "search.json"
    inner = MockSearchProvider(responses=[_response("q"), _response("q")])
    provider = ReplaySearchProvider(inner, path, mode=ReplayMode.RECORD)
    asyncio.run(provider.search("q"))
    asyncio.run(provider.search("q"))
    assert len(inner.calls) == 2


def test_recording_needs_an_inner_provider(tmp_path) -> None:
    with pytest.raises(ValueError):
        ReplaySearchProvider(None, tmp_path / "s.json", mode=ReplayMode.AUTO)
