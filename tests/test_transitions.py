"""Tests for explicit workflow state-transition validation."""

from __future__ import annotations

import pytest

from app.models.state import RunStatus
from app.orchestration.transitions import InvalidStateTransition, validate_transition

VALID_TRANSITIONS = [
    (RunStatus.CREATED, RunStatus.PLANNING),
    (RunStatus.PLANNING, RunStatus.RESEARCHING),
    (RunStatus.RESEARCHING, RunStatus.JUDGING),
    (RunStatus.JUDGING, RunStatus.RESEARCHING),
    (RunStatus.JUDGING, RunStatus.ANALYZING),
    (RunStatus.ANALYZING, RunStatus.WRITING),
    (RunStatus.WRITING, RunStatus.VALIDATING),
    (RunStatus.VALIDATING, RunStatus.WRITING),
    (RunStatus.VALIDATING, RunStatus.COMPLETED),
]

INVALID_TRANSITIONS = [
    (RunStatus.CREATED, RunStatus.WRITING),
    (RunStatus.RESEARCHING, RunStatus.COMPLETED),
    (RunStatus.COMPLETED, RunStatus.PLANNING),
    (RunStatus.FAILED, RunStatus.PLANNING),
]

ACTIVE_STATES = [
    RunStatus.CREATED,
    RunStatus.PLANNING,
    RunStatus.RESEARCHING,
    RunStatus.JUDGING,
    RunStatus.ANALYZING,
    RunStatus.WRITING,
    RunStatus.VALIDATING,
]


@pytest.mark.parametrize(("current", "nxt"), VALID_TRANSITIONS)
def test_valid_transitions_pass(current: RunStatus, nxt: RunStatus) -> None:
    assert validate_transition(current, nxt) is None


@pytest.mark.parametrize(("current", "nxt"), INVALID_TRANSITIONS)
def test_invalid_transitions_raise(current: RunStatus, nxt: RunStatus) -> None:
    with pytest.raises(InvalidStateTransition):
        validate_transition(current, nxt)


@pytest.mark.parametrize("current", ACTIVE_STATES)
def test_any_active_state_may_fail(current: RunStatus) -> None:
    assert validate_transition(current, RunStatus.FAILED) is None


@pytest.mark.parametrize("current", [RunStatus.COMPLETED, RunStatus.FAILED])
def test_terminal_states_have_no_outgoing_transitions(current: RunStatus) -> None:
    for nxt in RunStatus:
        with pytest.raises(InvalidStateTransition):
            validate_transition(current, nxt)


def test_exception_carries_states() -> None:
    with pytest.raises(InvalidStateTransition) as excinfo:
        validate_transition(RunStatus.CREATED, RunStatus.COMPLETED)
    assert excinfo.value.current_status is RunStatus.CREATED
    assert excinfo.value.next_status is RunStatus.COMPLETED
