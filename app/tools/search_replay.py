"""Record/replay for search, the companion to the model-call cassette.

Model calls replay only when their prompt is byte-identical, and a prompt
includes the search evidence. Live web results change from day to day, so a
research run recorded with live search would never replay. Recording the search
responses too (keyed by query and result count) makes the whole run replayable:
same query, same evidence, same prompt, same recorded answer, all at no cost.

Modes mirror :class:`app.providers.replay.ReplayMode`.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.search import SearchResponse
from app.providers.replay import ReplayMode
from app.tools.exceptions import SearchError
from app.tools.search import DEFAULT_MAX_RESULTS, SearchProvider

_CASSETTE_VERSION = 1

#: Default search cassette, kept next to the model-call cassette.
DEFAULT_SEARCH_CASSETTE = "cassettes/search.json"


class SearchCassetteMissError(SearchError):
    """Replay mode was asked for a query that was never recorded."""


class ReplaySearchProvider(SearchProvider):
    def __init__(
        self,
        inner: SearchProvider | None,
        cassette_path: str | Path = DEFAULT_SEARCH_CASSETTE,
        *,
        mode: ReplayMode = ReplayMode.AUTO,
    ) -> None:
        if mode is ReplayMode.OFF:
            raise ValueError("ReplaySearchProvider needs a mode other than 'off'")
        if inner is None and mode is not ReplayMode.REPLAY:
            raise ValueError(f"search replay mode {mode.value!r} needs a provider to record from")
        self._inner = inner
        self._path = Path(cassette_path)
        self._mode = mode
        self._entries: dict[str, dict] = self._load()

    async def search(self, query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> SearchResponse:
        key = f"{max_results}|{query.strip()}"
        entry = self._entries.get(key)
        if entry is not None and self._mode is not ReplayMode.RECORD:
            return SearchResponse.model_validate(entry)
        if self._mode is ReplayMode.REPLAY:
            raise SearchCassetteMissError(
                f"no recorded search for {query!r} in {self._path} (record it with a live run)"
            )
        response = await self._inner.search(query, max_results=max_results)  # type: ignore[union-attr]
        self._entries[key] = response.model_dump(mode="json")
        self._save()
        return response

    def _load(self) -> dict[str, dict]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if data.get("version") != _CASSETTE_VERSION:
            raise ValueError(f"unsupported search cassette version in {self._path}")
        return dict(data.get("entries", {}))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": _CASSETTE_VERSION, "entries": self._entries}
        self._path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
