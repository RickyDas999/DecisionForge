"""Core Pydantic domain models for DecisionForge.

Current architecture (post-reframe): ``routing`` holds the models used by the
single-hop OrchestratorAgent. The ``analysis`` / ``brief`` / ``judging`` /
``planning`` / ``research`` / ``state`` modules are **legacy** — they describe the
earlier multi-stage pipeline that is no longer the target. They are kept only so
existing tests keep passing; do not build new code on them. See
``docs/architecture.md`` -> "Architecture Reframe".
"""

from app.models.analysis import (
    AlternativesAnalysis,
    AnalysisInput,
    AnalysisMode,
    DecisionAnalysis,
    OptionAssessment,
    RiskAnalysis,
    SecondaryAnalysisInput,
)
from app.models.brief import BriefInput, FinalBrief
from app.models.events import EventType, WorkflowEvent
from app.models.judging import JudgeInput, JudgeResult
from app.models.planning import PlannerInput, ResearchPlan, ResearchTrack
from app.models.research import (
    ResearchFinding,
    ResearchResult,
    ResearchTask,
    Source,
)
from app.models.routing import AgentRoute, RoutingDecision, RoutingInput
from app.models.state import RunState, RunStatus

__all__ = [
    # Current architecture
    "AgentRoute",
    "RoutingDecision",
    "RoutingInput",
    # Shared
    "EventType",
    "RunState",
    "RunStatus",
    "WorkflowEvent",
    # Legacy (pre-reframe multi-stage pipeline; see docs/architecture.md)
    "AlternativesAnalysis",
    "AnalysisInput",
    "AnalysisMode",
    "BriefInput",
    "DecisionAnalysis",
    "FinalBrief",
    "JudgeInput",
    "JudgeResult",
    "OptionAssessment",
    "PlannerInput",
    "ResearchFinding",
    "ResearchPlan",
    "ResearchResult",
    "ResearchTask",
    "ResearchTrack",
    "RiskAnalysis",
    "SecondaryAnalysisInput",
    "Source",
]
