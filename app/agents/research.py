"""ResearchAgent: leaf specialist for investigate / explain / summarize requests.

One ``ModelProvider`` call per run. No HTTP, no search library, no tools, no
other-agent invocation, no retry, no loop. Search evidence arrives through
``ResearchInput.provided_context`` (as text) and ``ResearchInput.evidence``.

With ``grounded=True`` the model returns findings that each cite a search result
and quote it; :mod:`app.grounding` verifies every quote against that result and
derives the sources, so invented citations never reach the answer.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.grounding import to_research_response, verify_findings
from app.models.grounding import GroundedResearch
from app.models.specialists import ResearchInput, ResearchResponse
from app.providers.model import ModelProvider

RESEARCH_SYSTEM_PROMPT = """\
You are the research specialist for DecisionForge.

Your job is to investigate and explain the topic the user asked about, using \
only the information in the supplied context plus your own model knowledge.

The supplied context may include deterministic search evidence (titled results \
with URLs and snippets). Treat it as external evidence, keep it distinct from \
your own model knowledge, and in `sources` list only URLs that actually appear \
in the supplied context. Never invent URLs.

If external research context is supplied, synthesize it carefully.

If no external research context is supplied:
- do not claim that you performed live or web research
- do not fabricate citations or sources (leave `sources` empty)
- record the lack of external evidence in `limitations`

Return a structured research response.

Do not delegate. Do not call another agent. Do not recommend another workflow.\
"""


GROUNDED_RESEARCH_SYSTEM_PROMPT = """\
You are the research specialist for DecisionForge. Answer the research request \
as findings that code will check against the search evidence.

- summary: 2-3 sentences answering the request.
- findings: 3-6 specific claims. For each, source = the number of the search \
Result it relies on, and quote = 5-20 words copied exactly from that Result's \
title or snippet. For a claim from general knowledge, set source to null and \
quote to "".
- open_questions: at most 3 things the evidence does not settle.

Never cite a Result for a claim it does not support. Never write URLs. Keep the \
JSON compact. Do not delegate or call another agent.\
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
        *,
        grounded: bool = False,
    ) -> None:
        self.model_provider = model_provider
        #: The activated `research` SKILL.md body, or None. Only this skill's
        #: instructions ever reach this agent.
        self.skill_instructions = skill_instructions
        self.grounded = grounded

    def _system_prompt(self) -> str:
        base = GROUNDED_RESEARCH_SYSTEM_PROMPT if self.grounded else RESEARCH_SYSTEM_PROMPT
        if not self.skill_instructions:
            return base
        return (
            f"{base}\n\n"
            f"--- Activated skill: research ---\n{self.skill_instructions.strip()}"
        )

    async def run(
        self,
        task_input: ResearchInput,
        context: AgentRuntimeContext,
    ) -> ResearchResponse:
        if self.grounded:
            research = await self.model_provider.generate_structured(
                system_prompt=self._system_prompt(),
                user_prompt=_build_user_prompt(task_input),
                response_model=GroundedResearch,
            )
            report = verify_findings(research.findings, task_input.evidence)
            return to_research_response(research, report, task_input.evidence)
        return await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=_build_user_prompt(task_input),
            response_model=ResearchResponse,
        )
