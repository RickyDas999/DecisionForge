"""Every run is metered: llm.call events, a usage summary, and a hard budget."""

from __future__ import annotations

import asyncio

import pytest

from app.models.dispatch import DispatchRequest
from app.models.persistence import EventType
from app.persistence.null import NullRunRepository
from app.providers.usage import BudgetExceededError, RunBudget, active_ledger
from app.runtime import create_dispatcher
from app.service import DecisionForgeService
from app.web.api_models import RunResult
from app.web.demo_provider import DemoModelProvider, DemoSearchProvider


def _service(budget: RunBudget | None = None) -> DecisionForgeService:
    dispatcher = create_dispatcher(DemoModelProvider(), search_provider=DemoSearchProvider())
    return DecisionForgeService(dispatcher, NullRunRepository(), run_budget=budget)


def test_run_reports_estimated_usage_per_call() -> None:
    outcome = asyncio.run(_service().run(DispatchRequest(user_request="Postgres vs MongoDB?")))
    calls = [e for e in outcome.events if e.event_type is EventType.LLM_CALL]
    assert len(calls) == 2  # routing + specialist
    assert all(e.metadata["source"] == "estimated" for e in calls)
    assert outcome.usage is not None
    assert outcome.usage.calls == 2
    assert outcome.usage.cost_usd == 0.0
    assert 0 < outcome.usage.list_cost_usd < 0.002  # well under the default run budget

    view = RunResult.from_run(outcome.record, outcome.events)
    assert view.usage["calls"] == 2


class _CheckingDemo(DemoModelProvider):
    """Checks the budget before each call, as the live provider does."""

    async def generate_structured(self, **kwargs):
        active_ledger().check(model="claude-haiku-5-5", input_tokens=10, max_output_tokens=10)
        return await super().generate_structured(**kwargs)


def test_call_limit_fails_the_run_cleanly() -> None:
    repo = NullRunRepository()
    service = DecisionForgeService(
        create_dispatcher(_CheckingDemo()), repo, run_budget=RunBudget(max_calls=1)
    )
    with pytest.raises(BudgetExceededError):
        asyncio.run(service.run(DispatchRequest(user_request="Explain observability")))
