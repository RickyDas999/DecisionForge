"""Small shared field types used across model modules."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator


def _require_nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be empty or whitespace")
    return value


#: A string field that must contain at least one non-whitespace character.
NonBlankStr = Annotated[str, AfterValidator(_require_nonblank)]
