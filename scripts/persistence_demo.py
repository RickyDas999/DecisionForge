"""Zero-cost demo of SQLite persistence + execution tracing.

Runs one request through DecisionForgeService with MockModelProvider and
MockSearchProvider against a throwaway temp database. No Anthropic, no network.

    python scripts/persistence_demo.py
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from app.agents.brief import BriefAgent
from app.agents.comparison import ComparisonAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.research import ResearchAgent
from app.models.dispatch import DispatchRequest
from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import ComparisonOption, ComparisonResponse
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.persistence.sqlite import SQLiteRunRepository
from app.providers.mock import MockModelProvider
from app.service import DecisionForgeService
from app.tools.search import MockSearchProvider


def _build(db_path: Path) -> tuple[DecisionForgeService, SQLiteRunRepository]:
    dispatcher = DecisionForgeDispatcher(
        orchestrator=OrchestratorAgent(
            MockModelProvider(
                structured_responses=[
                    RoutingDecision(
                        route=AgentRoute.COMPARISON,
                        reasoning="the user explicitly compares two databases",
                    )
                ]
            )
        ),
        research_agent=ResearchAgent(MockModelProvider()),
        comparison_agent=ComparisonAgent(
            MockModelProvider(
                structured_responses=[
                    ComparisonResponse(
                        question="Compare PostgreSQL and MongoDB for a small SaaS app.",
                        options=[
                            ComparisonOption(
                                name="PostgreSQL", advantages=["Strong consistency"]
                            ),
                            ComparisonOption(
                                name="MongoDB", advantages=["Flexible documents"]
                            ),
                        ],
                        recommendation="PostgreSQL for relational SaaS data.",
                        rationale="Most SaaS data benefits from constraints and joins.",
                        important_tradeoffs=["Schema rigidity vs flexibility"],
                        confidence=0.66,
                        limitations=["Search evidence was mock/offline for this demo."],
                    )
                ]
            )
        ),
        brief_agent=BriefAgent(MockModelProvider()),
        search_provider=MockSearchProvider(
            responses=[
                SearchResponse(
                    query="demo",
                    results=[
                        SearchResult(
                            title="Illustrative result",
                            url="https://example.com/a",
                            snippet="A short deterministic snippet for the demo.",
                            source="example.com",
                        )
                    ],
                )
            ]
        ),
    )
    repo = SQLiteRunRepository(db_path)
    return DecisionForgeService(dispatcher, repo), repo


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "decisionforge-demo.db"
        service, repo = _build(db_path)

        request = DispatchRequest(
            user_request="Compare PostgreSQL and MongoDB for a small SaaS application."
        )
        record = asyncio.run(service.run(request))

        print("Running with MockModelProvider + MockSearchProvider (no network, no cost).")
        print(f"Temp DB: {db_path}\n")
        print(f"run_id            : {record.run_id}")
        print(f"status            : {record.status.value}")
        print(f"route             : {record.route.value if record.route else None}")
        print(f"selected_specialist: {record.selected_specialist}")
        print(f"search_used       : {record.search_used}")
        print(f"created_at        : {record.created_at.isoformat()}")
        print(f"completed_at      : {record.completed_at.isoformat()}")
        print("\npersisted result_json:")
        print(record.result_json)

        print("\nchronological events:")
        for event in repo.get_events(record.run_id):
            meta = f"  {event.metadata}" if event.metadata else ""
            print(f"  {event.timestamp.isoformat()}  {event.event_type.value}{meta}")

        print("\nModelProvider calls added by persistence: 0")
        print("Total LLM calls for this run: 2 (1 orchestrator + 1 specialist)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
