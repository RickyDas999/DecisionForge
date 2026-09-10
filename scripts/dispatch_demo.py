"""End-to-end DecisionForge demo: request -> orchestrator -> one specialist -> result.

Default (mock, zero network, zero cost) -- runs three independent requests:

    python scripts/dispatch_demo.py

Live mode -- runs ONE request through the real Anthropic API:

    MODEL_PROVIDER=anthropic \
    ANTHROPIC_API_KEY=... \
    ANTHROPIC_MODEL=... \
    python scripts/dispatch_demo.py --live "Compare PostgreSQL and MongoDB for a SaaS startup."

Live brief requests also need --context:

    python scripts/dispatch_demo.py --live --context "Our team evaluated three approaches..." \
        "Create an executive brief from this material."

A live run makes at most TWO Anthropic calls (one orchestrator + one specialist),
with no retry and no fallback route. If routing picks BRIEF and no --context was
given, the run stops after the single orchestrator call. Do not run --live unless
you intend to spend API credit.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.agents.base import AgentRuntimeContext
from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest, DispatchResult
from app.models.routing import AgentRoute, RoutingDecision
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.orchestration.exceptions import MissingBriefContextError
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.mock import MockModelProvider
from app.runtime import create_dispatcher

_CTX = AgentRuntimeContext(run_id="dispatch-demo")


def _show(request: DispatchRequest, result: DispatchResult) -> None:
    print(f"User request:\n  {request.user_request}")
    if request.provided_context:
        print(f"Provided context:\n  {request.provided_context}")
    print(f"\nRoute: {result.route.value}")
    print("LLM calls for this run: 2 maximum (1 orchestrator + 1 specialist)")
    print(f"Routing reasoning:\n  {result.routing_reasoning}")
    print(f"Selected specialist: {result.route.value}Agent")
    print("Structured result:")
    print(result.result.model_dump_json(indent=2))
    print("=" * 64)


# --------------------------------------------------------------------------- #
# Mock demo
# --------------------------------------------------------------------------- #
def _mock_dispatcher(
    routing: RoutingDecision,
    *,
    research: ResearchResponse | None = None,
    comparison: ComparisonResponse | None = None,
    brief: BriefResponse | None = None,
) -> DecisionForgeDispatcher:
    """One dispatcher per demo request, with per-agent mock providers."""
    return DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(
            MockModelProvider(structured_responses=[routing])
        ),
        research_agent=ResearchAgent(
            MockModelProvider(structured_responses=[research] if research else [])
        ),
        comparison_agent=ComparisonAgent(
            MockModelProvider(structured_responses=[comparison] if comparison else [])
        ),
        brief_agent=BriefAgent(
            MockModelProvider(structured_responses=[brief] if brief else [])
        ),
    )


def _run_mock_demo() -> int:
    print("Running in MOCK mode (no network, no cost).\n")

    # A. Research
    req_a = DispatchRequest(user_request="Explain open-source vector databases.")
    disp_a = _mock_dispatcher(
        RoutingDecision(route=AgentRoute.RESEARCH, reasoning="asks to explain a topic"),
        research=ResearchResponse(
            topic="vector databases",
            summary="Databases specialised for similarity search over embeddings.",
            key_findings=["pgvector, Milvus, Qdrant and Weaviate are common choices."],
            limitations=["No live search performed; based on model knowledge only."],
            sources=[],
        ),
    )
    _show(req_a, asyncio.run(disp_a.dispatch(req_a, _CTX)))

    # B. Comparison
    req_b = DispatchRequest(
        user_request="Compare PostgreSQL and MongoDB for a small SaaS application."
    )
    disp_b = _mock_dispatcher(
        RoutingDecision(
            route=AgentRoute.COMPARISON, reasoning="explicitly compares two databases"
        ),
        comparison=ComparisonResponse(
            question=req_b.user_request,
            options=[
                ComparisonOption(
                    name="PostgreSQL",
                    advantages=["Strong consistency", "Mature SQL tooling"],
                    disadvantages=["Careful schema migrations"],
                ),
                ComparisonOption(
                    name="MongoDB",
                    advantages=["Flexible documents"],
                    disadvantages=["Weaker multi-doc transactions"],
                ),
            ],
            recommendation="PostgreSQL for relational SaaS data.",
            rationale="Most SaaS data benefits from constraints and joins.",
            important_tradeoffs=["Schema rigidity vs flexibility"],
            confidence=0.66,
            limitations=["No workload benchmarks or pricing supplied."],
        ),
    )
    _show(req_b, asyncio.run(disp_b.dispatch(req_b, _CTX)))

    # C. Brief (with context)
    req_c = DispatchRequest(
        user_request="Create an executive brief from this material.",
        provided_context=(
            "Our team evaluated two database approaches over three weeks. "
            "Approach A shipped faster; approach B scaled better under load."
        ),
    )
    disp_c = _mock_dispatcher(
        RoutingDecision(
            route=AgentRoute.BRIEF, reasoning="supplies material and asks to transform it"
        ),
        brief=BriefResponse(
            title="Database Approach: Decision Brief",
            executive_summary=(
                "Two approaches were trialled; each has one clear strength and a "
                "direction must be chosen."
            ),
            key_points=["A shipped faster.", "B scaled better under load."],
            recommendation=None,
            action_items=["Choose a direction by Friday."],
        ),
    )
    _show(req_c, asyncio.run(disp_c.dispatch(req_c, _CTX)))
    return 0


# --------------------------------------------------------------------------- #
# Live demo
# --------------------------------------------------------------------------- #
def _run_live_demo(request_text: str, context: str | None) -> int:
    config = ModelConfig.from_env()
    if config.provider is not ModelProviderType.ANTHROPIC:
        print(
            "Refusing to run --live: set MODEL_PROVIDER=anthropic (plus "
            "ANTHROPIC_API_KEY and ANTHROPIC_MODEL).",
            file=sys.stderr,
        )
        return 2

    print(
        "This request may make up to 2 real Anthropic API calls and may incur "
        "API charges."
    )
    print(f"provider={config.provider.value} model={config.model}\n")

    dispatcher = create_dispatcher(create_model_provider(config))
    request = DispatchRequest(user_request=request_text, provided_context=context)

    try:
        result = asyncio.run(dispatcher.dispatch(request, _CTX))
    except MissingBriefContextError as exc:
        print(
            f"\nRouting selected 'brief' but no --context was supplied: {exc}\n"
            "Stopped after the single orchestrator call; no specialist call was "
            "made.",
            file=sys.stderr,
        )
        return 3

    _show(request, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", nargs="?", help="The single request (live mode).")
    parser.add_argument(
        "--live", action="store_true", help="Make up to 2 real Anthropic API calls."
    )
    parser.add_argument(
        "--context", help="Source material (required if routing picks 'brief')."
    )
    args = parser.parse_args(argv)

    if not args.live:
        return _run_mock_demo()

    if not args.request:
        print(
            '--live requires one request argument, e.g.:\n'
            '    python scripts/dispatch_demo.py --live "Compare X and Y."',
            file=sys.stderr,
        )
        return 2
    return _run_live_demo(args.request, args.context)


if __name__ == "__main__":
    raise SystemExit(main())
