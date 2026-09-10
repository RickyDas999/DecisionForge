"""Deterministic structural contract checks for specialist responses.

Pydantic already enforces field presence and the ``confidence`` bounds; these add
the *semantic minimums* the models allow but a good answer should not violate
(empty strings, zero findings, non-URL sources). No LLM judge.

Each function returns a list of problem strings — empty means the response
satisfies its contract.
"""

from __future__ import annotations

import re

from app.models.specialists import (
    BriefResponse,
    ComparisonResponse,
    ResearchResponse,
)

_URL_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def check_research_response(response: ResearchResponse) -> list[str]:
    problems: list[str] = []
    if not response.summary.strip():
        problems.append("summary is empty")
    if not response.key_findings:
        problems.append("no key findings")
    non_urls = [s for s in response.sources if not _URL_RE.match(s.strip())]
    if non_urls:
        problems.append(f"{len(non_urls)} source(s) are not valid URLs")
    return problems


def check_comparison_response(response: ComparisonResponse) -> list[str]:
    problems: list[str] = []
    if not response.options:
        problems.append("no options compared")
    if not response.recommendation.strip():
        problems.append("recommendation is empty")
    if not response.rationale.strip():
        problems.append("rationale is empty")
    if not 0.0 <= response.confidence <= 1.0:
        problems.append("confidence is out of the 0.0-1.0 range")
    return problems


def check_brief_response(response: BriefResponse) -> list[str]:
    problems: list[str] = []
    if not response.title.strip():
        problems.append("title is empty")
    if not response.executive_summary.strip():
        problems.append("executive summary is empty")
    if not response.key_points:
        problems.append("no key points")
    return problems
