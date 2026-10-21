"""Record/replay wrapper: pay for each distinct prompt once, replay it for free.

A *cassette* is a JSON file mapping a hash of ``(model, operation, system prompt,
user prompt, response schema)`` to the output the model produced and the tokens
it used. Modes:

* ``record`` — always call the wrapped provider and (over)write the entry.
* ``replay`` — never call a model; a missing entry raises :class:`CassetteMissError`.
  No API key needed: this is how tests, CI, and the hosted demo show *real*
  recorded model output at zero cost.
* ``auto`` — replay on a hit, otherwise call the wrapped provider and record.

Replayed calls are entered in the active :class:`UsageLedger` as ``replayed``
(``cost_usd == 0``) with the originally recorded token counts, so the trace still
shows what the call *would* cost live.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.providers.exceptions import ModelConfigurationError, ModelProviderError
from app.providers.model import ModelProvider
from app.providers.usage import CallSource, active_ledger, estimate_tokens

_CASSETTE_VERSION = 1


class ReplayMode(str, Enum):
    OFF = "off"
    RECORD = "record"
    REPLAY = "replay"
    AUTO = "auto"


class CassetteMissError(ModelProviderError):
    """Replay mode was asked for a prompt that was never recorded."""


def cassette_key(
    model: str, operation: str, system_prompt: str, user_prompt: str, schema: str
) -> str:
    payload = json.dumps(
        [model, operation, system_prompt, user_prompt, schema], separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


class ReplayModelProvider(ModelProvider):
    """Wraps a provider with a cassette file. See the module docstring."""

    def __init__(
        self,
        inner: ModelProvider | None,
        cassette_path: str | Path,
        *,
        mode: ReplayMode = ReplayMode.AUTO,
        model: str,
    ) -> None:
        if mode is ReplayMode.OFF:
            raise ModelConfigurationError("ReplayModelProvider needs a mode other than 'off'")
        if inner is None and mode is not ReplayMode.REPLAY:
            raise ModelConfigurationError(f"replay mode {mode.value!r} needs a provider to record from")
        self._inner = inner
        self._path = Path(cassette_path)
        self._mode = mode
        self._model = model
        self._entries: dict[str, dict[str, Any]] = self._load()

    @property
    def model(self) -> str:
        return self._model

    @property
    def mode(self) -> ReplayMode:
        return self._mode

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        return await self._through(
            "generate_text",
            system_prompt,
            user_prompt,
            schema="",
            call=lambda: self._inner.generate_text(  # type: ignore[union-attr]
                system_prompt=system_prompt, user_prompt=user_prompt
            ),
            encode=lambda out: out,
            decode=lambda raw: raw,
        )

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        return await self._through(
            "generate_structured",
            system_prompt,
            user_prompt,
            schema=response_model.__name__,
            call=lambda: self._inner.generate_structured(  # type: ignore[union-attr]
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=response_model,
            ),
            encode=lambda out: out.model_dump_json(),
            decode=response_model.model_validate_json,
        )

    async def _through(
        self,
        operation: str,
        system_prompt: str,
        user_prompt: str,
        *,
        schema: str,
        call: Callable[[], Awaitable[Any]],
        encode: Callable[[Any], str],
        decode: Callable[[str], Any],
    ) -> Any:
        key = cassette_key(self._model, operation, system_prompt, user_prompt, schema)
        entry = self._entries.get(key)
        ledger = active_ledger()

        if entry is not None and self._mode is not ReplayMode.RECORD:
            if ledger is not None:
                ledger.record(
                    operation=operation,
                    model=self._model,
                    source=CallSource.REPLAYED,
                    input_tokens=entry["input_tokens"],
                    output_tokens=entry["output_tokens"],
                )
            return decode(entry["output"])

        if self._mode is ReplayMode.REPLAY:
            raise CassetteMissError(
                f"no recording for this {operation} prompt in {self._path} "
                "(record it with REPLAY_MODE=auto)"
            )

        calls_before = len(ledger.calls) if ledger is not None else 0
        output = await call()
        encoded = encode(output)
        if ledger is not None and len(ledger.calls) > calls_before:
            recorded = ledger.calls[-1]
            input_tokens, output_tokens = recorded.input_tokens, recorded.output_tokens
        else:
            input_tokens = estimate_tokens(system_prompt, user_prompt)
            output_tokens = estimate_tokens(encoded)

        self._entries[key] = {
            "operation": operation,
            "model": self._model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "output": encoded,
        }
        self._save()
        return output

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if data.get("version") != _CASSETTE_VERSION:
            raise ModelConfigurationError(f"unsupported cassette version in {self._path}")
        return dict(data.get("entries", {}))

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {"version": _CASSETTE_VERSION, "entries": self._entries}
        self._path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
