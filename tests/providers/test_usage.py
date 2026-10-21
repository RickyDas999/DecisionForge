"""Tests for per-run usage accounting, the run budget, and the lifetime cap."""

from __future__ import annotations

import pytest

from app.providers.usage import (
    BudgetExceededError,
    CallSource,
    LifetimeSpend,
    RunBudget,
    UsageLedger,
    active_ledger,
    cost_usd,
    estimate_tokens,
    metered,
    record_estimated,
)


def test_haiku_5_5_pricing() -> None:
    # 1M input at $0.10 + 1M output at $0.50
    assert cost_usd("claude-haiku-5-5", 1_000_000, 1_000_000) == pytest.approx(0.60)


def test_unknown_model_priced_conservatively() -> None:
    assert cost_usd("some-future-model", 1_000_000, 0) == pytest.approx(4.00)


def test_estimate_overcounts() -> None:
    assert estimate_tokens("abcd" * 30) == 40  # 120 chars / 3


def test_live_calls_are_charged_others_are_free() -> None:
    ledger = UsageLedger()
    ledger.record(operation="x", model="claude-haiku-5-5", source=CallSource.LIVE,
                  input_tokens=2000, output_tokens=400)
    ledger.record(operation="x", model="claude-haiku-5-5", source=CallSource.REPLAYED,
                  input_tokens=2000, output_tokens=400)
    summary = ledger.summary()
    assert summary.calls == 2
    assert summary.live_calls == 1
    assert summary.cost_usd == pytest.approx(0.0004)
    assert summary.list_cost_usd == pytest.approx(0.0008)


def test_check_refuses_call_that_could_exceed_budget() -> None:
    ledger = UsageLedger(RunBudget(max_usd=0.001))
    ledger.check(model="claude-haiku-5-5", input_tokens=3000, max_output_tokens=800)
    with pytest.raises(BudgetExceededError):
        # worst case 0.0003 + 0.002 > 0.001
        ledger.check(model="claude-haiku-5-5", input_tokens=3000, max_output_tokens=4000)


def test_check_counts_prior_spend() -> None:
    ledger = UsageLedger(RunBudget(max_usd=0.001))
    ledger.record(operation="x", model="claude-haiku-5-5", source=CallSource.LIVE,
                  input_tokens=3000, output_tokens=800)  # 0.0007
    with pytest.raises(BudgetExceededError):
        ledger.check(model="claude-haiku-5-5", input_tokens=3000, max_output_tokens=800)


def test_check_enforces_call_limit() -> None:
    ledger = UsageLedger(RunBudget(max_calls=1))
    ledger.record(operation="x", model="m", source=CallSource.ESTIMATED,
                  input_tokens=1, output_tokens=1)
    with pytest.raises(BudgetExceededError):
        ledger.check(model="claude-haiku-5-5", input_tokens=1, max_output_tokens=1)


def test_metered_sets_and_resets_active_ledger() -> None:
    ledger = UsageLedger()
    assert active_ledger() is None
    with metered(ledger):
        assert active_ledger() is ledger
        record_estimated(operation="op", model="claude-haiku-5-5", prompts=("abc",), output="d")
    assert active_ledger() is None
    assert ledger.calls[0].source is CallSource.ESTIMATED
    assert ledger.calls[0].cost_usd == 0.0


def test_on_record_callback_receives_each_call() -> None:
    seen = []
    ledger = UsageLedger(on_record=seen.append)
    ledger.record(operation="op", model="m", source=CallSource.LIVE,
                  input_tokens=1, output_tokens=1)
    assert len(seen) == 1


def test_lifetime_spend_accumulates_and_caps(tmp_path) -> None:
    spend = LifetimeSpend(tmp_path / "spend.json", limit_usd=0.001)
    assert spend.total_usd == 0.0
    spend.check(0.0009)
    spend.add(0.0009)
    assert LifetimeSpend(tmp_path / "spend.json").total_usd == pytest.approx(0.0009)
    with pytest.raises(BudgetExceededError):
        spend.check(0.0002)


def test_default_cap_lets_a_close_call_comparison_fit_the_default_budget() -> None:
    """Routing, then two decision-model extractions, at realistic input sizes."""
    from app.providers.config import DEFAULT_MAX_TOKENS

    ledger = UsageLedger(RunBudget())
    for estimated_input, actual_in, actual_out in ((900, 700, 40), (1800, 1400, 600), (1900, 1500, 600)):
        ledger.check(model="claude-haiku-5-5", input_tokens=estimated_input,
                     max_output_tokens=DEFAULT_MAX_TOKENS)
        ledger.record(operation="x", model="claude-haiku-5-5", source=CallSource.LIVE,
                      input_tokens=actual_in, output_tokens=actual_out)
    assert ledger.summary().cost_usd < RunBudget().max_usd
