"""Eval reports: JSON for machines, Markdown for people, deltas for regressions.

``save_report`` writes ``<dir>/<label>.json`` and ``<dir>/<label>.md``. Passing a
previous report as ``baseline`` adds a delta column, so a prompt or model change
shows up as "+0.12 rubric coverage, -0.08 route accuracy" instead of a vibe.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evaluation.harness import EvalRun

#: Metric deltas smaller than this are shown as unchanged.
_EPSILON = 0.005


def to_dict(run: EvalRun) -> dict[str, Any]:
    return {
        "label": run.label,
        "started_at": run.started_at.isoformat(),
        "metrics": run.metric_summary(),
        "totals": run.totals(),
        "cases": [
            {
                "id": r.case.id,
                "expected_route": r.case.expected_route.value,
                "route": r.outcome.route.value if r.outcome.route else None,
                "scores": r.scores,
                "error": r.outcome.error,
                "llm_calls": r.outcome.llm_calls,
                "cost_usd": r.outcome.cost_usd,
                "list_cost_usd": r.outcome.list_cost_usd,
                "latency_ms": round(r.outcome.latency_ms, 1),
            }
            for r in run.results
        ],
    }


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _delta(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return ""
    diff = current - previous
    if abs(diff) < _EPSILON:
        return "="
    return f"{diff:+.2f}"


def to_markdown(run: EvalRun, baseline: dict[str, Any] | None = None) -> str:
    data = to_dict(run)
    totals = data["totals"]
    lines = [f"# Eval report: {run.label}", ""]
    lines.append(
        f"{totals['cases']} cases · {totals['errors']} errors · {totals['llm_calls']} LLM calls · "
        f"charged ${totals['cost_usd']:.5f} · ${totals['mean_list_cost_per_case_usd']:.5f}/case "
        f"if live · p50 latency {totals['p50_latency_ms']:.0f} ms"
    )
    lines.append("")
    header = "| metric | score | n |"
    rule = "|---|---|---|"
    if baseline:
        header += f" Δ vs {baseline.get('label', 'baseline')} |"
        rule += "---|"
    lines += [header, rule]
    for name, summary in data["metrics"].items():
        row = f"| {name} | {_fmt(summary['mean'])} | {summary['n']} |"
        if baseline:
            prev = baseline.get("metrics", {}).get(name, {}).get("mean")
            row += f" {_delta(summary['mean'], prev)} |"
        lines.append(row)

    lines += ["", "## Cases", ""]
    names = run.metric_names
    lines.append("| case | route | " + " | ".join(names) + " | cost if live |")
    lines.append("|---|---|" + "---|" * len(names) + "---|")
    for case in data["cases"]:
        route = case["route"] or "—"
        if case["route"] != case["expected_route"]:
            route = f"**{route}** (want {case['expected_route']})"
        cells = " | ".join(_fmt(case["scores"].get(n)) for n in names)
        lines.append(f"| {case['id']} | {route} | {cells} | ${case['list_cost_usd']:.5f} |")

    errors = [c for c in data["cases"] if c["error"]]
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- `{c['id']}`: {c['error']}" for c in errors]
    return "\n".join(lines) + "\n"


def save_report(
    run: EvalRun, directory: str | Path, baseline: dict[str, Any] | None = None
) -> tuple[Path, Path]:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{run.label}.json"
    md_path = out / f"{run.label}.md"
    json_path.write_text(json.dumps(to_dict(run), indent=1) + "\n", encoding="utf-8")
    md_path.write_text(to_markdown(run, baseline), encoding="utf-8")
    return json_path, md_path


def load_report(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
