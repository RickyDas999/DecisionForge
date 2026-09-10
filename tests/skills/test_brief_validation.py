"""Deterministic tests for the executive-brief validation script.

The script is loaded via the skill registry's Stage-3 ``get_script_path`` and
imported by file path (it is a skill asset, not an installed module). No LLM.
"""

from __future__ import annotations

import importlib.util
from types import ModuleType

import pytest

from app.skills.local import LocalSkillRegistry


def _load_validator() -> ModuleType:
    path = LocalSkillRegistry().get_script_path("executive-brief", "validate_brief.py")
    spec = importlib.util.spec_from_file_location("validate_brief", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()

VALID_BRIEF = {
    "title": "Database Decision",
    "executive_summary": "Two options were trialled; a choice is needed.",
    "key_points": ["A shipped faster", "B scaled better"],
    "recommendation": None,
    "action_items": ["Decide by Friday"],
}


def test_valid_brief_passes() -> None:
    result = VALIDATOR.validate_brief(VALID_BRIEF)
    assert result == {"success": True, "message": "Brief structure is valid."}


@pytest.mark.parametrize("missing", ["title", "executive_summary"])
def test_missing_required_string_fails(missing: str) -> None:
    brief = {**VALID_BRIEF, missing: ""}
    result = VALIDATOR.validate_brief(brief)
    assert result["success"] is False


def test_absent_key_fails() -> None:
    brief = {k: v for k, v in VALID_BRIEF.items() if k != "title"}
    assert VALIDATOR.validate_brief(brief)["success"] is False


def test_empty_key_points_fails() -> None:
    brief = {**VALID_BRIEF, "key_points": []}
    result = VALIDATOR.validate_brief(brief)
    assert result["success"] is False
    assert "key point" in result["message"].lower()


def test_script_imports_nothing_forbidden() -> None:
    source = LocalSkillRegistry().get_script_path(
        "executive-brief", "validate_brief.py"
    ).read_text()
    for banned in ("anthropic", "requests", "httpx", "urllib", "socket"):
        assert banned not in source
