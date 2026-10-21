"""A recorded eval (model calls + search) replays identically with no network."""

from __future__ import annotations

import asyncio

from app.evaluation.golden import load_golden_set, pick_balanced
from app.evaluation.harness import run_eval
from app.evaluation.report import to_dict
from app.providers.replay import ReplayMode, ReplayModelProvider
from app.tools.search_replay import ReplaySearchProvider
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider


def _run(model, search):
    return asyncio.run(run_eval(pick_balanced(load_golden_set()), model, label="rt",
                                search_provider=search))


def test_recorded_run_replays_identically(tmp_path) -> None:
    calls, searches = tmp_path / "calls.json", tmp_path / "search.json"
    recorded = _run(
        ReplayModelProvider(DemoModelProvider(), calls, mode=ReplayMode.AUTO, model="claude-haiku-5-5"),
        ReplaySearchProvider(DemoSearchProvider(), searches, mode=ReplayMode.AUTO),
    )
    replayed = _run(
        ReplayModelProvider(None, calls, mode=ReplayMode.REPLAY, model="claude-haiku-5-5"),
        ReplaySearchProvider(None, searches, mode=ReplayMode.REPLAY),
    )
    assert all(r.outcome.error is None for r in replayed.results)
    strip = lambda d: [{k: v for k, v in c.items() if k != "latency_ms"} for c in d["cases"]]
    assert strip(to_dict(replayed)) == strip(to_dict(recorded))
