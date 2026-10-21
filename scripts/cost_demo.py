"""Show what one DecisionForge run costs, call by call.

Default (offline, zero cost) -- token counts are estimates of what the same
calls would cost on claude-haiku-5-5:

    python scripts/cost_demo.py "Compare PostgreSQL and MongoDB for a SaaS startup."

Replay a recorded real run (zero cost, no API key):

    REPLAY_MODE=replay python scripts/cost_demo.py "..."

Live (billable, capped by RUN_BUDGET_USD per run and SPEND_LIMIT_USD lifetime);
REPLAY_MODE=auto records the run so later replays are free:

    MODEL_PROVIDER=anthropic ANTHROPIC_API_KEY=... REPLAY_MODE=auto \
        python scripts/cost_demo.py --live "..."
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.models.dispatch import DispatchRequest
from app.models.persistence import EventType
from app.persistence.null import NullRunRepository
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.exceptions import ModelProviderError
from app.providers.factory import create_model_provider
from app.providers.replay import ReplayMode
from app.providers.usage import LifetimeSpend
from app.runtime import create_dispatcher
from app.service import DecisionForgeService
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("request", nargs="?", default="Compare PostgreSQL and MongoDB for a SaaS startup.")
    parser.add_argument("--context", default=None)
    parser.add_argument("--live", action="store_true", help="allow billable Anthropic calls")
    args = parser.parse_args()

    config = ModelConfig.from_env()
    if config.provider is ModelProviderType.ANTHROPIC and not args.live:
        print("MODEL_PROVIDER=anthropic is billable; pass --live to confirm.", file=sys.stderr)
        return 2
    if config.provider is ModelProviderType.MOCK and config.replay_mode is not ReplayMode.REPLAY:
        provider = DemoModelProvider()
    else:
        provider = create_model_provider(config)

    service = DecisionForgeService(
        create_dispatcher(provider, search_provider=DemoSearchProvider(), decision_engine=True,
                          adaptive_samples=True, grounded_research=True),
        NullRunRepository(),
        run_budget=config.run_budget,
    )
    spend = LifetimeSpend(config.spend_ledger_path, config.spend_limit_usd)
    try:
        outcome = asyncio.run(
            service.run(DispatchRequest(user_request=args.request, provided_context=args.context))
        )
    except ModelProviderError as exc:
        print(f"run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"lifetime live spend: ${spend.total_usd:.5f} of ${spend.limit_usd:.2f} cap")
        return 1

    print(f"route: {outcome.record.route.value}\n")
    print(f"{'call':<22}{'source':<11}{'in':>7}{'out':>7}{'charged':>11}{'if live':>11}")
    for event in outcome.events:
        if event.event_type is EventType.LLM_CALL:
            m = event.metadata
            print(
                f"{m['operation']:<22}{m['source']:<11}{m['input_tokens']:>7}"
                f"{m['output_tokens']:>7}{m['cost_usd']:>11.5f}{m['list_cost_usd']:>11.5f}"
            )
    u = outcome.usage
    print(
        f"\ntotal: {u.calls} calls, ${u.cost_usd:.5f} charged, ${u.list_cost_usd:.5f} if live "
        f"(run budget ${u.budget_usd:.4f}, {u.max_calls} calls max)"
    )
    print(f"lifetime live spend: ${spend.total_usd:.5f} of ${spend.limit_usd:.2f} cap")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
