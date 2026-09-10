"""Local, file-backed :class:`SkillRegistry`.

Reads a ``skills/`` directory tree:

    skills/<skill-name>/SKILL.md          (YAML frontmatter + Markdown body)
    skills/<skill-name>/references/*.md    (Stage 3, loaded on request)
    skills/<skill-name>/scripts/*.py       (Stage 3, path returned on request)

Pure deterministic file I/O. No LLM, no ``ModelProvider``, no network.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.skills.base import SkillDefinition, SkillMetadata, SkillRegistry
from app.skills.exceptions import (
    InvalidSkillError,
    SkillNotFoundError,
    SkillResourceNotFoundError,
)

#: Default location of the skills tree (repo-root ``skills/``), resolved relative
#: to this package so it works regardless of the current working directory.
DEFAULT_SKILL_ROOT = Path(__file__).resolve().parents[2] / "skills"

_REFERENCES_DIR = "references"
_SCRIPTS_DIR = "scripts"


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Split a ``---``-delimited YAML frontmatter block from a Markdown body.

    Raises :class:`InvalidSkillError` if the frontmatter block is missing or not
    a YAML mapping.
    """
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        raise InvalidSkillError("SKILL.md is missing its '---' frontmatter block")

    lines = stripped.splitlines()
    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing = index
            break
    if closing is None:
        raise InvalidSkillError("SKILL.md frontmatter block is not closed with '---'")

    raw_yaml = "\n".join(lines[1:closing])
    body = "\n".join(lines[closing + 1 :]).lstrip("\n")

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise InvalidSkillError(f"SKILL.md frontmatter is not valid YAML: {exc}") from exc

    if not isinstance(parsed, dict):
        raise InvalidSkillError("SKILL.md frontmatter must be a YAML mapping")

    return parsed, body


def _metadata_from_frontmatter(frontmatter: dict, *, skill_dir_name: str) -> SkillMetadata:
    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if not isinstance(name, str) or not name.strip():
        raise InvalidSkillError(
            f"skill {skill_dir_name!r}: frontmatter is missing a non-empty 'name'"
        )
    if not isinstance(description, str) or not description.strip():
        raise InvalidSkillError(
            f"skill {skill_dir_name!r}: frontmatter is missing a non-empty 'description'"
        )
    return SkillMetadata(name=name.strip(), description=" ".join(description.split()))


class LocalSkillRegistry(SkillRegistry):
    """Discover and activate skills from a local directory tree."""

    def __init__(self, root: Path | str = DEFAULT_SKILL_ROOT) -> None:
        self.root = Path(root)

    # -- Stage 1: discovery ------------------------------------------------- #
    def discover(self) -> list[SkillMetadata]:
        if not self.root.is_dir():
            return []
        found: list[SkillMetadata] = []
        for child in sorted(self.root.iterdir()):
            skill_md = child / "SKILL.md"
            if not (child.is_dir() and skill_md.is_file()):
                continue
            frontmatter, _ = split_frontmatter(skill_md.read_text(encoding="utf-8"))
            found.append(_metadata_from_frontmatter(frontmatter, skill_dir_name=child.name))
        return found

    # -- Stage 2: activation --------------------------------------------- #
    def load(self, skill_name: str) -> SkillDefinition:
        skill_dir = self._skill_dir(skill_name)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            raise InvalidSkillError(f"skill {skill_name!r} has no SKILL.md")

        frontmatter, body = split_frontmatter(skill_md.read_text(encoding="utf-8"))
        metadata = _metadata_from_frontmatter(frontmatter, skill_dir_name=skill_name)

        return SkillDefinition(
            metadata=metadata,
            instructions=body.strip(),
            references=self._list_resource_dir(skill_dir / _REFERENCES_DIR),
            scripts=self._list_resource_dir(skill_dir / _SCRIPTS_DIR),
        )

    # -- Stage 3: extension --------------------------------------------- #
    def load_reference(self, skill_name: str, reference_name: str) -> str:
        """Return the text of one reference file (loaded only when asked)."""
        path = self._resource_path(skill_name, _REFERENCES_DIR, reference_name)
        return path.read_text(encoding="utf-8")

    def get_script_path(self, skill_name: str, script_name: str) -> Path:
        """Return the path to one script file (never executed here)."""
        return self._resource_path(skill_name, _SCRIPTS_DIR, script_name)

    # -- internals ----------------------------------------------------- #
    def _skill_dir(self, skill_name: str) -> Path:
        skill_dir = self.root / skill_name
        if "/" in skill_name or "\\" in skill_name or not skill_dir.is_dir():
            raise SkillNotFoundError(f"no skill named {skill_name!r} in {self.root}")
        return skill_dir

    @staticmethod
    def _list_resource_dir(directory: Path) -> list[str]:
        if not directory.is_dir():
            return []
        return sorted(p.name for p in directory.iterdir() if p.is_file())

    def _resource_path(self, skill_name: str, kind: str, resource_name: str) -> Path:
        base = self._skill_dir(skill_name) / kind
        candidate = (base / resource_name).resolve()
        # Reject path traversal and non-existent files.
        if base.resolve() not in candidate.parents or not candidate.is_file():
            raise SkillResourceNotFoundError(
                f"skill {skill_name!r} has no {kind} resource {resource_name!r}"
            )
        return candidate
