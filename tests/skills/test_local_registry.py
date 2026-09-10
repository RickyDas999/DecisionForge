"""Progressive-disclosure tests for :class:`LocalSkillRegistry`. Pure file I/O."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.skills.exceptions import (
    InvalidSkillError,
    SkillNotFoundError,
    SkillResourceNotFoundError,
)
from app.skills.local import DEFAULT_SKILL_ROOT, LocalSkillRegistry

EXPECTED_SKILLS = {"research", "comparison", "executive-brief"}


@pytest.fixture
def registry() -> LocalSkillRegistry:
    return LocalSkillRegistry(DEFAULT_SKILL_ROOT)


# -- Stage 1: discovery --------------------------------------------------- #
def test_discover_returns_exactly_the_three_skills(registry: LocalSkillRegistry) -> None:
    names = {m.name for m in registry.discover()}
    assert names == EXPECTED_SKILLS


def test_discover_returns_metadata_only(registry: LocalSkillRegistry) -> None:
    for meta in registry.discover():
        assert meta.name and meta.description
        # SkillMetadata has no instructions/references/scripts fields at all.
        assert set(meta.model_dump()) == {"name", "description"}


def test_discover_descriptions_are_descriptive(registry: LocalSkillRegistry) -> None:
    by_name = {m.name: m.description.lower() for m in registry.discover()}
    assert "compar" in by_name["comparison"]
    assert "research" in by_name["research"] or "investigat" in by_name["research"]
    assert "brief" in by_name["executive-brief"]


# -- Stage 2: activation ------------------------------------------------ #
def test_load_returns_instructions_body(registry: LocalSkillRegistry) -> None:
    definition = registry.load("comparison")
    assert definition.metadata.name == "comparison"
    assert "Comparison skill" in definition.instructions
    assert "---" not in definition.instructions.splitlines()[0]  # frontmatter stripped


def test_load_exposes_resource_names_without_contents(
    registry: LocalSkillRegistry,
) -> None:
    definition = registry.load("executive-brief")
    assert definition.references == ["brief-template.md"]
    assert definition.scripts == ["validate_brief.py"]
    # Names only — the body text is not present anywhere in the definition.
    assert "Preferred structure" not in definition.instructions
    assert "def validate_brief" not in definition.instructions


def test_load_research_has_reference_and_no_scripts(
    registry: LocalSkillRegistry,
) -> None:
    definition = registry.load("research")
    assert definition.references == ["research-guidelines.md"]
    assert definition.scripts == []


# -- Stage 3: extension ----------------------------------------------- #
def test_load_reference_returns_content_on_request(
    registry: LocalSkillRegistry,
) -> None:
    text = registry.load_reference("comparison", "comparison-framework.md")
    assert "Identify decision criteria" in text


def test_get_script_path_returns_only_the_requested_script(
    registry: LocalSkillRegistry,
) -> None:
    path = registry.get_script_path("executive-brief", "validate_brief.py")
    assert isinstance(path, Path)
    assert path.name == "validate_brief.py"
    assert path.is_file()


# -- Errors ---------------------------------------------------------- #
def test_unknown_skill_raises_skill_not_found(registry: LocalSkillRegistry) -> None:
    with pytest.raises(SkillNotFoundError):
        registry.load("planner")


def test_unknown_reference_raises_resource_not_found(
    registry: LocalSkillRegistry,
) -> None:
    with pytest.raises(SkillResourceNotFoundError):
        registry.load_reference("research", "does-not-exist.md")


def test_unknown_script_raises_resource_not_found(
    registry: LocalSkillRegistry,
) -> None:
    with pytest.raises(SkillResourceNotFoundError):
        registry.get_script_path("executive-brief", "nope.py")


def test_reference_path_traversal_is_rejected(registry: LocalSkillRegistry) -> None:
    with pytest.raises(SkillResourceNotFoundError):
        registry.load_reference("research", "../../SKILL.md")


def test_malformed_frontmatter_raises_invalid_skill(tmp_path: Path) -> None:
    bad = tmp_path / "broken"
    bad.mkdir()
    (bad / "SKILL.md").write_text("no frontmatter here\njust text\n")
    with pytest.raises(InvalidSkillError):
        LocalSkillRegistry(tmp_path).load("broken")


def test_frontmatter_missing_description_raises_invalid_skill(tmp_path: Path) -> None:
    bad = tmp_path / "partial"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: partial\n---\nbody\n")
    with pytest.raises(InvalidSkillError):
        LocalSkillRegistry(tmp_path).load("partial")


def test_discover_on_missing_root_is_empty(tmp_path: Path) -> None:
    assert LocalSkillRegistry(tmp_path / "nope").discover() == []
