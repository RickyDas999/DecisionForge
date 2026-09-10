"""Construction and validation tests for the core domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.analysis import (
    AlternativesAnalysis,
    DecisionAnalysis,
    OptionAssessment,
    RiskAnalysis,
)
from app.models.brief import FinalBrief
from app.models.judging import JudgeResult
from app.models.planning import ResearchPlan, ResearchTrack
from app.models.research import ResearchFinding, ResearchResult, Source
from app.models.state import RunState, RunStatus
from app.orchestration.config import WorkflowConfig


# --------------------------------------------------------------------------- #
# A. Valid model construction
# --------------------------------------------------------------------------- #
def test_valid_research_plan() -> None:
    plan = ResearchPlan(
        normalized_question="Should we use PostgreSQL or MongoDB?",
        decision_type="technology-selection",
        options=["PostgreSQL", "MongoDB"],
        research_tracks=[
            ResearchTrack(
                name="technical",
                objective="Compare consistency and scaling models",
                suggested_queries=["postgres vs mongodb consistency"],
            )
        ],
    )
    assert plan.options == ["PostgreSQL", "MongoDB"]
    assert plan.research_tracks[0].name == "technical"


def test_valid_research_result() -> None:
    result = ResearchResult(
        track_name="technical",
        summary="Postgres offers strong consistency; Mongo favors flexibility.",
        findings=[
            ResearchFinding(
                claim="Postgres supports ACID transactions",
                evidence="Official docs describe full ACID compliance.",
                source_urls=["https://www.postgresql.org/docs/"],
                confidence=0.9,
            )
        ],
        sources=[
            Source(
                title="PostgreSQL Documentation",
                url="https://www.postgresql.org/docs/",
                publisher="PostgreSQL Global Development Group",
            )
        ],
    )
    assert result.findings[0].confidence == 0.9


def test_valid_judge_result() -> None:
    verdict = JudgeResult(
        approved=True,
        score=0.82,
        strengths=["Multiple primary sources"],
        weaknesses=["Limited cost analysis"],
        missing_information=["Operational tooling comparison"],
        follow_up_queries=["managed postgres vs managed mongodb pricing"],
    )
    assert verdict.approved is True
    assert verdict.score == 0.82


def test_valid_decision_analysis() -> None:
    analysis = DecisionAnalysis(
        option_assessments=[
            OptionAssessment(
                option="PostgreSQL",
                strengths=["Relational integrity"],
                weaknesses=["Rigid schema migrations"],
                best_for=["Transactional workloads"],
                concerns=["Horizontal scaling effort"],
            )
        ],
        recommendation="Use PostgreSQL",
        rationale="The workload is transactional and relational.",
        confidence=0.75,
    )
    assert analysis.recommendation == "Use PostgreSQL"


def test_valid_final_brief() -> None:
    brief = FinalBrief(
        title="PostgreSQL vs MongoDB",
        executive_summary="PostgreSQL is the better fit for this workload.",
        recommendation="Adopt PostgreSQL",
        rationale="Strong consistency requirements dominate.",
        risks=["Scaling writes may require partitioning"],
        alternatives=["MongoDB for document-heavy features"],
        sources=[Source(title="PostgreSQL Docs", url="https://www.postgresql.org/docs/")],
        confidence=0.8,
    )
    assert brief.confidence == 0.8


def test_valid_run_state() -> None:
    state = RunState(run_id="run-1", original_query="Should we use PostgreSQL or MongoDB?")
    assert state.status is RunStatus.CREATED
    assert state.research_iteration == 0
    assert state.research_results == []
    assert state.errors == []
    assert state.created_at.tzinfo is not None
    assert state.updated_at.tzinfo is not None


def test_run_state_mutable_defaults_are_independent() -> None:
    a = RunState(run_id="a", original_query="q")
    b = RunState(run_id="b", original_query="q")
    a.research_results.append(
        ResearchResult(track_name="t", summary="s")
    )
    assert b.research_results == []


# --------------------------------------------------------------------------- #
# B. Validation failures
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad_confidence", [-0.1, 1.1])
def test_research_finding_confidence_out_of_range(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        ResearchFinding(
            claim="c",
            evidence="e",
            source_urls=[],
            confidence=bad_confidence,
        )


@pytest.mark.parametrize("bad_score", [-0.01, 1.5])
def test_judge_result_score_out_of_range(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        JudgeResult(approved=False, score=bad_score)


@pytest.mark.parametrize("bad_confidence", [-1.0, 2.0])
def test_decision_analysis_confidence_out_of_range(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        DecisionAnalysis(
            recommendation="r",
            rationale="why",
            confidence=bad_confidence,
        )


@pytest.mark.parametrize("bad_confidence", [-0.5, 1.01])
def test_final_brief_confidence_out_of_range(bad_confidence: float) -> None:
    with pytest.raises(ValidationError):
        FinalBrief(
            title="t",
            executive_summary="s",
            recommendation="r",
            rationale="why",
            confidence=bad_confidence,
        )


# --------------------------------------------------------------------------- #
# D. WorkflowConfig defaults
# --------------------------------------------------------------------------- #
def test_workflow_config_defaults() -> None:
    config = WorkflowConfig()
    assert config.max_research_iterations == 3
    assert config.max_validation_attempts == 2
    assert config.agent_timeout_seconds == 60
    assert config.max_parallel_researchers == 3


@pytest.mark.parametrize(
    "field",
    [
        "max_research_iterations",
        "max_validation_attempts",
        "agent_timeout_seconds",
        "max_parallel_researchers",
    ],
)
def test_workflow_config_rejects_below_lower_bound(field: str) -> None:
    with pytest.raises(ValidationError):
        WorkflowConfig(**{field: 0})


# --------------------------------------------------------------------------- #
# Secondary analysis models construct cleanly
# --------------------------------------------------------------------------- #
def test_secondary_analysis_models() -> None:
    risk = RiskAnalysis(
        risks=["Vendor lock-in"],
        failure_modes=["Unbounded write amplification"],
        mitigations=["Adopt connection pooling"],
    )
    alternatives = AlternativesAnalysis(
        alternatives=["SQLite for the prototype"],
        counterarguments=["Team lacks relational expertise"],
        when_recommendation_may_be_wrong=["If schema is highly dynamic"],
    )
    assert risk.risks == ["Vendor lock-in"]
    assert alternatives.alternatives == ["SQLite for the prototype"]
