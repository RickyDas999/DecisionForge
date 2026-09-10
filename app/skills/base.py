"""Agent Skill contracts.

Progressive disclosure:
  * Stage 1 (discovery): :class:`SkillMetadata` only — name + description.
  * Stage 2 (activation): :class:`SkillDefinition` — metadata + the SKILL.md body
    + the *names* of available references and scripts (not their contents).
  * Stage 3 (extension): reference contents / script paths, fetched only on
    explicit request via registry methods.

Skill loading is ordinary deterministic file I/O. It never calls an LLM, a
``ModelProvider``, or an agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class SkillMetadata(BaseModel):
    """Discovery-level descriptor."""

    name: str
    description: str


class SkillDefinition(BaseModel):
    """Activated skill data.

    ``references`` and ``scripts`` are filenames only. Their contents stay on
    disk until explicitly requested (Stage 3).
    """

    metadata: SkillMetadata
    instructions: str
    references: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.metadata.name


class SkillRegistry(ABC):
    """Discovery + activation interface for Agent Skills (synchronous file I/O)."""

    @abstractmethod
    def discover(self) -> list[SkillMetadata]:
        """Stage 1: return name + description for every known skill."""
        raise NotImplementedError

    @abstractmethod
    def load(self, skill_name: str) -> SkillDefinition:
        """Stage 2: return the activated definition for one skill."""
        raise NotImplementedError
