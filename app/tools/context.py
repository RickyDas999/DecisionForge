"""Deterministic conversion of search results into specialist ``provided_context``.

No LLM, no ``ModelProvider``, no semantic ranking, no summarization. Just string
assembly with hard, deterministic size limits so Claude's input stays small.
"""

from __future__ import annotations

from app.models.search import SearchResponse

#: At most this many results are rendered, regardless of how many were returned.
MAX_RESULTS = 5
#: Each snippet is truncated to this many characters.
MAX_SNIPPET_CHARS = 500
#: The whole rendered search block is capped near this many characters; trailing
#: results are dropped whole (plus a one-line marker) to stay close to it. This
#: is deliberately tight to keep Claude's input tokens small.
MAX_CONTEXT_CHARS = 2500

_ELLIPSIS = "…"
_USER_HEADER = "USER-PROVIDED CONTEXT"
_SEARCH_HEADER = "SEARCH EVIDENCE"


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 0)].rstrip() + _ELLIPSIS


def build_search_context(response: SearchResponse) -> str:
    """Render a :class:`SearchResponse` as compact, size-bounded plain text."""
    header = f"Search query: {response.query.strip()}"
    considered = list(response.results[:MAX_RESULTS])
    if not considered:
        return f"{header}\n\n(no search results)"

    blocks: list[str] = []
    used = len(header)
    for index, result in enumerate(considered, start=1):
        lines = [f"Result {index}", f"Title: {result.title.strip()}"]
        if result.source and result.source.strip():
            lines.append(f"Source: {result.source.strip()}")
        lines.append(f"URL: {result.url.strip()}")
        lines.append(f"Snippet: {_truncate(result.snippet, MAX_SNIPPET_CHARS)}")
        block = "\n".join(lines)

        if blocks and used + len(block) + 2 > MAX_CONTEXT_CHARS:
            break
        blocks.append(block)
        used += len(block) + 2

    body = "\n\n".join([header, *blocks])
    if len(blocks) < len(considered):
        body += (
            f"\n\n[search context truncated: {len(blocks)} of "
            f"{len(considered)} results shown]"
        )
    return body


def combine_contexts(
    user_context: str | None,
    search_context: str | None,
) -> str | None:
    """Merge user-supplied context with search-derived context, deterministically.

    User content is never discarded or reordered. Returns ``None`` when both are
    empty.
    """
    user = user_context.strip() if user_context and user_context.strip() else None
    search = search_context.strip() if search_context and search_context.strip() else None

    if user and search:
        return f"{_USER_HEADER}\n{user}\n\n{_SEARCH_HEADER}\n{search}"
    if user:
        return user
    if search:
        return f"{_SEARCH_HEADER}\n{search}"
    return None
