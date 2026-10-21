"""Model-provider configuration.

Configuration must be constructible with **no credentials** so the whole project
runs and tests in mock mode for free. Anthropic-specific requirements are
enforced later, when the Anthropic provider is actually constructed
(see ``app/providers/factory.py``), not here.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import Enum

from pydantic import BaseModel, Field

from app.env import load_dotenv
from app.providers.exceptions import ModelConfigurationError
from app.providers.replay import ReplayMode
from app.providers.usage import DEFAULT_LIFETIME_LIMIT_USD, DEFAULT_MODEL, RunBudget

#: Default output-token ceiling for a single generation. Output tokens are the
#: expensive half of a call, and this cap bounds every call's worst-case cost.
#: 1200 leaves headroom for a full decision model (800 truncated one live) while
#: a three-call run still fits the default $0.002 budget.
DEFAULT_MAX_TOKENS = 1200

#: Default reasoning effort sent to models that accept it.
DEFAULT_EFFORT = "low"

#: Where the lifetime live-spend total is kept (``data/`` is git-ignored).
DEFAULT_SPEND_LEDGER_PATH = "data/spend.json"

#: Default record/replay cassette (committed, so recorded runs replay anywhere).
DEFAULT_REPLAY_CASSETTE = "cassettes/default.json"

_TRUE = {"1", "true", "yes", "on"}
_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


class ModelProviderType(str, Enum):
    """Selectable model-provider backends."""

    MOCK = "mock"
    ANTHROPIC = "anthropic"


class ModelConfig(BaseModel):
    """Provider selection plus optional tuning values.

    The default constructs a mock configuration; no environment variables and no
    API key are required.
    """

    provider: ModelProviderType = ModelProviderType.MOCK
    model: str | None = None
    api_key: str | None = None
    max_tokens: int = Field(default=DEFAULT_MAX_TOKENS, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    #: ``None`` omits the parameter (model default).
    effort: str | None = DEFAULT_EFFORT
    disable_thinking: bool = True
    run_budget: RunBudget = Field(default_factory=RunBudget)
    spend_limit_usd: float = Field(default=DEFAULT_LIFETIME_LIMIT_USD, gt=0.0)
    spend_ledger_path: str = DEFAULT_SPEND_LEDGER_PATH
    replay_mode: ReplayMode = ReplayMode.OFF
    replay_cassette: str = DEFAULT_REPLAY_CASSETTE

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        use_dotenv: bool = True,
    ) -> "ModelConfig":
        """Build a config from environment variables.

        Reads ``MODEL_PROVIDER`` (default ``mock``), ``ANTHROPIC_API_KEY``,
        ``ANTHROPIC_MODEL`` (default ``claude-haiku-5-5`` when unset), and the
        optional tuning values ``ANTHROPIC_MAX_TOKENS``, ``ANTHROPIC_TEMPERATURE``,
        ``ANTHROPIC_EFFORT`` (``low``; ``none`` omits it) and
        ``ANTHROPIC_DISABLE_THINKING`` (``true``). Cost guards:
        ``RUN_BUDGET_USD`` (0.002), ``RUN_MAX_LLM_CALLS`` (3), ``SPEND_LIMIT_USD``
        (0.03, lifetime) and ``SPEND_LEDGER_PATH`` (``data/spend.json``).
        Record/replay: ``REPLAY_MODE`` (``off`` | ``record`` | ``replay`` |
        ``auto``) and ``REPLAY_CASSETTE`` (``cassettes/default.json``).

        When ``env`` is not given, the nearest ``.env`` file at or above the
        current working directory is loaded into ``os.environ`` first (real
        environment variables are never overwritten). Pass an explicit ``env``
        mapping, or ``use_dotenv=False``, to skip that.

        With no variables set, this returns a mock configuration and never
        raises. An unrecognised ``MODEL_PROVIDER`` value raises
        ``ModelConfigurationError``.
        """
        if env is None:
            if use_dotenv:
                load_dotenv()
            source: Mapping[str, str] = os.environ
        else:
            source = env

        raw_provider = (source.get("MODEL_PROVIDER") or "mock").strip().lower() or "mock"
        try:
            provider = ModelProviderType(raw_provider)
        except ValueError as exc:
            allowed = ", ".join(p.value for p in ModelProviderType)
            raise ModelConfigurationError(
                f"Unknown MODEL_PROVIDER {raw_provider!r}; expected one of: {allowed}"
            ) from exc

        api_key = source.get("ANTHROPIC_API_KEY") or None
        model = source.get("ANTHROPIC_MODEL") or None

        max_tokens = _parse_int(
            source.get("ANTHROPIC_MAX_TOKENS"), DEFAULT_MAX_TOKENS, "ANTHROPIC_MAX_TOKENS"
        )
        temperature = _parse_float(source.get("ANTHROPIC_TEMPERATURE"), "ANTHROPIC_TEMPERATURE")

        raw_effort = (source.get("ANTHROPIC_EFFORT") or DEFAULT_EFFORT).strip().lower()
        if raw_effort == "none":
            effort = None
        elif raw_effort in _EFFORTS:
            effort = raw_effort
        else:
            raise ModelConfigurationError(
                f"ANTHROPIC_EFFORT must be one of {sorted(_EFFORTS)} or 'none', "
                f"got {raw_effort!r}"
            )
        raw_thinking = source.get("ANTHROPIC_DISABLE_THINKING")
        disable_thinking = (
            True if raw_thinking is None or not raw_thinking.strip()
            else raw_thinking.strip().lower() in _TRUE
        )

        default_budget = RunBudget()
        run_budget = RunBudget(
            max_usd=_parse_float(source.get("RUN_BUDGET_USD"), "RUN_BUDGET_USD")
            or default_budget.max_usd,
            max_calls=_parse_int(
                source.get("RUN_MAX_LLM_CALLS"), default_budget.max_calls, "RUN_MAX_LLM_CALLS"
            ),
        )

        raw_replay = (source.get("REPLAY_MODE") or "off").strip().lower() or "off"
        try:
            replay_mode = ReplayMode(raw_replay)
        except ValueError as exc:
            allowed = ", ".join(m.value for m in ReplayMode)
            raise ModelConfigurationError(
                f"Unknown REPLAY_MODE {raw_replay!r}; expected one of: {allowed}"
            ) from exc

        return cls(
            provider=provider,
            model=model,
            api_key=api_key,
            max_tokens=max_tokens,
            temperature=temperature,
            replay_mode=replay_mode,
            replay_cassette=source.get("REPLAY_CASSETTE") or DEFAULT_REPLAY_CASSETTE,
            effort=effort,
            disable_thinking=disable_thinking,
            run_budget=run_budget,
            spend_limit_usd=_parse_float(source.get("SPEND_LIMIT_USD"), "SPEND_LIMIT_USD")
            or DEFAULT_LIFETIME_LIMIT_USD,
            spend_ledger_path=source.get("SPEND_LEDGER_PATH") or DEFAULT_SPEND_LEDGER_PATH,
        )

    @property
    def resolved_model(self) -> str:
        """The model a real call would use (``model`` or the cheap default)."""
        return self.model or DEFAULT_MODEL


def _parse_int(raw: str | None, default: int, name: str) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ModelConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


def _parse_float(raw: str | None, name: str) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise ModelConfigurationError(f"{name} must be a number, got {raw!r}") from exc
