"""Workflow configuration.

These bounds are defined early because future iterative and parallel workflows
must always be bounded.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowConfig(BaseModel):
    """Tunable limits for a decision run."""

    max_research_iterations: int = Field(default=3, ge=1)
    max_validation_attempts: int = Field(default=2, ge=1)
    agent_timeout_seconds: int = Field(default=60, ge=1)
    max_parallel_researchers: int = Field(default=3, ge=1)
