"""Per-run token accounting and a hard dollar budget.

Every model call in a run is recorded in a :class:`UsageLedger` (tokens, dollar
cost, whether it was real, replayed, or estimated). Before a **real** call the
provider asks the ledger whether the call's *worst case* still fits the run's
budget — worst case meaning the full input plus the full ``max_tokens`` of
output. If it does not, :class:`BudgetExceededError` is raised and nothing is
sent. A run therefore can never spend more than ``RunBudget.max_usd``.

The active ledger is carried in a :class:`contextvars.ContextVar`, so one shared
provider instance can serve concurrent runs while each run gets its own ledger.
With no active ledger, providers record nothing and enforce nothing.
"""

from __future__ import annotations

import contextvars
import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field

from app.providers.exceptions import ModelProviderError

#: Default model for real calls — the cheapest current Claude model.
DEFAULT_MODEL = "claude-haiku-5-5"

#: First-party API prices in USD per million tokens: (input, output).
#: Haiku 5.5 is quoted for prompts up to 100K tokens (DecisionForge stays far below).
MODEL_PRICES_PER_MTOK: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}

#: Unknown models are priced at the Opus rate so the budget errs on the safe side.
_FALLBACK_PRICE = MODEL_PRICES_PER_MTOK["claude-opus-5-5"]

#: Conservative characters-per-token ratio for pre-call input estimates.
#: Real English text averages ~4 chars/token; using 3 over-estimates on purpose.
_CHARS_PER_TOKEN = 3


class BudgetExceededError(ModelProviderError):
    """A model call was refused because it could push the run over budget."""


class CallSource(str, Enum):
    """Where a recorded call's output came from."""

    LIVE = "live"  # a billed API request
    REPLAYED = "replayed"  # served from a record/replay cassette (free)
    ESTIMATED = "estimated"  # offline mock/demo call; tokens are estimates (free)


class CallRecord(BaseModel):
    """One model call."""

    operation: str
    model: str
    source: CallSource
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    #: Dollars actually charged (0 unless ``source`` is ``live``).
    cost_usd: float = Field(ge=0.0)
    #: What the call would cost live at the model's price.
    list_cost_usd: float = Field(ge=0.0)


class RunBudget(BaseModel):
    """Hard ceilings for one run."""

    max_usd: float = Field(default=0.002, gt=0.0)
    max_calls: int = Field(default=3, ge=1)


class UsageSummary(BaseModel):
    """Totals for one run, safe to serialize into API responses and events."""

    calls: int
    live_calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    list_cost_usd: float
    budget_usd: float
    max_calls: int


def price_for(model: str) -> tuple[float, float]:
    """``(input, output)`` USD per million tokens for ``model``."""
    return MODEL_PRICES_PER_MTOK.get(model, _FALLBACK_PRICE)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = price_for(model)
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000


def estimate_tokens(*texts: str) -> int:
    """A deliberately high token estimate for ``texts`` (no network, no tokenizer)."""
    chars = sum(len(t) for t in texts)
    return -(-chars // _CHARS_PER_TOKEN)  # ceiling division


class UsageLedger:
    """Collects the calls of one run and enforces its :class:`RunBudget`."""

    def __init__(
        self,
        budget: RunBudget | None = None,
        *,
        on_record: Callable[[CallRecord], None] | None = None,
    ) -> None:
        self.budget = budget or RunBudget()
        self.calls: list[CallRecord] = []
        self._on_record = on_record

    @property
    def spent_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    def check(self, *, model: str, input_tokens: int, max_output_tokens: int) -> None:
        """Raise unless a live call with this worst case fits the remaining budget."""
        if len(self.calls) >= self.budget.max_calls:
            raise BudgetExceededError(
                f"run already made {len(self.calls)} model calls "
                f"(limit {self.budget.max_calls})"
            )
        worst = cost_usd(model, input_tokens, max_output_tokens)
        if self.spent_usd + worst > self.budget.max_usd:
            raise BudgetExceededError(
                f"call could cost up to ${worst:.5f}; run has spent "
                f"${self.spent_usd:.5f} of its ${self.budget.max_usd:.5f} budget"
            )

    def record(
        self,
        *,
        operation: str,
        model: str,
        source: CallSource,
        input_tokens: int,
        output_tokens: int,
    ) -> CallRecord:
        list_cost = cost_usd(model, input_tokens, output_tokens)
        call = CallRecord(
            operation=operation,
            model=model,
            source=source,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=list_cost if source is CallSource.LIVE else 0.0,
            list_cost_usd=list_cost,
        )
        self.calls.append(call)
        if self._on_record is not None:
            self._on_record(call)
        return call

    def summary(self) -> UsageSummary:
        return UsageSummary(
            calls=len(self.calls),
            live_calls=sum(1 for c in self.calls if c.source is CallSource.LIVE),
            input_tokens=sum(c.input_tokens for c in self.calls),
            output_tokens=sum(c.output_tokens for c in self.calls),
            cost_usd=round(self.spent_usd, 8),
            list_cost_usd=round(sum(c.list_cost_usd for c in self.calls), 8),
            budget_usd=self.budget.max_usd,
            max_calls=self.budget.max_calls,
        )


_ACTIVE_LEDGER: contextvars.ContextVar[UsageLedger | None] = contextvars.ContextVar(
    "decisionforge_usage_ledger", default=None
)


def active_ledger() -> UsageLedger | None:
    """The ledger of the run currently executing in this context, if any."""
    return _ACTIVE_LEDGER.get()


@contextmanager
def metered(ledger: UsageLedger) -> Iterator[UsageLedger]:
    """Make ``ledger`` the active ledger for the duration of the block."""
    token = _ACTIVE_LEDGER.set(ledger)
    try:
        yield ledger
    finally:
        _ACTIVE_LEDGER.reset(token)


def record_estimated(
    *, operation: str, model: str, prompts: tuple[str, ...], output: str
) -> None:
    """Record a free offline call with estimated tokens (no-op without a ledger)."""
    ledger = active_ledger()
    if ledger is None:
        return
    ledger.record(
        operation=operation,
        model=model,
        source=CallSource.ESTIMATED,
        input_tokens=estimate_tokens(*prompts),
        output_tokens=estimate_tokens(output),
    )


#: Default lifetime cap on live spend, across every run on this machine.
DEFAULT_LIFETIME_LIMIT_USD = 0.03


class LifetimeSpend:
    """A tiny on-disk running total of live spend with a hard ceiling.

    Guards against accidental overspend across many runs, scripts, and eval
    passes: before each live call the provider checks the call's worst case
    against ``limit_usd``; after the call the real cost is added to the file.
    Raise the limit deliberately (``SPEND_LIMIT_USD``) when you mean to spend more.
    """

    def __init__(self, path: str | Path, limit_usd: float = DEFAULT_LIFETIME_LIMIT_USD) -> None:
        if limit_usd <= 0:
            raise ValueError("limit_usd must be positive")
        self.path = Path(path)
        self.limit_usd = limit_usd

    @property
    def total_usd(self) -> float:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return 0.0
        return float(data.get("total_usd", 0.0))

    def check(self, worst_case_usd: float) -> None:
        total = self.total_usd
        if total + worst_case_usd > self.limit_usd:
            raise BudgetExceededError(
                f"lifetime spend ${total:.5f} + this call's worst case "
                f"${worst_case_usd:.5f} would exceed the ${self.limit_usd:.2f} cap "
                f"({self.path}); raise SPEND_LIMIT_USD to allow more"
            )

    def add(self, amount_usd: float) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"total_usd": round(self.total_usd + amount_usd, 8)}
        self.path.write_text(json.dumps(data), encoding="utf-8")
