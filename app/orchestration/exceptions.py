"""Deterministic dispatcher exceptions.

Kept small on purpose. Because ``AgentRoute`` is an enum, an invalid route
normally fails during structured-output parsing, long before dispatch.
"""

from __future__ import annotations

from app.models.routing import AgentRoute


class DispatchError(Exception):
    """Base class for deterministic dispatch failures."""


class MissingBriefContextError(DispatchError):
    """The brief route was selected but no usable context was supplied.

    The dispatcher raises this instead of inventing context, calling another
    agent, or retrying routing. The orchestrator call has already happened; no
    specialist call is made.
    """

    def __init__(self, message: str = "Brief requests require provided context.") -> None:
        super().__init__(message)


class UnexpectedRouteError(DispatchError):
    """Defensive: a routing decision carried a route the dispatcher cannot map."""

    def __init__(self, route: AgentRoute) -> None:
        self.route = route
        super().__init__(f"No specialist is wired for route: {route!r}")
