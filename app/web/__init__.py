"""Local FastAPI web layer. Adds zero LLM calls."""

from app.web.app import create_app

__all__ = ["create_app"]
