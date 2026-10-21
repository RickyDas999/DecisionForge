"""Tests for the record/replay provider. No network."""

from __future__ import annotations

import asyncio

import pytest

from app.models.routing import AgentRoute, RoutingDecision
from app.providers.exceptions import ModelConfigurationError
from app.providers.mock import MockModelProvider
from app.providers.replay import CassetteMissError, ReplayMode, ReplayModelProvider
from app.providers.usage import CallSource, UsageLedger, metered

MODEL = "claude-haiku-5-5"


def _decision() -> RoutingDecision:
    return RoutingDecision(route=AgentRoute.COMPARISON, reasoning="compares two options")


def _ask(provider, user="Postgres or Mongo?"):
    return asyncio.run(provider.generate_structured(
        system_prompt="route it", user_prompt=user, response_model=RoutingDecision
    ))


def test_auto_records_then_replays_without_calling_inner(tmp_path) -> None:
    path = tmp_path / "c.json"
    inner = MockModelProvider(structured_responses=[_decision()])
    first = _ask(ReplayModelProvider(inner, path, mode=ReplayMode.AUTO, model=MODEL))
    assert len(inner.calls) == 1 and path.exists()

    # A fresh provider (new process) replays from disk; inner is not consulted.
    replay = ReplayModelProvider(None, path, mode=ReplayMode.REPLAY, model=MODEL)
    ledger = UsageLedger()
    with metered(ledger):
        second = _ask(replay)
    assert second == first
    assert ledger.calls[0].source is CallSource.REPLAYED
    assert ledger.calls[0].cost_usd == 0.0


def test_replay_miss_raises(tmp_path) -> None:
    replay = ReplayModelProvider(None, tmp_path / "c.json", mode=ReplayMode.REPLAY, model=MODEL)
    with pytest.raises(CassetteMissError):
        _ask(replay)


def test_different_prompt_or_model_is_a_miss(tmp_path) -> None:
    path = tmp_path / "c.json"
    _ask(ReplayModelProvider(
        MockModelProvider(structured_responses=[_decision()]), path,
        mode=ReplayMode.AUTO, model=MODEL,
    ))
    with pytest.raises(CassetteMissError):
        _ask(ReplayModelProvider(None, path, mode=ReplayMode.REPLAY, model=MODEL), user="other")
    with pytest.raises(CassetteMissError):
        _ask(ReplayModelProvider(None, path, mode=ReplayMode.REPLAY, model="claude-opus-5-5"))


def test_record_mode_always_calls_inner(tmp_path) -> None:
    path = tmp_path / "c.json"
    inner = MockModelProvider(structured_responses=[_decision(), _decision()])
    provider = ReplayModelProvider(inner, path, mode=ReplayMode.RECORD, model=MODEL)
    _ask(provider)
    _ask(provider)
    assert len(inner.calls) == 2


def test_text_round_trip(tmp_path) -> None:
    path = tmp_path / "c.json"
    rec = ReplayModelProvider(MockModelProvider(text_responses=["hi"]), path,
                              mode=ReplayMode.AUTO, model=MODEL)
    asyncio.run(rec.generate_text(system_prompt="s", user_prompt="u"))
    rep = ReplayModelProvider(None, path, mode=ReplayMode.REPLAY, model=MODEL)
    assert asyncio.run(rep.generate_text(system_prompt="s", user_prompt="u")) == "hi"


def test_non_replay_mode_requires_inner(tmp_path) -> None:
    with pytest.raises(ModelConfigurationError):
        ReplayModelProvider(None, tmp_path / "c.json", mode=ReplayMode.AUTO, model=MODEL)
