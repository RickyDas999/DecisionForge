"""Tests for the deterministic search-context builder. No LLM."""

from __future__ import annotations

from app.models.search import SearchResponse, SearchResult
from app.tools.context import (
    MAX_CONTEXT_CHARS,
    MAX_RESULTS,
    MAX_SNIPPET_CHARS,
    build_search_context,
    combine_contexts,
)


def _result(i: int, snippet: str | None = None) -> SearchResult:
    return SearchResult(
        title=f"Title {i}",
        url=f"https://example.com/page-{i}",
        snippet=snippet or f"Snippet body number {i}",
        source=f"example{i}.com",
    )


def _response(n: int, query: str = "postgres vs mongodb") -> SearchResponse:
    return SearchResponse(query=query, results=[_result(i) for i in range(1, n + 1)])


def test_query_title_url_snippet_preserved() -> None:
    ctx = build_search_context(_response(2))
    assert "Search query: postgres vs mongodb" in ctx
    assert "Title: Title 1" in ctx and "Title: Title 2" in ctx
    assert "https://example.com/page-1" in ctx
    assert "Snippet body number 2" in ctx


def test_result_order_preserved() -> None:
    ctx = build_search_context(_response(3))
    assert ctx.index("Result 1") < ctx.index("Result 2") < ctx.index("Result 3")


def test_result_count_capped_at_max_results() -> None:
    ctx = build_search_context(_response(MAX_RESULTS + 3))
    assert f"Result {MAX_RESULTS}" in ctx
    assert f"Result {MAX_RESULTS + 1}" not in ctx


def test_snippet_cap_enforced() -> None:
    long_snippet = "x" * (MAX_SNIPPET_CHARS + 500)
    resp = SearchResponse(query="q", results=[_result(1, snippet=long_snippet)])
    ctx = build_search_context(resp)
    snippet_line = next(line for line in ctx.splitlines() if line.startswith("Snippet: "))
    rendered = snippet_line[len("Snippet: ") :]
    assert len(rendered) <= MAX_SNIPPET_CHARS
    assert rendered.endswith("…")


def test_total_context_cap_enforced() -> None:
    big = "y" * MAX_SNIPPET_CHARS
    resp = SearchResponse(
        query="q",
        results=[_result(i, snippet=big) for i in range(1, MAX_RESULTS + 1)],
    )
    ctx = build_search_context(resp)
    assert len(ctx) <= MAX_CONTEXT_CHARS + 200  # + the truncation marker line
    assert "[search context truncated" in ctx
    # at least one result always survives
    assert "Result 1" in ctx


def test_empty_results_are_represented_clearly() -> None:
    ctx = build_search_context(SearchResponse(query="nothing here", results=[]))
    assert "Search query: nothing here" in ctx
    assert "(no search results)" in ctx


def test_combine_user_and_search_keeps_both() -> None:
    combined = combine_contexts("User said this matters.", "Search query: q\n...")
    assert combined is not None
    assert "USER-PROVIDED CONTEXT" in combined
    assert "User said this matters." in combined
    assert "SEARCH EVIDENCE" in combined
    assert combined.index("USER-PROVIDED CONTEXT") < combined.index("SEARCH EVIDENCE")


def test_combine_user_only_returns_user_verbatim() -> None:
    assert combine_contexts("just the user", None) == "just the user"


def test_combine_search_only_is_labelled() -> None:
    combined = combine_contexts(None, "Search query: q")
    assert combined == "SEARCH EVIDENCE\nSearch query: q"


def test_combine_both_empty_is_none() -> None:
    assert combine_contexts(None, None) is None
    assert combine_contexts("  ", "") is None
