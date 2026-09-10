"""Demonstrate OrchestratorAgent routing.

Default (mock, zero network, zero cost) -- routes three sample requests:

    python scripts/orchestrator_demo.py

Live mode -- routes ONE request through the real Anthropic API:

    MODEL_PROVIDER=anthropic \
    ANTHROPIC_API_KEY=... \
    ANTHROPIC_MODEL=... \
    python scripts/orchestrator_demo.py --live "Compare PostgreSQL and MongoDB."

Live mode makes exactly one Orchestrator call (one billable request). It never
batches the sample requests. Do not run it unless you intend to spend API credit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agents.base import AgentRuntimeContext
from app.agents.orchestrator import OrchestratorAgent
from app.models.routing import AgentRoute, RoutingDecision, RoutingInput
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.mock import MockModelProvider

_SAMPLES: list[tuple[str, AgentRoute]] = [
    ("Research current open-source vector databases.", AgentRoute.RESEARCH),
    ("Compare PostgreSQL and MongoDB for a small startup.", AgentRoute.COMPARISON),
    ("Turn the analysis below into an executive memo for leadership.", AgentRoute.BRIEF),
]


def _print_decision(request: str, decision: RoutingDecision) -> None:
    print(f"Input:\n{request}\n")
    print(f"Route:\n{decision.route.value}\n")
    print(f"Reasoning:\n{decision.reasoning}\n")
    print("-" * 60)


async def _route_once(agent: OrchestratorAgent, request: str) -> RoutingDecision:
    return await agent.run(
        RoutingInput(user_request=request), AgentRuntimeContext(run_id="demo")
    )


def _run_mock_demo() -> int:
    print("Running in MOCK mode (no network, no cost).\n")
    # Queue one plausible decision per sample so the mock has something to return.
    provider = MockModelProvider(
        structured_responses=[
            RoutingDecision(route=route, reasoning=f"mock classification -> {route.value}")
            for _, route in _SAMPLES
        ]
    )
    agent = OrchestratorAgent(provider)
    for request, _ in _SAMPLES:
        decision = asyncio.run(_route_once(agent, request))
        _print_decision(request, decision)
    return 0


def _run_live_demo(request: str) -> int:
    config = ModelConfig.from_env()
    if config.provider is not ModelProviderType.ANTHROPIC:
        print(
            "Refusing to run --live: set MODEL_PROVIDER=anthropic (plus "
            "ANTHROPIC_API_KEY and ANTHROPIC_MODEL) to make a live request.",
            file=sys.stderr,
        )
        return 2

    print("This will make real Anthropic API requests and may incur API charges.")
    print(f"provider={config.provider.value} model={config.model}\n")

    agent = OrchestratorAgent(create_model_provider(config))
    decision = asyncio.run(_route_once(agent, request))
    _print_decision(request, decision)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "request",
        nargs="?",
        help="The single user request to route (required with --live).",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Make ONE real Anthropic API request (may incur charges).",
    )
    args = parser.parse_args(argv)

    if not args.live:
        return _run_mock_demo()

    if not args.request:
        print(
            "--live requires exactly one request argument, e.g.:\n"
            '    python scripts/orchestrator_demo.py --live "Compare X and Y."',
            file=sys.stderr,
        )
        return 2
    return _run_live_demo(args.request)


if __name__ == "__main__":
    raise SystemExit(main())
