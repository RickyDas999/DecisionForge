"""Zero-cost demo of the deterministic search-tool layer.

Default: MockSearchProvider only — no network, no ModelProvider, no agents.

    python scripts/tools_demo.py

Optional (USER only — never run by Claude Code): a single live DuckDuckGo search.

    python scripts/tools_demo.py --real-search "current vector database options"

The --real-search path performs a live external web search. It makes NO Anthropic
call. It requires `pip install -e ".[search]"`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.models.search import SearchResponse, SearchResult
from app.tools.context import (
    MAX_CONTEXT_CHARS,
    MAX_RESULTS,
    MAX_SNIPPET_CHARS,
    build_search_context,
    combine_contexts,
)
from app.tools.search import DuckDuckGoSearchProvider, MockSearchProvider

_MOCK_RESPONSE = SearchResponse(
    query="PostgreSQL vs MongoDB for a small SaaS startup",
    results=[
        SearchResult(
            title="Choosing a database for an early-stage SaaS",
            url="https://example.com/db-choice",
            snippet=(
                "Relational databases suit transactional SaaS data with clear "
                "schemas; document stores trade consistency for flexibility."
            ),
            source="example.com",
        ),
        SearchResult(
            title="PostgreSQL JSONB vs MongoDB documents",
            url="https://example.com/jsonb-vs-documents",
            snippet=(
                "PostgreSQL's JSONB narrows the flexibility gap while keeping "
                "constraints, joins and transactions."
            ),
            source="example.com",
        ),
    ],
)


def _print_search(response: SearchResponse) -> None:
    print(f"SearchResponse.query : {response.query}")
    print(f"SearchResponse.results: {len(response.results)}")
    print()
    print("--- build_search_context() output ---")
    context = build_search_context(response)
    print(context)
    print()
    print(f"(context length: {len(context)} chars; caps: {MAX_RESULTS} results, "
          f"{MAX_SNIPPET_CHARS}/snippet, ~{MAX_CONTEXT_CHARS} total)")
    print()
    print("--- combine_contexts('user note', <search>) ---")
    print(combine_contexts("User note: we already run Postgres in another service.", context))


def _run_mock() -> int:
    print("Running with MockSearchProvider (no network, no model calls).\n")
    provider = MockSearchProvider(responses=[_MOCK_RESPONSE])
    response = asyncio.run(provider.search(_MOCK_RESPONSE.query))
    _print_search(response)
    print(f"\nMockSearchProvider.calls: {[(c.query, c.max_results) for c in provider.calls]}")
    print("ModelProvider calls made by this demo: 0")
    return 0


def _run_real(query: str) -> int:
    print("This performs a live external web search (no Anthropic call).\n")
    provider = DuckDuckGoSearchProvider()
    response = asyncio.run(provider.search(query))
    _print_search(response)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="Query for --real-search.")
    parser.add_argument(
        "--real-search",
        action="store_true",
        help="Perform ONE live DuckDuckGo search (no Anthropic call).",
    )
    args = parser.parse_args(argv)

    if not args.real_search:
        return _run_mock()

    if not args.query:
        print('--real-search requires a query argument.', file=sys.stderr)
        return 2
    return _run_real(args.query)


if __name__ == "__main__":
    raise SystemExit(main())
