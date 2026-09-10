"""Agent Skill loading exceptions. Small on purpose."""

from __future__ import annotations


class SkillError(Exception):
    """Base class for skill discovery / loading failures."""


class SkillNotFoundError(SkillError):
    """No skill directory with the requested name exists."""


class InvalidSkillError(SkillError):
    """A skill exists but its ``SKILL.md`` is missing or has bad frontmatter."""


class SkillResourceNotFoundError(SkillError):
    """A requested reference file or script does not exist in the skill."""
