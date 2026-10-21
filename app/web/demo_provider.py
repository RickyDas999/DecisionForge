"""A deterministic, offline stand-in for Claude, used only by the web demo.

The default web app cannot use ``MockModelProvider`` directly (that needs one
queued response per call, keyed to a route we don't know ahead of time). This
provider returns plausible canned structured output based on the requested
``response_model`` and a light keyword read of the request.

It is **not** an LLM and **not** the real orchestrator. The architecture is
unchanged: OrchestratorAgent still calls ``generate_structured(RoutingDecision)``
(call #1) and the selected specialist calls ``generate_structured(...)`` (call
#2) — exactly two model calls. This class just makes those two calls return
demo data.
"""

from __future__ import annotations

import hashlib
import json
import re

from pydantic import BaseModel

from app.agents.comparison import SECOND_OPINION_NOTE
from app.models.decision import Criterion, DecisionModel, Score

from app.models.routing import AgentRoute, RoutingDecision
from app.models.search import SearchResponse, SearchResult
from app.models.specialists import (
    BriefResponse,
    ComparisonOption,
    ComparisonResponse,
    ResearchResponse,
)
from app.providers.model import ModelProvider
from app.providers.usage import DEFAULT_MODEL, record_estimated
from app.tools.search import MockSearchProvider

_COMPARISON_HINTS = (" vs ", " vs.", "compare ", " versus ", " or ")
_BRIEF_HINTS = ("brief", "memo", "summari", "leadership", "executive")


def _route_for(text: str) -> RoutingDecision:
    lowered = f" {text.lower()} "
    if any(hint in lowered for hint in _COMPARISON_HINTS):
        return RoutingDecision(
            route=AgentRoute.COMPARISON,
            reasoning="Demo router: the request compares alternatives.",
        )
    if any(hint in lowered for hint in _BRIEF_HINTS):
        return RoutingDecision(
            route=AgentRoute.BRIEF,
            reasoning="Demo router: the request asks to transform supplied material.",
        )
    return RoutingDecision(
        route=AgentRoute.RESEARCH,
        reasoning="Demo router: the request asks to investigate a topic.",
    )


_PAIR_RE = re.compile(
    r"(?:compare|between)\s+(.+?)\s+and\s+(.+?)(?=\s+(?:for|in|on|at|when)\b|[?.,:]|$)",
    re.IGNORECASE,
)
_SPLIT_RE = re.compile(r"\s+(?:vs\.?|versus|or)\s+", re.IGNORECASE)
_STOP_RE = re.compile(r"\s+(?:for|in|on|at|when|to|with)\b|[?.,:;]")
_DEMO_CRITERIA = (
    ("Fit for the stated context", 0.35),
    ("Operational simplicity", 0.25),
    ("Low total cost", 0.2),
    ("Ecosystem and support", 0.2),
)


def _trailing_name(chunk: str) -> str:
    """The option name at the end of e.g. 'Should we host this on AWS'."""
    words = chunk.strip().split()
    name: list[str] = []
    for word in reversed(words):
        if word[:1].isupper() or word[:1].isdigit():
            name.insert(0, word)
        else:
            break
    return " ".join(name) if name else (words[-1] if words else "")


def _leading_name(chunk: str) -> str:
    """The option name at the start of e.g. 'Svelte for a three-person team'."""
    head = _STOP_RE.split(chunk.strip(), maxsplit=1)[0]
    return " ".join(head.split()[:3])


def _demo_options(request: str) -> list[str]:
    """A light, deterministic read of the option names in a comparison request."""
    match = _PAIR_RE.search(request)
    if match:
        candidates = [match.group(1), match.group(2)]
    else:
        parts = _SPLIT_RE.split(request)
        if len(parts) < 2:
            return ["Option A", "Option B"]
        candidates = [_trailing_name(parts[0]), *[p for p in parts[1:-1]], _leading_name(parts[-1])]
    options: list[str] = []
    for raw in candidates:
        name = raw.strip(" ?.,:;\"'")
        if name and name.lower() not in {o.lower() for o in options}:
            options.append(name)
    return options[:4] if len(options) >= 2 else ["Option A", "Option B"]


def _demo_decision(user_prompt: str) -> DecisionModel:
    """Illustrative decision model: real option names, hash-derived scores."""
    request = user_prompt.split("\n\n", 1)[0].removeprefix("Comparison request:").strip()
    options = _demo_options(request)
    has_evidence = "Result 1" in user_prompt
    # A second-opinion request gets its own (different) illustrative scores.
    salt = "second|" if user_prompt.endswith(SECOND_OPINION_NOTE) else ""
    scores = []
    for option in options:
        for index, (criterion, _) in enumerate(_DEMO_CRITERIA):
            digest = hashlib.sha256(f"{salt}{option}|{criterion}".lower().encode()).digest()
            mid = 3.0 + digest[0] / 255 * 6.0  # 3..9
            half = 0.5 + digest[1] / 255 * 1.5  # 0.5..2
            scores.append(Score(
                option=option,
                criterion=criterion,
                low=round(max(0.0, mid - half), 1),
                high=round(min(10.0, mid + half), 1),
                note="demo estimate",
                source=1 if has_evidence and index == 0 else None,
            ))
    return DecisionModel(
        question=request,
        options=options,
        criteria=[Criterion(name=n, weight=w) for n, w in _DEMO_CRITERIA],
        scores=scores,
        assumptions=["Offline demo: scores are illustrative, not real estimates."],
    )


class DemoModelProvider(ModelProvider):
    """Offline canned-response provider for the local web demo."""

    async def generate_text(self, *, system_prompt: str, user_prompt: str) -> str:
        raise NotImplementedError("DemoModelProvider only supports structured output")

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
    ) -> BaseModel:
        result = self._canned(user_prompt, response_model)
        # Record what this call would cost on the default live model. The schema
        # is counted because the live provider sends it with every request.
        schema = json.dumps(response_model.model_json_schema(), separators=(",", ":"))
        record_estimated(
            operation="generate_structured",
            model=DEFAULT_MODEL,
            prompts=(system_prompt, schema, user_prompt),
            output=result.model_dump_json(),
        )
        return result

    def _canned(self, user_prompt: str, response_model: type[BaseModel]) -> BaseModel:
        if response_model is RoutingDecision:
            return _route_for(user_prompt)

        if response_model is DecisionModel:
            return _demo_decision(user_prompt)

        if response_model is ResearchResponse:
            return ResearchResponse(
                topic="Demo research topic",
                summary=(
                    "This is a deterministic demo response. No live or web research "
                    "was performed; it is generated offline by DemoModelProvider."
                ),
                key_findings=[
                    "Demo finding 1 — replace by configuring a real model provider.",
                    "Demo finding 2 — the request text was received and routed.",
                ],
                limitations=[
                    "Offline demo output; not based on real evidence.",
                    "Configure MODEL_PROVIDER=anthropic for real answers.",
                ],
                sources=[],
            )

        if response_model is ComparisonResponse:
            return ComparisonResponse(
                question="Demo comparison",
                options=[
                    ComparisonOption(
                        name="Option A",
                        advantages=["Demo advantage"],
                        disadvantages=["Demo disadvantage"],
                    ),
                    ComparisonOption(
                        name="Option B",
                        advantages=["Demo advantage"],
                        disadvantages=["Demo disadvantage"],
                    ),
                ],
                recommendation="Demo recommendation (offline).",
                rationale="Deterministic demo rationale — not real analysis.",
                important_tradeoffs=["Demo tradeoff"],
                confidence=0.5,
                limitations=["Offline demo output; configure a real provider."],
            )

        if response_model is BriefResponse:
            return BriefResponse(
                title="Demo Executive Brief",
                executive_summary=(
                    "Deterministic demo brief generated offline from the supplied "
                    "context."
                ),
                key_points=["Demo key point 1", "Demo key point 2"],
                recommendation=None,
                action_items=["Demo action item"],
            )

        raise NotImplementedError(  # pragma: no cover
            f"DemoModelProvider has no canned response for {response_model.__name__}"
        )


class DemoSearchProvider(MockSearchProvider):
    """Offline canned search results, so the demo shows the search step running.

    No network. Used by the demo web app for RESEARCH / COMPARISON requests.
    """

    async def search(self, query: str, *, max_results: int = 5) -> SearchResponse:
        self.responses = [
            SearchResponse(
                query=query,
                results=[
                    SearchResult(
                        title="Illustrative source A (offline demo)",
                        url="https://example.com/a",
                        snippet=(
                            "A short deterministic snippet. Set "
                            "SEARCH_PROVIDER=duckduckgo + install the '[search]' "
                            "extra for real web results."
                        ),
                        source="example.com",
                    ),
                    SearchResult(
                        title="Illustrative source B (offline demo)",
                        url="https://example.com/b",
                        snippet="A second deterministic snippet for the demo.",
                        source="example.com",
                    ),
                ],
            )
        ]
        return await super().search(query, max_results=max_results)
