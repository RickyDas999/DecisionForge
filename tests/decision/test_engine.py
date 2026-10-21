"""Tests for the deterministic decision engine, its summary, and the agent mode."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.agents.base import AgentRuntimeContext
from app.agents.comparison import ComparisonAgent
from app.decision import analyze, to_comparison_response
from app.models.decision import Criterion, DecisionModel, Score
from app.models.specialists import ComparisonInput
from app.providers.mock import MockModelProvider


def _model(**overrides) -> DecisionModel:
    data = dict(
        question="Postgres or Mongo?",
        options=["PostgreSQL", "MongoDB"],
        criteria=[Criterion(name="Data integrity", weight=0.4),
                  Criterion(name="Schema flexibility", weight=0.2),
                  Criterion(name="Scalability", weight=0.4)],
        scores=[
            Score(option="PostgreSQL", criterion="Data integrity", low=8, high=10, note="ACID"),
            Score(option="MongoDB", criterion="Data integrity", low=5, high=7),
            Score(option="PostgreSQL", criterion="Schema flexibility", low=4, high=6),
            Score(option="MongoDB", criterion="Schema flexibility", low=8, high=10, source=1),
            Score(option="PostgreSQL", criterion="Scalability", low=6, high=8),
            Score(option="MongoDB", criterion="Scalability", low=6, high=9),
        ],
    )
    data.update(overrides)
    return DecisionModel(**data)


def test_expected_scores_are_weighted_midpoints() -> None:
    report = analyze(_model())
    scores = {r.option: r.expected_score for r in report.ranking}
    assert scores == {"PostgreSQL": pytest.approx(7.4), "MongoDB": pytest.approx(7.2)}
    assert report.weights == {"Data integrity": 0.4, "Schema flexibility": 0.2, "Scalability": 0.4}


def test_flip_point_is_solved_exactly() -> None:
    flips = {p.criterion: p for p in analyze(_model()).flip_points}
    flex = flips["Schema flexibility"]
    # Rest scores 8.0 vs 6.75; crossing at 1.25 / (1.25 + 4) = 0.238.
    assert flex.flip_weight == pytest.approx(0.238, abs=1e-3)
    assert flex.new_winner == "MongoDB" and flex.direction == "increase"
    assert flips["Data integrity"].direction == "decrease"


def test_flip_points_sorted_most_fragile_first() -> None:
    flips = analyze(_model()).flip_points
    distances = [abs(p.flip_weight - p.current_weight) for p in flips]
    assert distances == sorted(distances)


def test_close_call_is_a_tossup_and_dominance_is_robust() -> None:
    assert analyze(_model()).verdict in {"toss-up", "leaning"}
    dominant = _model(scores=[
        Score(option=o, criterion=c, low=lo, high=lo + 1)
        for o, lo in (("PostgreSQL", 8), ("MongoDB", 2))
        for c in ("Data integrity", "Schema flexibility", "Scalability")
    ])
    report = analyze(dominant)
    assert report.verdict == "robust"
    assert report.win_probability == 1.0
    assert report.flip_points == []  # nothing can flip a dominated option


def test_analysis_is_deterministic() -> None:
    assert analyze(_model()) == analyze(_model())


def test_missing_cells_become_gaps_and_names_match_loosely() -> None:
    model = _model(scores=[
        Score(option="postgresql ", criterion="DATA INTEGRITY", low=8, high=10),
        Score(option="Unknown", criterion="Scalability", low=1, high=2),
    ])
    report = analyze(model)
    assert report.total_scores == 1
    assert len(report.gaps) == 5
    assert "MongoDB / Scalability" in report.gaps


def test_reversed_bounds_are_reordered_and_duplicates_rejected() -> None:
    assert Score(option="a", criterion="b", low=7, high=3).low == 3
    with pytest.raises(ValidationError):
        _model(options=["Redis", "redis"])


def test_summary_text_matches_the_numbers() -> None:
    model = _model()
    report = analyze(model)
    response = to_comparison_response(model, report)
    assert response.confidence == report.win_probability
    assert report.winner in response.recommendation
    assert len(response.important_tradeoffs) == len(report.flip_points)
    pg = next(o for o in response.options if o.name == "PostgreSQL")
    assert any(a.startswith("Data integrity: 9/10") for a in pg.advantages)
    assert response.decision_model == model and response.decision_report == report


def test_agent_decision_mode_makes_one_call_for_a_decision_model() -> None:
    provider = MockModelProvider(structured_responses=[_model()])
    agent = ComparisonAgent(provider, decision_engine=True)
    response = asyncio.run(agent.run(
        ComparisonInput(user_request="Postgres or Mongo?"), AgentRuntimeContext(run_id="t")
    ))
    assert len(provider.calls) == 1
    assert provider.calls[0].response_model is DecisionModel
    assert "Do not write" in provider.calls[0].system_prompt
    assert response.decision_report is not None


def test_single_sample_report_defaults() -> None:
    report = analyze(_model())
    assert report.samples == 1 and report.disagreement is None


def test_summary_mentions_merged_samples() -> None:
    model = _model()
    report = analyze(model).model_copy(update={"samples": 2, "disagreement": 0.15})
    limitations = to_comparison_response(model, report).limitations
    assert any("2 independent estimates" in n and "1.5 points" in n for n in limitations)
