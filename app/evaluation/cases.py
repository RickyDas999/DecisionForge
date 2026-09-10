"""Representative routing evaluation cases — three per route."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.routing import AgentRoute


@dataclass(frozen=True)
class EvaluationCase:
    """One routing expectation: a request and the route it should take."""

    name: str
    user_request: str
    expected_route: AgentRoute
    provided_context: str | None = None


ROUTING_CASES: tuple[EvaluationCase, ...] = (
    # -- research --
    EvaluationCase(
        "research-vector-databases",
        "Research the current landscape of vector databases for a small AI startup.",
        AgentRoute.RESEARCH,
    ),
    EvaluationCase(
        "research-observability",
        "What are the main approaches to observability for microservices?",
        AgentRoute.RESEARCH,
    ),
    EvaluationCase(
        "research-edge-computing",
        "Find information about recent trends in edge computing.",
        AgentRoute.RESEARCH,
    ),
    # -- comparison --
    EvaluationCase(
        "comparison-postgres-mongo",
        "Compare PostgreSQL and MongoDB for a small SaaS startup expecting rapid growth.",
        AgentRoute.COMPARISON,
    ),
    EvaluationCase(
        "comparison-aws-gcp",
        "Should we host this on AWS or GCP?",
        AgentRoute.COMPARISON,
    ),
    EvaluationCase(
        "comparison-fastapi-flask",
        "Which is better for our team: FastAPI or Flask?",
        AgentRoute.COMPARISON,
    ),
    # -- brief --
    EvaluationCase(
        "brief-findings-to-brief",
        "Turn these findings into an executive brief for leadership.",
        AgentRoute.BRIEF,
        provided_context=(
            "The team benchmarked three caching strategies over two sprints; "
            "results and cost estimates are attached."
        ),
    ),
    EvaluationCase(
        "brief-decision-memo",
        "Create a concise decision memo from the material below.",
        AgentRoute.BRIEF,
        provided_context="Two vendors submitted proposals with different pricing and SLAs.",
    ),
    EvaluationCase(
        "brief-executive-summary",
        "Summarize the following analysis for executives.",
        AgentRoute.BRIEF,
        provided_context="Our latency SLO was missed in 3 of the last 4 weeks.",
    ),
)
