"""Run persistence. Deterministic file I/O — no LLM, no agents.

``SQLiteRunRepository`` keeps durable local history; ``NullRunRepository`` is
stateless (for deployments without a writable store). Both satisfy
``RunRepository``.
"""

from app.persistence.base import RunRepository
from app.persistence.null import NullRunRepository
from app.persistence.sqlite import (
    DB_PATH_ENV_VAR,
    DEFAULT_DB_PATH,
    SQLiteRunRepository,
    resolve_db_path,
)

__all__ = [
    "DB_PATH_ENV_VAR",
    "DEFAULT_DB_PATH",
    "NullRunRepository",
    "RunRepository",
    "SQLiteRunRepository",
    "resolve_db_path",
]
