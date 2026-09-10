"""ComparisonAgent: leaf specialist for compare / tradeoff / recommendation requests.

One ``ModelProvider`` call per run. No research, no tools, no other-agent
invocation, no retry, no loop.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.models.specialists import ComparisonInput, ComparisonResponse
from app.providers.model import ModelProvider

COMPARISON_SYSTEM_PROMPT = """\
You are the comparison specialist for DecisionForge.

Your job is to compare the alternatives in the user's request and produce a \
structured decision analysis.

Identify and populate:
- the options being compared, each with advantages and disadvantages
- the important tradeoffs between them
- a recommendation where one is justified (otherwise say a clear recommendation \
is not possible)
- the rationale for that recommendation
- a confidence score between 0.0 and 1.0
- limitations of the analysis

Use the supplied context when it is available. It may include deterministic \
search evidence (results with URLs and snippets) — use it and keep it distinct \
from your own model knowledge, and do not invent sources or URLs. Do not claim \
to have done current or external research unless external evidence was provided \
in the context; if current evidence would be needed and none was supplied, say \
so in `limitations`.

Do not call another agent. Do not delegate. Do not create a multi-stage \
workflow.\
"""


def _build_user_prompt(task_input: ComparisonInput) -> str:
    parts = [f"Comparison request:\n{task_input.user_request}"]
    if task_input.provided_context is not None and task_input.provided_context.strip():
        parts.append(f"Supplied context:\n{task_input.provided_context}")
    else:
        parts.append(
            "Supplied context: none. If current external evidence would be "
            "required, note that in `limitations`."
        )
    return "\n\n".join(parts)


class ComparisonAgent(BaseAgent[ComparisonInput, ComparisonResponse]):
    """Produces a structured comparison of the alternatives in a request."""

    name = "comparison"

    def __init__(
        self,
        model_provider: ModelProvider,
        skill_instructions: str | None = None,
    ) -> None:
        self.model_provider = model_provider
        #: The activated `comparison` SKILL.md body, or None.
        self.skill_instructions = skill_instructions

    def _system_prompt(self) -> str:
        if not self.skill_instructions:
            return COMPARISON_SYSTEM_PROMPT
        return (
            f"{COMPARISON_SYSTEM_PROMPT}\n\n"
            f"--- Activated skill: comparison ---\n{self.skill_instructions.strip()}"
        )

    async def run(
        self,
        task_input: ComparisonInput,
        context: AgentRuntimeContext,
    ) -> ComparisonResponse:
        return await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=_build_user_prompt(task_input),
            response_model=ComparisonResponse,
        )
