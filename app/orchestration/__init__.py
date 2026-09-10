"""Deterministic orchestration.

Phase 4 adds the single-hop dispatcher. The ``config`` and ``transitions``
modules are legacy Phase 0 scaffolding for the removed multi-stage pipeline
(kept only for existing tests).
"""

from app.orchestration.config import WorkflowConfig
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.orchestration.exceptions import (
    DispatchError,
    MissingBriefContextError,
    UnexpectedRouteError,
)
from app.orchestration.transitions import InvalidStateTransition, validate_transition

__all__ = [
    "DecisionForgeDispatcher",
    "DispatchError",
    "InvalidStateTransition",
    "MissingBriefContextError",
    "UnexpectedRouteError",
    "WorkflowConfig",
    "validate_transition",
]
