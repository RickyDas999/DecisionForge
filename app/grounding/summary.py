"""Turn verified grounded research into the existing :class:`ResearchResponse`.

Only verified findings keep their citation; uncited ones are labelled general
knowledge; unsupported citations move to limitations rather than appearing as
findings. ``sources`` lists the URLs of verified citations: code derives them
from the evidence, so the model never writes a URL and cannot invent one.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.models.grounding import FindingStatus, GroundedResearch, GroundingReport
from app.models.search import SearchResult
from app.models.specialists import ResearchResponse


def to_research_response(
    research: GroundedResearch,
    report: GroundingReport,
    evidence: Sequence[SearchResult],
) -> ResearchResponse:
    findings: list[str] = []
    limitations = list(research.open_questions)
    cited: list[int] = []
    for f in report.findings:
        if f.status is FindingStatus.VERIFIED:
            findings.append(f"{f.claim} [{f.source}]")
            if f.source not in cited:
                cited.append(f.source)
        elif f.status is FindingStatus.MODEL_KNOWLEDGE:
            findings.append(f"{f.claim} (general knowledge)")
        else:
            limitations.append(f"Not verified, so left out of the findings: {f.claim} ({f.reason}).")
    if not evidence:
        limitations.append("No search evidence was supplied; findings are general model knowledge.")
    return ResearchResponse(
        topic=research.topic,
        summary=research.summary,
        key_findings=findings,
        limitations=limitations,
        sources=[evidence[n - 1].url for n in sorted(cited)],
        grounding=report,
    )
