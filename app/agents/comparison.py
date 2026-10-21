"""ComparisonAgent: leaf specialist for compare / tradeoff / recommendation requests.

One ``ModelProvider`` call per run. No research, no tools, no other-agent
invocation, no retry, no loop.

With ``decision_engine=True`` the model is not asked for a verdict at all. It
extracts a :class:`DecisionModel` (options, weighted criteria, score ranges), and
the deterministic engine in :mod:`app.decision` computes the recommendation, its
win probability, and the flip points. Still exactly one model call.

With ``adaptive_samples=True`` as well, a close call (verdict not ``robust``)
earns exactly one more, independently framed extraction. The two samples are
merged so their disagreement widens the ranges, and the merged model is
re-analysed. Clear-cut decisions never pay for the second call, and a failed
second call (budget, parse error) falls back to the first answer.
"""

from __future__ import annotations

from app.agents.base import AgentRuntimeContext, BaseAgent
from app.decision import analyze, to_comparison_response
from app.decision.ensemble import disagreement, merge_models
from app.grounding import drop_invalid_sources
from app.models.decision import DecisionModel
from app.models.specialists import ComparisonInput, ComparisonResponse
from app.providers.exceptions import ModelProviderError
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


DECISION_SYSTEM_PROMPT = """\
You are the decision-modeling specialist for DecisionForge. Do not write a \
verdict: code will score your model, simulate its uncertainty, and pick the winner.

Extract:
- options: the 2-4 real alternatives, as short exact names.
- criteria: what matters for THIS decision (team, scale, budget in the request), \
each phrased so higher is better (e.g. "Low operating cost"), with weight = \
relative importance from 0 to 1. Keep options x criteria at 12 or fewer.
- scores: one entry for EVERY option and criterion pair, with low and high on a \
0-10 scale (wider = less certain), a note of at most 8 words, and source = the \
number of the search Result that supports it, or null for general knowledge.
- assumptions: at most 3 short assumptions about the user's situation.

Never cite a Result that does not support the score. Keep the JSON compact. Do \
not call another agent or delegate.\
"""


#: Verdicts uncertain enough to justify a second, independent extraction.
SECOND_SAMPLE_VERDICTS = frozenset({"toss-up", "leaning"})

#: Appended to the user prompt for the second sample. The different framing
#: (and prompt) yields an independent estimate rather than a cached repeat.
SECOND_OPINION_NOTE = (
    "\n\nThis is a second, independent estimate. Score the decision from scratch "
    "as a skeptical reviewer would, and widen ranges where the evidence is thin."
)


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
        *,
        decision_engine: bool = False,
        adaptive_samples: bool = False,
    ) -> None:
        self.model_provider = model_provider
        #: The activated `comparison` SKILL.md body, or None.
        self.skill_instructions = skill_instructions
        self.decision_engine = decision_engine
        self.adaptive_samples = adaptive_samples

    def _system_prompt(self) -> str:
        base = DECISION_SYSTEM_PROMPT if self.decision_engine else COMPARISON_SYSTEM_PROMPT
        if not self.skill_instructions:
            return base
        return (
            f"{base}\n\n"
            f"--- Activated skill: comparison ---\n{self.skill_instructions.strip()}"
        )

    async def run(
        self,
        task_input: ComparisonInput,
        context: AgentRuntimeContext,
    ) -> ComparisonResponse:
        if self.decision_engine:
            return await self._decide(_build_user_prompt(task_input), len(task_input.evidence))
        return await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=_build_user_prompt(task_input),
            response_model=ComparisonResponse,
        )

    async def _extract(self, user_prompt: str, evidence_count: int) -> tuple[DecisionModel, int]:
        """One extraction, with citations to never-shown results removed."""
        model = await self.model_provider.generate_structured(
            system_prompt=self._system_prompt(),
            user_prompt=user_prompt,
            response_model=DecisionModel,
        )
        return drop_invalid_sources(model, evidence_count)

    async def _decide(self, user_prompt: str, evidence_count: int) -> ComparisonResponse:
        model, invalid = await self._extract(user_prompt, evidence_count)
        report = analyze(model)
        if self.adaptive_samples and report.verdict in SECOND_SAMPLE_VERDICTS:
            try:
                second, invalid_second = await self._extract(
                    user_prompt + SECOND_OPINION_NOTE, evidence_count
                )
            except ModelProviderError:
                # The first answer stands on its own; never fail the run here.
                pass
            else:
                merged = merge_models(model, second)
                report = analyze(merged).model_copy(
                    update={"samples": 2, "disagreement": disagreement(model, second)}
                )
                model = merged
                invalid += invalid_second
        report = report.model_copy(update={"invalid_citations": invalid})
        return to_comparison_response(model, report)
