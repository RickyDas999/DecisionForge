"""Grounded-research contracts: cited findings and their verification.

The research specialist returns findings that each name the search result they
rely on and quote it. Code then checks every quote against the text of that
result (:mod:`app.grounding`), so "this finding is supported by result 3" is a
verified fact rather than the model's claim.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Finding(BaseModel):
    """One claim, the search result it relies on, and a quote from that result."""

    claim: str = Field(min_length=1)
    #: ``Result n`` from the search evidence; ``None`` = general model knowledge.
    source: int | None = Field(default=None, ge=1)
    #: Words copied verbatim from that result's title or snippet.
    quote: str = ""


class GroundedResearch(BaseModel):
    """What the research specialist extracts (it never writes URLs)."""

    topic: str
    summary: str
    findings: list[Finding] = Field(min_length=1, max_length=8)
    open_questions: list[str] = Field(default_factory=list)


class FindingStatus(str, Enum):
    VERIFIED = "verified"  # the quote appears in the cited result
    UNSUPPORTED = "unsupported"  # cites a result, but the citation does not hold up
    MODEL_KNOWLEDGE = "model_knowledge"  # no citation; general knowledge


class CheckedFinding(Finding):
    status: FindingStatus
    #: Why a citation failed (empty when verified or uncited).
    reason: str = ""


class GroundingReport(BaseModel):
    """Verification of every finding against the evidence the model was shown."""

    findings: list[CheckedFinding]
    evidence_count: int
    verified: int
    unsupported: int
    model_knowledge: int
    #: Share of all findings with a verified citation.
    groundedness: float = Field(ge=0.0, le=1.0)
    #: Share of cited findings whose citation holds up (``None`` if none cited).
    citation_precision: float | None = Field(default=None, ge=0.0, le=1.0)
