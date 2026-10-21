"""Run the golden eval set end to end and write a report.

Offline, zero cost (canned demo answers; validates the harness):

    python scripts/run_eval.py

Replay recorded real answers (zero cost, no key; needs a recorded cassette):

    python scripts/run_eval.py --provider replay --label haiku-replay

Live (billable). Shows the worst-case cost and stops unless --yes-spend is given.
Every live answer is recorded to the cassette, so re-running replays it for free.
--pick runs a balanced 5-case sample (2 comparison, 2 research, 1 brief):

    MODEL_PROVIDER=anthropic ANTHROPIC_API_KEY=... \
        python scripts/run_eval.py --provider live --pick --yes-spend

Compare against an earlier report to see regressions:

    python scripts/run_eval.py --baseline evals/reports/demo.json --label demo-v2
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from app.evaluation.golden import load_golden_set, pick_balanced
from app.evaluation.harness import run_eval
from app.evaluation.report import load_report, save_report
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.replay import ReplayMode
from app.providers.usage import LifetimeSpend
from app.skills.local import LocalSkillRegistry
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--provider", choices=["demo", "replay", "live"], default="demo")
    parser.add_argument("--label", default=None, help="report name (default: the provider)")
    parser.add_argument("--limit", type=int, default=None, help="run only the first N cases")
    parser.add_argument("--tag", default=None, help="run only cases with this tag")
    parser.add_argument("--pick", action="store_true",
                        help="a balanced sample: 2 comparison, 2 research, 1 brief")
    parser.add_argument("--baseline", default=None, help="earlier report JSON to diff against")
    parser.add_argument("--out", default="evals/reports")
    parser.add_argument("--yes-spend", action="store_true", help="confirm live API spend")
    args = parser.parse_args()

    cases = load_golden_set()
    if args.tag:
        cases = [c for c in cases if args.tag in c.tags]
    if args.pick:
        cases = pick_balanced(cases)
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        print("no cases selected", file=sys.stderr)
        return 2

    config = ModelConfig.from_env()
    if args.provider == "demo":
        provider = DemoModelProvider()
    elif args.provider == "replay":
        if not Path(config.replay_cassette).exists():
            print(f"no cassette at {config.replay_cassette}; record one with --provider live",
                  file=sys.stderr)
            return 2
        provider = create_model_provider(config.model_copy(update={"replay_mode": ReplayMode.REPLAY}))
    else:
        if config.provider is not ModelProviderType.ANTHROPIC:
            print("--provider live needs MODEL_PROVIDER=anthropic and ANTHROPIC_API_KEY", file=sys.stderr)
            return 2
        spend = LifetimeSpend(config.spend_ledger_path, config.spend_limit_usd)
        worst = len(cases) * config.run_budget.max_usd
        print(
            f"{len(cases)} cases on {config.resolved_model}: worst case ${worst:.4f} "
            f"(${config.run_budget.max_usd} per case). Lifetime spend so far "
            f"${spend.total_usd:.5f} of ${spend.limit_usd:.2f}."
        )
        if not args.yes_spend:
            print("Re-run with --yes-spend to make these live calls.", file=sys.stderr)
            return 2
        # Record every live answer so the same eval replays for free afterwards.
        mode = config.replay_mode if config.replay_mode is not ReplayMode.OFF else ReplayMode.AUTO
        provider = create_model_provider(config.model_copy(update={"replay_mode": mode}))

    run = asyncio.run(
        run_eval(
            cases,
            provider,
            label=args.label or args.provider,
            search_provider=DemoSearchProvider(),
            skill_registry=LocalSkillRegistry(),
            run_budget=config.run_budget,
        )
    )
    baseline = load_report(args.baseline) if args.baseline else None
    json_path, md_path = save_report(run, args.out, baseline)
    print(md_path.read_text(encoding="utf-8").split("## Cases")[0].rstrip())
    print(f"\nwrote {md_path} and {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
