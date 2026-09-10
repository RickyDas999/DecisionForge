"""Demonstrate the three leaf specialist agents independently.

Default (mock, zero network, zero cost) -- runs all three specialists:

    python scripts/specialists_demo.py

Live mode -- runs exactly ONE specialist through the real Anthropic API:

    MODEL_PROVIDER=anthropic \
    ANTHROPIC_API_KEY=... \
    ANTHROPIC_MODEL=... \
    python scripts/specialists_demo.py --live --agent comparison \
        "Compare PostgreSQL and MongoDB for a small SaaS startup."

Live BriefAgent additionally requires --context:

    python scripts/specialists_demo.py --live --agent brief \
        "Create an executive brief." --context "Our team tested two approaches..."

Live mode makes exactly one specialist call (one billable request). It never
calls the orchestrator first and never runs the other specialists. Do not run it
unless you intend to spend API credit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.research import ResearchAgent
from app.models.specialists import (
    BriefInput,
    BriefResponse,
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
    ResearchInput,
    ResearchResponse,
)
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.mock import MockModelProvider

_CONTEXT = AgentRuntimeContext(run_id="demo")

_MOCK_RESEARCH = ResearchResponse(
    topic="vector databases",
    summary="Vector databases index high-dimensional embeddings for similarity search.",
    key_findings=[
        "Common options include pgvector, Milvus, Qdrant, and Weaviate.",
        "Choice depends on scale, existing stack, and operational appetite.",
    ],
    limitations=["No live search was performed; based on model knowledge only."],
    sources=[],
)
_MOCK_COMPARISON = ComparisonResponse(
    question="Compare PostgreSQL and MongoDB for a small SaaS application.",
    options=[
        ComparisonOption(
            name="PostgreSQL",
            advantages=["Strong consistency", "Mature SQL ecosystem"],
            disadvantages=["Schema migrations require care"],
        ),
        ComparisonOption(
            name="MongoDB",
            advantages=["Flexible documents", "Fast early iteration"],
            disadvantages=["Weaker multi-document transactional story"],
        ),
    ],
    recommendation="PostgreSQL for a small SaaS app with relational data.",
    rationale="Most SaaS data is relational and benefits from constraints.",
    important_tradeoffs=["Schema rigidity vs schema flexibility"],
    confidence=0.66,
    limitations=["No workload benchmarks or current pricing were supplied."],
)
_MOCK_BRIEF = BriefResponse(
    title="Database Approach: Decision Brief",
    executive_summary=(
        "Two database approaches were trialled over three weeks; each has a clear "
        "strength and the team must choose a direction."
    ),
    key_points=[
        "Approach A shipped faster.",
        "Approach B scaled better under load.",
    ],
    recommendation=None,
    action_items=["Choose a direction by Friday", "Document the rationale"],
)


def _print(header: str, model) -> None:
    print(f"=== {header} ===")
    print(model.model_dump_json(indent=2))
    print()


def _run_mock_demo() -> int:
    print("Running in MOCK mode (no network, no cost).\n")

    research = ResearchAgent(MockModelProvider(structured_responses=[_MOCK_RESEARCH]))
    comparison = ComparisonAgent(
        MockModelProvider(structured_responses=[_MOCK_COMPARISON])
    )
    brief = BriefAgent(MockModelProvider(structured_responses=[_MOCK_BRIEF]))

    _print(
        "ResearchAgent",
        asyncio.run(
            research.run(
                ResearchInput(user_request="Explain vector databases."), _CONTEXT
            )
        ),
    )
    _print(
        "ComparisonAgent",
        asyncio.run(
            comparison.run(
                ComparisonInput(
                    user_request=(
                        "Compare PostgreSQL and MongoDB for a small SaaS application."
                    )
                ),
                _CONTEXT,
            )
        ),
    )
    _print(
        "BriefAgent",
        asyncio.run(
            brief.run(
                BriefInput(
                    user_request="Create an executive brief.",
                    provided_context=(
                        "Our team tested two database approaches over three weeks. "
                        "Approach A shipped faster; approach B scaled better."
                    ),
                ),
                _CONTEXT,
            )
        ),
    )
    return 0


def _run_live_demo(agent_name: str, request: str, context: str | None) -> int:
    config = ModelConfig.from_env()
    if config.provider is not ModelProviderType.ANTHROPIC:
        print(
            "Refusing to run --live: set MODEL_PROVIDER=anthropic (plus "
            "ANTHROPIC_API_KEY and ANTHROPIC_MODEL).",
            file=sys.stderr,
        )
        return 2

    if agent_name == "brief" and not (context and context.strip()):
        print(
            "--agent brief requires --context \"...\" in live mode "
            "(context is never fabricated).",
            file=sys.stderr,
        )
        return 2

    print("This will make one real Anthropic API request and may incur API charges.")
    print(f"provider={config.provider.value} model={config.model} agent={agent_name}\n")

    provider = create_model_provider(config)

    if agent_name == "research":
        result = asyncio.run(
            ResearchAgent(provider).run(
                ResearchInput(user_request=request, provided_context=context), _CONTEXT
            )
        )
    elif agent_name == "comparison":
        result = asyncio.run(
            ComparisonAgent(provider).run(
                ComparisonInput(user_request=request, provided_context=context), _CONTEXT
            )
        )
    else:  # brief
        result = asyncio.run(
            BriefAgent(provider).run(
                BriefInput(user_request=request, provided_context=context or ""),
                _CONTEXT,
            )
        )

    _print(f"{agent_name}Agent (live)", result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", help="The single request (live mode).")
    parser.add_argument("--live", action="store_true", help="Make ONE real API request.")
    parser.add_argument(
        "--agent", choices=["research", "comparison", "brief"], help="Which specialist."
    )
    parser.add_argument("--context", help="Supplied context (required for --agent brief).")
    args = parser.parse_args(argv)

    if not args.live:
        return _run_mock_demo()

    if not args.agent or not args.request:
        print(
            "--live requires --agent [research|comparison|brief] and one request "
            "argument.",
            file=sys.stderr,
        )
        return 2
    return _run_live_demo(args.agent, args.request, args.context)


if __name__ == "__main__":
    raise SystemExit(main())
