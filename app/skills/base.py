"""Agent Skill contracts.

The future skill runtime implements progressive disclosure:
  * Stage 1 (discovery): load only :class:`SkillMetadata`.
  * Stage 2 (activation): load the :class:`SkillDefinition` body when relevant.
  * Stage 3 (extension): load references / scripts only when needed.

Phase 0 defines the contracts only. No SKILL.md parsing, directory scanning, or
script execution happens yet.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Minimal descriptor loaded during discovery."""

    name: str
    description: str


class SkillDefinition(BaseModel):
    """Full skill payload loaded on activation."""

    metadata: SkillMetadata
    instructions: str
    references: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)


class SkillRegistry(ABC):
    """Abstract discovery + loading interface for Agent Skills."""

    @abstractmethod
    async def discover(self) -> list[SkillMetadata]:
        """Return metadata for every known skill (Stage 1)."""
        raise NotImplementedError

    @abstractmethod
    async def load(self, skill_name: str) -> SkillDefinition:
        """Return the full definition for one skill (Stage 2)."""
        raise NotImplementedError
