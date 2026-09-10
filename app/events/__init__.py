"""Synchronous, local execution-event recording (no queues, no bus)."""

from app.events.recorder import ExecutionRecorder

__all__ = ["ExecutionRecorder"]
