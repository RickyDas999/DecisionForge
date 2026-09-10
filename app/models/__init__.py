"""Core Pydantic domain models for DecisionForge.

Current architecture (post-reframe):

- ``routing`` — models for the single-hop OrchestratorAgent
- ``specialists`` — input/output models for the three leaf specialist agents

- ``persistence`` — current ``RunStatus`` / ``EventType`` plus ``RunRecord`` /
  ``ExecutionEvent`` for local SQLite run history

The ``analysis`` / ``brief`` / ``judging`` / ``planning`` / ``research`` /
``state`` / ``events`` modules are **legacy** — they describe the earlier
multi-stage pipeline that is no longer the target. They are kept only so existing
tests keep passing; do not build new code on them. See
``docs/architecture.md`` -> "Architecture Reframe". Two names are intentionally
re-pointed here to their current-architecture versions:
``BriefInput`` (from ``app.models.specialists``, not ``app.models.brief``) and
``RunStatus`` / ``EventType`` (from ``app.models.persistence``, not
``app.models.state`` / ``app.models.events``). The legacy classes stay importable
from their own modules.
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
from app.models.brief import FinalBrief
from app.models.dispatch import DispatchRequest, DispatchResult, SpecialistResponse
from app.models.events import WorkflowEvent
from app.models.judging import JudgeInput, JudgeResult
from app.models.persistence import EventType, ExecutionEvent, RunRecord, RunStatus
from app.models.planning import PlannerInput, ResearchPlan, ResearchTrack
from app.models.research import (
    ResearchFinding,
    ResearchResult,
    ResearchTask,
    Source,
)
from app.models.routing import AgentRoute, RoutingDecision, RoutingInput
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefInput,
    BriefResponse,
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
    ResearchInput,
    ResearchResponse,
)
from app.models.state import RunState

__all__ = [
    # --- Current architecture: routing ---
    "AgentRoute",
    "RoutingDecision",
    "RoutingInput",
    # --- Current architecture: specialists ---
    "BriefInput",
    "BriefResponse",
    "ComparisonInput",
    "ComparisonOption",
    "ComparisonResponse",
    "ResearchInput",
    "ResearchResponse",
    # --- Current architecture: dispatch ---
    "DispatchRequest",
    "DispatchResult",
    "SpecialistResponse",
    # --- Current architecture: search tool ---
    "SearchResponse",
    "SearchResult",
    # --- Current architecture: persistence / tracing ---
    "EventType",
    "ExecutionEvent",
    "RunRecord",
    "RunStatus",
    # --- Legacy shared ---
    "RunState",
    "WorkflowEvent",
    # --- Legacy (pre-reframe multi-stage pipeline; see docs/architecture.md) ---
    "AlternativesAnalysis",
    "AnalysisInput",
    "AnalysisMode",
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
