"""A small local FastAPI app over :class:`DecisionForgeService`.

The web layer adds **zero** LLM calls: it validates input, calls
``service.run(...)`` exactly once, and reads persisted runs/events. Failures are
mapped to clean HTTP responses (exception type + short message + run id only —
no stack traces, no secrets); the underlying exception is still persisted by the
service (marked ``failed``, ``run.failed`` recorded).

``POST /api/runs`` returns the full run **and** its event trace, so the browser
renders a completed run from one response — no follow-up request. That keeps the
app usable when the repository is stateless (Vercel).
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models.dispatch import DispatchRequest
from app.orchestration.exceptions import DispatchError, MissingBriefContextError
from app.persistence.base import RunRepository
from app.persistence.null import NullRunRepository
from app.providers.exceptions import ModelProviderError
from app.service import DecisionForgeService
from app.tools.exceptions import SearchError
from app.web.api_models import (
    ErrorResponse,
    RecentRuns,
    RunResult,
    RunSummary,
)

_WEB_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _WEB_DIR / "static"
_INDEX_HTML = _WEB_DIR / "templates" / "index.html"

_RECENT_LIMIT = 25


def create_app(
    service: DecisionForgeService,
    repository: RunRepository,
    *,
    model_provider_label: str = "mock",
) -> FastAPI:
    """Build the app around an already-constructed service + repository."""
    persistence_enabled = not isinstance(repository, NullRunRepository)

    app = FastAPI(title="DecisionForge", docs_url="/api/docs")
    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR), check_dir=False),
        name="static",
    )

    @app.get("/", include_in_schema=False)
    async def index():
        if _INDEX_HTML.is_file():
            return FileResponse(_INDEX_HTML)
        # Static assets weren't bundled by the host; the JSON API still works.
        return JSONResponse(
            {
                "detail": "UI assets are unavailable on this host; the JSON API "
                "at /api/runs and /api/health still works.",
                "error_type": "UIAssetsMissing",
            },
            status_code=200,
        )

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        return {
            "status": "ok",
            "model_provider": model_provider_label,
            "persistence_enabled": persistence_enabled,
        }

    @app.post("/api/runs", response_model=RunResult)
    async def create_run(request: DispatchRequest):
        run_id = str(uuid.uuid4())
        try:
            outcome = await service.run(request, run_id=run_id)
        except MissingBriefContextError as exc:
            return _error_response(400, exc, run_id)
        except (DispatchError, ModelProviderError, SearchError) as exc:
            return _error_response(500, exc, run_id)
        except Exception as exc:  # noqa: BLE001 - last-resort safe mapping
            return _error_response(500, exc, run_id)
        return RunResult.from_run(outcome.record, outcome.events)

    @app.get("/api/runs", response_model=RecentRuns)
    async def list_runs() -> RecentRuns:
        records = repository.list_recent_runs(limit=_RECENT_LIMIT)
        return RecentRuns(runs=[RunSummary.from_record(r) for r in records])

    @app.get("/api/runs/{run_id}", response_model=RunResult)
    async def get_run(run_id: str):
        record = repository.get_run(run_id)
        if record is None:
            return JSONResponse(
                status_code=404,
                content=ErrorResponse(
                    detail=f"run {run_id!r} not found",
                    error_type="RunNotFound",
                ).model_dump(),
            )
        events = repository.get_events(run_id)
        return RunResult.from_run(record, events)

    return app


def _error_response(status: int, exc: Exception, run_id: str) -> JSONResponse:
    message = str(exc).strip() or exc.__class__.__name__
    return JSONResponse(
        status_code=status,
        content=ErrorResponse(
            detail=message,
            error_type=exc.__class__.__name__,
            run_id=run_id,
        ).model_dump(),
    )
