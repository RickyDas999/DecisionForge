"""Zero-cost local bootstrap for the web app.

Builds a :class:`DecisionForgeService` from an **offline** demo model provider,
an offline mock search provider, and local SQLite. No Anthropic, no network, no
credentials. A real Anthropic-backed server is a later, user-driven change.

``uvicorn --factory app.web.bootstrap:create_demo_app`` or
``python scripts/web_demo.py`` serve this. There is intentionally **no**
module-level ``app`` — construction touches the filesystem (creates the SQLite
file), so it must be explicit.
"""

from __future__ import annotations

from fastapi import FastAPI

from app.models.search import SearchResponse, SearchResult
from app.orchestration.dispatcher import DecisionForgeDispatcher
from app.persistence.sqlite import SQLiteRunRepository, resolve_db_path
from app.runtime import create_dispatcher
from app.service import DecisionForgeService
from app.skills.local import LocalSkillRegistry
from app.tools.search import MockSearchProvider
from app.web.app import create_app
from app.web.demo_provider import DemoModelProvider


class _DemoSearchProvider(MockSearchProvider):
    """A MockSearchProvider that always returns the same offline demo results."""

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        self.responses = [
            SearchResponse(
                query=query,
                results=[
                    SearchResult(
                        title="Demo search result",
                        url="https://example.com/demo",
                        snippet=(
                            "Offline demo search snippet. Install and select the "
                            "'[search]' provider for real web results."
                        ),
                        source="example.com",
                    )
                ],
            )
        ]
        return await super().search(query, max_results=max_results)


def create_demo_service(db_path: str | None = None) -> tuple[DecisionForgeService, SQLiteRunRepository]:
    """A fully offline service + its repository."""
    repository = SQLiteRunRepository(resolve_db_path(db_path))
    dispatcher: DecisionForgeDispatcher = create_dispatcher(
        DemoModelProvider(),
        skill_registry=LocalSkillRegistry(),
        search_provider=_DemoSearchProvider(),
    )
    return DecisionForgeService(dispatcher, repository), repository


def create_demo_app(db_path: str | None = None) -> FastAPI:
    service, repository = create_demo_service(db_path)
    return create_app(service, repository)
