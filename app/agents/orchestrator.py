"""OrchestratorAgent: the only agent allowed to select another agent.

It performs one structured model call to classify a user request into exactly
one of ``AgentRoute.{RESEARCH, COMPARISON, BRIEF}`` and returns a
``RoutingDecision``. It does not answer the request, call tools, touch
``RunState``, loop, retry, or invoke a specialist. Deterministic Python (a later
phase) dispatches on the returned route.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.models.routing import RoutingDecision, RoutingInput
from app.providers.model import ModelProvider

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are the routing orchestrator for DecisionForge.

Your only job is to classify the user's request and select exactly one \
specialist agent.

Available routes:

research:
Use when the user wants information gathered, investigated, or explained through \
research.

comparison:
Use when the user wants options compared, tradeoffs evaluated, or a \
recommendation between alternatives.

brief:
Use when the user provides existing context and wants it transformed into an \
executive brief, memo, or polished summary.

Priority when a request could fit more than one route:
- If it explicitly asks to compare alternatives or choose between options, pick \
comparison.
- Otherwise, if it primarily asks to gather or investigate information, pick \
research.
- Otherwise, if it supplies source material and asks to transform it, pick brief.

Rules:
- Select exactly one route.
- Do not answer the user's request.
- Do not perform the specialist's work.
- Do not recommend additional agents.
- Do not create multi-agent workflows.
- Return only the structured routing decision, with a short reasoning string \
that explains the classification (not hidden chain-of-thought).\
"""


def build_user_prompt(user_request: str) -> str:
    """Wrap the raw user request in a minimal routing instruction."""
    return (
        "Classify the following user request and select exactly one route.\n\n"
        "User request:\n"
        f"{user_request}"
    )


class OrchestratorAgent(BaseAgent[RoutingInput, RoutingDecision]):
    """Classifies a user request into exactly one specialist route."""

    name = "orchestrator"

    def __init__(self, model_provider: ModelProvider) -> None:
        self.model_provider = model_provider

    async def run(
        self,
        task_input: RoutingInput,
        context: AgentRuntimeContext,
    ) -> RoutingDecision:
        return await self.model_provider.generate_structured(
            system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
            user_prompt=build_user_prompt(task_input.user_request),
            response_model=RoutingDecision,
        )
