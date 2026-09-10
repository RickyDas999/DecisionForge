"""Tests for :class:`SQLiteRunRepository`. Temp DB files only; no network."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.persistence import (
    EventType,
    ExecutionEvent,
    RunRecord,
    RunStatus,
)
from app.models.routing import AgentRoute
from app.persistence.sqlite import SQLiteRunRepository


@pytest.fixture
def repo(tmp_path) -> SQLiteRunRepository:
    return SQLiteRunRepository(tmp_path / "runs.db")


def _record(run_id: str = "run-1", request: str = "Research vector DBs.") -> RunRecord:
    return RunRecord(run_id=run_id, user_request=request, status=RunStatus.STARTED)


def test_schema_initializes_and_is_idempotent(tmp_path) -> None:
    path = tmp_path / "nested" / "dir" / "runs.db"
    SQLiteRunRepository(path)
    second = SQLiteRunRepository(path)  # re-init must not raise
    assert path.is_file()
    assert second.list_recent_runs() == []


def test_create_and_fetch_run(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    fetched = repo.get_run("run-1")
    assert fetched is not None
    assert fetched.user_request == "Research vector DBs."
    assert fetched.status is RunStatus.STARTED
    assert fetched.search_used is False
    assert fetched.created_at.tzinfo is not None


def test_get_missing_run_returns_none(repo: SQLiteRunRepository) -> None:
    assert repo.get_run("nope") is None


def test_set_route_updates_status_and_fields(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    repo.set_route(
        "run-1",
        route=AgentRoute.COMPARISON,
        routing_reasoning="explicit comparison",
        selected_specialist="ComparisonAgent",
    )
    fetched = repo.get_run("run-1")
    assert fetched.route is AgentRoute.COMPARISON
    assert fetched.routing_reasoning == "explicit comparison"
    assert fetched.selected_specialist == "ComparisonAgent"
    assert fetched.status is RunStatus.ROUTED


def test_mark_completed_stores_result_json(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    repo.mark_completed("run-1", result_json='{"route": "research"}')
    fetched = repo.get_run("run-1")
    assert fetched.status is RunStatus.COMPLETED
    assert fetched.result_json == '{"route": "research"}'
    assert fetched.completed_at is not None
    assert fetched.completed_at.tzinfo is not None


def test_mark_failed_stores_error(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    repo.mark_failed("run-1", error="SearchProviderError: backend down")
    fetched = repo.get_run("run-1")
    assert fetched.status is RunStatus.FAILED
    assert fetched.error == "SearchProviderError: backend down"
    assert fetched.completed_at is not None


def test_set_search_used(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    repo.set_search_used("run-1", True)
    assert repo.get_run("run-1").search_used is True


def test_list_recent_runs_newest_first(repo: SQLiteRunRepository) -> None:
    early = RunRecord(
        run_id="a",
        user_request="a",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    late = RunRecord(
        run_id="b",
        user_request="b",
        created_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    repo.create_run(early)
    repo.create_run(late)
    ids = [r.run_id for r in repo.list_recent_runs()]
    assert ids == ["b", "a"]
    assert [r.run_id for r in repo.list_recent_runs(limit=1)] == ["b"]


def test_append_and_fetch_events_in_chronological_order(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    for i, et in enumerate(
        [EventType.RUN_STARTED, EventType.ROUTE_SELECTED, EventType.RUN_COMPLETED]
    ):
        repo.append_event(
            ExecutionEvent(
                run_id="run-1",
                event_type=et,
                message=f"m{i}",
                metadata={"n": i},
                timestamp=datetime(2024, 1, 1, 0, 0, i, tzinfo=timezone.utc),
            )
        )
    events = repo.get_events("run-1")
    assert [e.event_type for e in events] == [
        EventType.RUN_STARTED,
        EventType.ROUTE_SELECTED,
        EventType.RUN_COMPLETED,
    ]
    assert events[1].metadata == {"n": 1}  # JSON round-trip
    assert all(e.timestamp.tzinfo is not None for e in events)


def test_same_timestamp_events_keep_insertion_order(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record())
    stamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for et in (EventType.SEARCH_STARTED, EventType.SEARCH_COMPLETED):
        repo.append_event(
            ExecutionEvent(run_id="run-1", event_type=et, timestamp=stamp)
        )
    assert [e.event_type for e in repo.get_events("run-1")] == [
        EventType.SEARCH_STARTED,
        EventType.SEARCH_COMPLETED,
    ]


def test_events_are_scoped_per_run(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record("run-1"))
    repo.create_run(_record("run-2"))
    repo.append_event(ExecutionEvent(run_id="run-1", event_type=EventType.RUN_STARTED))
    repo.append_event(ExecutionEvent(run_id="run-2", event_type=EventType.RUN_STARTED))
    repo.append_event(ExecutionEvent(run_id="run-2", event_type=EventType.RUN_COMPLETED))
    assert len(repo.get_events("run-1")) == 1
    assert len(repo.get_events("run-2")) == 2


def test_multiple_runs_are_independent(repo: SQLiteRunRepository) -> None:
    repo.create_run(_record("run-1", "req one"))
    repo.create_run(_record("run-2", "req two"))
    repo.mark_completed("run-1", result_json="{}")
    repo.mark_failed("run-2", error="boom")
    assert repo.get_run("run-1").status is RunStatus.COMPLETED
    assert repo.get_run("run-2").status is RunStatus.FAILED
    assert repo.get_run("run-1").user_request == "req one"
