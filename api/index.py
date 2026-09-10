"""Vercel Python entrypoint.

Vercel discovers the module-level ``app`` (an ASGI ``FastAPI`` instance) and
serves it. All business logic lives in ``app/`` — this file only wires it up.

Importing this module is side-effect-safe: no network call, no LLM call, no
SQLite file, no credentials required in the default (mock) mode. Behaviour is
controlled entirely by environment variables (see ``app/web/deployment.py``).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repository root importable regardless of how the host invokes this
# file (Vercel runs functions from the project root, but be explicit).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.web.deployment import create_deployment_app  # noqa: E402

app = create_deployment_app()
