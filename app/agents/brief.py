"""BriefAgent: leaf specialist that transforms supplied material into a brief.

One ``ModelProvider`` call per run. It requires user-provided context and works
only from it — no research, no tools, no other-agent invocation, no retry, no
loop.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.models.specialists import BriefInput, BriefResponse
from app.providers.model import ModelProvider

BRIEF_SYSTEM_PROMPT = """\
You are the executive brief specialist for DecisionForge.

Your job is to transform the user-supplied material into a concise, professional, \
structured brief for a leadership audience.

Use only the information supplied in the user's context. Preserve its meaning, \
emphasize the decision-relevant points, and do not introduce facts that are not \
supported by the supplied material.

Do not invent facts. Do not perform research. Do not call another agent. Do not \
delegate.

Produce:
- title
- executive summary
- key points
- an optional recommendation, only when the supplied material supports one
- action items\
"""


def _build_user_prompt(task_input: BriefInput) -> str:
    return (
        "Brief request:\n"
        f"{task_input.user_request}\n\n"
        "Source material (use ONLY this; do not add outside facts):\n"
        f"{task_input.provided_context}"
    )


class BriefAgent(BaseAgent[BriefInput, BriefResponse]):
    """Turns supplied context into a structured executive brief."""

    name = "brief"

    def __init__(
        self,
        model_provider: ModelProvider,
        skill_instructions: str | None = None,
    ) -> None:
        self.model_provider = model_provider
        #: The activated `executive-brief` SKILL.md body, or None.
        self.skill_instructions = skill_instructions

    def _system_prompt(self) -> str:
        if not self.skill_instructions:
            return BRIEF_SYSTEM_PROMPT
        return (
            f"{BRIEF_SYSTEM_PROMPT}\n\n"
            f"--- Activated skill: executive-brief ---\n{self.skill_instructions.strip()}"
        )

    async def run(
        self,
        task_input: BriefInput,
        context: AgentRuntimeContext,
    ) -> BriefResponse:
        return await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=_build_user_prompt(task_input),
            response_model=BriefResponse,
        )
