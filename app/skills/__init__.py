"""Local Agent Skills: contracts, a file-backed registry, and route mapping.

Skill loading is deterministic file I/O — it never invokes an LLM or an agent and
never increases the two-LLM-call ceiling.
"""

from app.skills.base import SkillDefinition, SkillMetadata, SkillRegistry
from app.skills.exceptions import (
    InvalidSkillError,
    SkillError,
    SkillNotFoundError,
    SkillResourceNotFoundError,
)
from app.skills.local import DEFAULT_SKILL_ROOT, LocalSkillRegistry
from app.skills.mapping import ROUTE_SKILLS, skill_for_route

__all__ = [
    "DEFAULT_SKILL_ROOT",
    "ROUTE_SKILLS",
    "InvalidSkillError",
    "LocalSkillRegistry",
    "SkillDefinition",
    "SkillError",
    "SkillMetadata",
    "SkillNotFoundError",
    "SkillRegistry",
    "SkillResourceNotFoundError",
    "skill_for_route",
]
