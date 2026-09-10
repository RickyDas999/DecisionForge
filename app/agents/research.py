"""ResearchAgent: leaf specialist for investigate / explain / summarize requests.

One ``ModelProvider`` call per run. No HTTP, no search library, no tools, no
other-agent invocation, no retry, no loop. Real search/fetch tools arrive in a
later phase and will feed evidence in through ``ResearchInput.provided_context``.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.models.specialists import ResearchInput, ResearchResponse
from app.providers.model import ModelProvider

RESEARCH_SYSTEM_PROMPT = """\
You are the research specialist for DecisionForge.

Your job is to investigate and explain the topic the user asked about, using \
only the information in the supplied context plus your own model knowledge.

If external research context is supplied, synthesize it carefully and you may \
cite it in `sources`.

If no external research context is supplied:
- do not claim that you performed live or web research
- do not fabricate citations or sources (leave `sources` empty)
- record the lack of external evidence in `limitations`

Return a structured research response.

Do not delegate. Do not call another agent. Do not recommend another workflow.\
"""


def _build_user_prompt(task_input: ResearchInput) -> str:
    parts = [f"Research request:\n{task_input.user_request}"]
    if task_input.provided_context is not None and task_input.provided_context.strip():
        parts.append(f"External research context:\n{task_input.provided_context}")
    else:
        parts.append(
            "External research context: none supplied. "
            "State this limitation and do not invent sources."
        )
    return "\n\n".join(parts)


class ResearchAgent(BaseAgent[ResearchInput, ResearchResponse]):
    """Produces a focused, structured research summary."""

    name = "research"

    def __init__(
        self,
        model_provider: ModelProvider,
        skill_instructions: str | None = None,
    ) -> None:
        self.model_provider = model_provider
        #: The activated `research` SKILL.md body, or None. Only this skill's
        #: instructions ever reach this agent.
        self.skill_instructions = skill_instructions

    def _system_prompt(self) -> str:
        if not self.skill_instructions:
            return RESEARCH_SYSTEM_PROMPT
        return (
            f"{RESEARCH_SYSTEM_PROMPT}\n\n"
            f"--- Activated skill: research ---\n{self.skill_instructions.strip()}"
        )

    async def run(
        self,
        task_input: ResearchInput,
        context: AgentRuntimeContext,
    ) -> ResearchResponse:
        return await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=_build_user_prompt(task_input),
            response_model=ResearchResponse,
        )
