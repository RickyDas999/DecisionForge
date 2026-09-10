"""Deterministic structural validator for an executive brief.

Part of the executive-brief skill (Stage 3 extension). This is plain Python: it
makes no LLM calls, imports no Anthropic SDK, invokes no agents, and touches no
network. It only inspects a serializable brief structure.

A later phase may call this and act on the result deterministically. There is no
automatic correction loop here.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def validate_brief(brief: Mapping[str, Any]) -> dict[str, Any]:
    """Check that a BriefResponse-like mapping has the required structure.

    Returns ``{"success": bool, "message": str}``.
    """
    title = brief.get("title")
    if not isinstance(title, str) or not title.strip():
        return {"success": False, "message": "Missing required title."}

    summary = brief.get("executive_summary")
    if not isinstance(summary, str) or not summary.strip():
        return {"success": False, "message": "Missing required executive summary."}

    key_points = brief.get("key_points")
    if not isinstance(key_points, (list, tuple)) or len(key_points) == 0:
        return {"success": False, "message": "Brief must contain at least one key point."}

    return {"success": True, "message": "Brief structure is valid."}


if __name__ == "__main__":  # pragma: no cover - manual convenience only
    import json
    import sys

    raw = sys.stdin.read()
    print(json.dumps(validate_brief(json.loads(raw))))
