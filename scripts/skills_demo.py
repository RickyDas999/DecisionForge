"""Zero-cost demo of the three-stage Agent Skills progressive disclosure.

No agents, no ModelProvider, no network — just deterministic file I/O.

    python scripts/skills_demo.py
"""

from __future__ import annotations

from app.skills.local import LocalSkillRegistry


def main() -> int:
    registry = LocalSkillRegistry()

    print("=" * 64)
    print("STAGE 1 — DISCOVERY (metadata only)")
    print("=" * 64)
    for meta in registry.discover():
        print(f"\n  {meta.name}")
        print(f"    {meta.description}")

    print("\n" + "=" * 64)
    print("STAGE 2 — ACTIVATION (load ONE skill's SKILL.md body)")
    print("=" * 64)
    comparison = registry.load("comparison")
    print(f"\nActivated skill: {comparison.name}")
    print(f"References available (not loaded): {comparison.references}")
    print(f"Scripts available (not loaded/run): {comparison.scripts}")
    print("\n--- comparison SKILL.md instructions ---")
    print(comparison.instructions)

    print("\n" + "=" * 64)
    print("STAGE 3 — EXTENSION (explicitly load one reference)")
    print("=" * 64)
    framework = registry.load_reference("comparison", "comparison-framework.md")
    print("\n--- comparison/references/comparison-framework.md ---")
    print(framework)

    print("\n" + "=" * 64)
    print("Not loaded during this run (progressive disclosure):")
    print("  - research/references/research-guidelines.md")
    print("  - executive-brief/references/brief-template.md")
    print("  - executive-brief/scripts/validate_brief.py  (path only, never executed)")
    print("  - the research and executive-brief SKILL.md bodies")
    print("\nModelProvider calls made by this demo: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
