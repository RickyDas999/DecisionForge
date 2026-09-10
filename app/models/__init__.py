"""Core Pydantic domain models for DecisionForge.

Current architecture (post-reframe):

- ``routing`` — models for the single-hop OrchestratorAgent
- ``specialists`` — input/output models for the three leaf specialist agents

The ``analysis`` / ``brief`` / ``judging`` / ``planning`` / ``research`` /
``state`` modules are **legacy** — they describe the earlier multi-stage pipeline
that is no longer the target. They are kept only so existing tests keep passing;
do not build new code on them. See ``docs/architecture.md`` -> "Architecture
Reframe". (The legacy ``BriefInput`` in ``app.models.brief`` is intentionally not
re-exported here; the current-architecture ``BriefInput`` below is from
``app.models.specialists``.)
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
from app.models.specialists import (
    BriefInput,
    BriefResponse,
    ComparisonInput,
    ComparisonOption,
    ComparisonResponse,
    ResearchInput,
    ResearchResponse,
)
from app.models.state import RunState, RunStatus

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
    # --- Shared ---
    "EventType",
    "RunState",
    "RunStatus",
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
