"""The comparison agent's adaptive second sample on close calls."""

from __future__ import annotations

import asyncio

from app.agents.base import AgentRuntimeContext
from app.agents.comparison import SECOND_OPINION_NOTE, ComparisonAgent
from app.models.decision import Criterion, DecisionModel, Score
from app.models.specialists import ComparisonInput
from app.providers.mock import MockModelProvider
from app.providers.usage import BudgetExceededError


def _model(a: tuple[float, float], b: tuple[float, float]) -> DecisionModel:
    return DecisionModel(
        question="A or B?",
        options=["A", "B"],
        criteria=[Criterion(name="Fit", weight=1.0)],
        scores=[Score(option="A", criterion="Fit", low=a[0], high=a[1]),
                Score(option="B", criterion="Fit", low=b[0], high=b[1])],
    )


CLEAR = _model((8, 9), (2, 3))  # robust: A always wins
CLOSE = _model((5, 7), (4, 7))  # toss-up / leaning


def _run(provider, adaptive=True):
    agent = ComparisonAgent(provider, decision_engine=True, adaptive_samples=adaptive)
    return asyncio.run(agent.run(ComparisonInput(user_request="A or B?"),
                                 AgentRuntimeContext(run_id="t")))


def test_clear_decision_makes_one_call() -> None:
    provider = MockModelProvider(structured_responses=[CLEAR])
    response = _run(provider)
    assert len(provider.calls) == 1
    assert response.decision_report.samples == 1


def test_close_call_takes_a_second_independent_sample() -> None:
    second = _model((3, 6), (6, 8))
    provider = MockModelProvider(structured_responses=[CLOSE, second])
    response = _run(provider)
    assert len(provider.calls) == 2
    assert provider.calls[1].user_prompt.endswith(SECOND_OPINION_NOTE)
    report = response.decision_report
    assert report.samples == 2 and report.disagreement > 0
    a = next(s for s in response.decision_model.scores if s.option == "A")
    assert (a.low, a.high) == (3, 7)  # envelope of both samples


def test_adaptive_off_never_resamples() -> None:
    provider = MockModelProvider(structured_responses=[CLOSE])
    _run(provider, adaptive=False)
    assert len(provider.calls) == 1


class _FailsSecondTime(MockModelProvider):
    async def generate_structured(self, **kwargs):
        if self.calls:
            self.calls.append(None)
            raise BudgetExceededError("over budget")
        return await super().generate_structured(**kwargs)


def test_failed_second_sample_keeps_the_first_answer() -> None:
    response = _run(_FailsSecondTime(structured_responses=[CLOSE]))
    assert response.decision_report.samples == 1
    assert response.recommendation


def test_citations_to_unseen_results_are_removed_and_reported() -> None:
    from app.models.search import SearchResult

    cited = CLEAR.model_copy(update={"scores": [
        s.model_copy(update={"source": 1 if s.option == "A" else 4}) for s in CLEAR.scores
    ]})
    provider = MockModelProvider(structured_responses=[cited])
    agent = ComparisonAgent(provider, decision_engine=True, adaptive_samples=True)
    evidence = [SearchResult(title="t", url="https://e.com", snippet="s")]
    response = asyncio.run(agent.run(
        ComparisonInput(user_request="A or B?", evidence=evidence), AgentRuntimeContext(run_id="t")))
    report = response.decision_report
    assert report.invalid_citations == 1
    assert report.cited_scores == 1
    assert any("never shown" in note for note in response.limitations)
