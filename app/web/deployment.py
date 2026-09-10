"""Deployment bootstrap — the app served on Vercel (or any host).

Configuration is read from the environment via the existing ``ModelConfig`` /
``SearchConfig`` plus one flag, ``PERSISTENCE_ENABLED`` (default: false).

``create_deployment_app()`` is **import-safe**: no network call, no LLM call, no
credentials required in the default (mock) mode, no SQLite file, no uvicorn, no
demo requests. It only constructs and configures the application (reading the
``skills/`` and static files at construction is fine).

Modes:

* ``MODEL_PROVIDER=mock`` (default) — the deterministic offline
  :class:`DemoModelProvider`. Usable with no credentials.
* ``MODEL_PROVIDER=anthropic`` — the real :class:`AnthropicModelProvider`
  (requires ``ANTHROPIC_API_KEY`` + ``ANTHROPIC_MODEL``; real, billable calls).
  Still exactly two LLM calls per successful request.

Search is **off** by default in a deployment (``SEARCH_PROVIDER=mock``). Set
``SEARCH_PROVIDER=duckduckgo`` and install the ``ddgs`` package to enable it.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from app.persistence.base import RunRepository
from app.persistence.null import NullRunRepository
from app.persistence.sqlite import SQLiteRunRepository, resolve_db_path
from app.providers.config import ModelConfig, ModelProviderType
from app.providers.factory import create_model_provider
from app.providers.model import ModelProvider
from app.runtime import create_dispatcher
from app.service import DecisionForgeService
from app.skills.local import LocalSkillRegistry
from app.tools.search import (
    SearchConfig,
    SearchProvider,
    SearchProviderType,
    create_search_provider,
)
from app.web.app import create_app
from app.web.demo_provider import DemoModelProvider

_TRUE = {"1", "true", "yes", "on"}

PERSISTENCE_ENV_VAR = "PERSISTENCE_ENABLED"


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in _TRUE


def _model_provider(config: ModelConfig) -> ModelProvider:
    if config.provider is ModelProviderType.MOCK:
        # A bare MockModelProvider needs pre-queued responses; DemoModelProvider
        # gives a usable, deterministic offline demo with none.
        return DemoModelProvider()
    # anthropic: validates key + model, constructs the async client (no request).
    return create_model_provider(config)


def _search_provider(config: SearchConfig) -> SearchProvider | None:
    if config.provider is SearchProviderType.DUCKDUCKGO:
        return create_search_provider(config)  # lazy ddgs import (only on .search())
    return None  # no automatic search in the deployed demo


def _repository(persistence_enabled: bool) -> RunRepository:
    if persistence_enabled:
        return SQLiteRunRepository(resolve_db_path())
    return NullRunRepository()


def create_deployment_app() -> FastAPI:
    """Construct the app from environment configuration. Import-safe.

    Reads process environment variables only (no ``.env`` file) — deployment
    configuration comes from the host.
    """
    model_config = ModelConfig.from_env(use_dotenv=False)
    search_config = SearchConfig.from_env()
    persistence_enabled = _env_bool(PERSISTENCE_ENV_VAR, default=False)

    repository = _repository(persistence_enabled)
    dispatcher = create_dispatcher(
        _model_provider(model_config),
        skill_registry=LocalSkillRegistry(),
        search_provider=_search_provider(search_config),
    )
    service = DecisionForgeService(dispatcher, repository)
    return create_app(
        service,
        repository,
        model_provider_label=model_config.provider.value,
    )
