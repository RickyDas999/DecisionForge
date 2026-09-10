"""Tiny zero-dependency ``.env`` loader.

DecisionForge stays framework-free, so instead of pulling in ``python-dotenv`` we
parse a small, predictable subset of the ``.env`` format:

- ``KEY=value`` one per line
- blank lines and lines starting with ``#`` are ignored
- an optional leading ``export`` is stripped (``export KEY=value``)
- surrounding single or double quotes on the value are stripped
- everything else in the value is kept verbatim (no interpolation, no inline
  comment stripping)

By default, existing ``os.environ`` values are **not** overwritten, so a real
environment variable always wins over the file.
"""

from __future__ import annotations

import os
from pathlib import Path

_loaded_paths: set[str] = set()


def find_dotenv(start: Path | None = None) -> Path | None:
    """Walk upward from ``start`` (default: cwd) looking for a ``.env`` file."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / ".env"
        if candidate.is_file():
            return candidate
    return None


def parse_dotenv(text: str) -> dict[str, str]:
    """Parse ``.env`` file contents into a plain dict (no side effects)."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        values[key] = value
    return values


def load_dotenv(
    path: Path | str | None = None,
    *,
    override: bool = False,
) -> dict[str, str]:
    """Load a ``.env`` file into ``os.environ`` and return the parsed values.

    ``path`` may be a file or a directory; when omitted, the nearest ``.env`` at
    or above the current working directory is used. Missing files are a no-op.
    Each resolved path is loaded at most once per process.
    """
    if path is None:
        resolved = find_dotenv()
    else:
        candidate = Path(path)
        resolved = candidate / ".env" if candidate.is_dir() else candidate

    if resolved is None or not resolved.is_file():
        return {}

    key = str(resolved.resolve())
    if key in _loaded_paths and not override:
        return {}
    _loaded_paths.add(key)

    values = parse_dotenv(resolved.read_text(encoding="utf-8"))
    for name, value in values.items():
        if override or name not in os.environ:
            os.environ[name] = value
    return values
