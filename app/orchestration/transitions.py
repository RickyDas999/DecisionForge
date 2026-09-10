"""Explicit workflow state-transition validation.

Deterministic Python owns state transitions. This module defines which
``RunStatus`` moves are legal; the orchestration engine itself is a later phase.
"""

from __future__ import annotations

from app.models.state import RunStatus

#: Nonterminal states from which the run may still transition to FAILED.
_ACTIVE_STATES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.CREATED,
        RunStatus.PLANNING,
        RunStatus.RESEARCHING,
        RunStatus.JUDGING,
        RunStatus.ANALYZING,
        RunStatus.WRITING,
        RunStatus.VALIDATING,
    }
)

#: Terminal states: no outgoing transitions.
_TERMINAL_STATES: frozenset[RunStatus] = frozenset(
    {RunStatus.COMPLETED, RunStatus.FAILED}
)

#: Allowed "happy path" and loop-back transitions (excluding -> FAILED).
_ALLOWED_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset({RunStatus.PLANNING}),
    RunStatus.PLANNING: frozenset({RunStatus.RESEARCHING}),
    RunStatus.RESEARCHING: frozenset({RunStatus.JUDGING}),
    RunStatus.JUDGING: frozenset({RunStatus.RESEARCHING, RunStatus.ANALYZING}),
    RunStatus.ANALYZING: frozenset({RunStatus.WRITING}),
    RunStatus.WRITING: frozenset({RunStatus.VALIDATING}),
    RunStatus.VALIDATING: frozenset({RunStatus.WRITING, RunStatus.COMPLETED}),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
}


class InvalidStateTransition(Exception):
    """Raised when a requested ``RunStatus`` transition is not allowed."""

    def __init__(self, current_status: RunStatus, next_status: RunStatus) -> None:
        self.current_status = current_status
        self.next_status = next_status
        super().__init__(
            f"Invalid state transition: {current_status.value} -> {next_status.value}"
        )


def validate_transition(current_status: RunStatus, next_status: RunStatus) -> None:
    """Return ``None`` for a valid transition; raise ``InvalidStateTransition`` otherwise.

    Rules:
      * Any active (nonterminal) state may transition to ``FAILED``.
      * Terminal states (``COMPLETED``, ``FAILED``) have no outgoing transitions.
      * Otherwise the move must appear in ``_ALLOWED_TRANSITIONS``.
    """
    if current_status in _TERMINAL_STATES:
        raise InvalidStateTransition(current_status, next_status)

    if next_status is RunStatus.FAILED and current_status in _ACTIVE_STATES:
        return

    if next_status in _ALLOWED_TRANSITIONS.get(current_status, frozenset()):
        return

    raise InvalidStateTransition(current_status, next_status)
