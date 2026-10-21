"""Check each finding's quote against the search result it cites.

A citation is **verified** when its quote appears in the cited result's title or
snippet, either verbatim (after normalizing case, punctuation and whitespace) or
near-verbatim (at least 80% of the quote's words present, to tolerate small
paraphrase or truncation). It is **unsupported** when it cites a result that was
never shown, gives no usable quote, or quotes text the result does not contain.

What this does *not* check: whether the quote actually entails the claim. It
proves provenance (the model really read this in result n), which stops
invented sources, a common failure in research agents.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.models.decision import DecisionModel
from app.models.grounding import CheckedFinding, Finding, FindingStatus, GroundingReport
from app.models.search import SearchResult

#: Quotes shorter than this many words are too generic to prove anything.
MIN_QUOTE_WORDS = 3
#: Share of a quote's words that must appear in the result for near-verbatim.
NEAR_VERBATIM_OVERLAP = 0.8

_WORD_RE = re.compile(r"[a-z0-9]+(?:[.'%$][a-z0-9]+)*")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _check(finding: Finding, evidence: Sequence[SearchResult]) -> CheckedFinding:
    def checked(status: FindingStatus, reason: str = "") -> CheckedFinding:
        return CheckedFinding(**finding.model_dump(), status=status, reason=reason)

    if finding.source is None:
        return checked(FindingStatus.MODEL_KNOWLEDGE)
    if finding.source > len(evidence):
        return checked(
            FindingStatus.UNSUPPORTED,
            f"cites Result {finding.source}, but only {len(evidence)} were shown",
        )
    quote = _words(finding.quote)
    if len(quote) < MIN_QUOTE_WORDS:
        return checked(FindingStatus.UNSUPPORTED, "quote too short to verify")

    result = evidence[finding.source - 1]
    text = _words(f"{result.title} {result.snippet}")
    if " ".join(quote) in " ".join(text):
        return checked(FindingStatus.VERIFIED)
    present = set(text)
    if sum(w in present for w in quote) / len(quote) >= NEAR_VERBATIM_OVERLAP:
        return checked(FindingStatus.VERIFIED)
    return checked(FindingStatus.UNSUPPORTED, f"quote not found in Result {finding.source}")


def verify_findings(
    findings: Sequence[Finding], evidence: Sequence[SearchResult]
) -> GroundingReport:
    checked = [_check(f, evidence) for f in findings]
    count = {s: sum(c.status is s for c in checked) for s in FindingStatus}
    cited = count[FindingStatus.VERIFIED] + count[FindingStatus.UNSUPPORTED]
    return GroundingReport(
        findings=checked,
        evidence_count=len(evidence),
        evidence_urls=[r.url for r in evidence],
        verified=count[FindingStatus.VERIFIED],
        unsupported=count[FindingStatus.UNSUPPORTED],
        model_knowledge=count[FindingStatus.MODEL_KNOWLEDGE],
        groundedness=count[FindingStatus.VERIFIED] / len(checked) if checked else 0.0,
        citation_precision=count[FindingStatus.VERIFIED] / cited if cited else None,
    )


def drop_invalid_sources(model: DecisionModel, evidence_count: int) -> tuple[DecisionModel, int]:
    """Clear score citations that point past the results the model was shown.

    Decision-model notes are too short to quote-check, but a citation to a
    result that does not exist is certainly wrong. Returns the cleaned model
    and how many citations were removed.
    """
    removed = 0
    scores = []
    for score in model.scores:
        if score.source is not None and score.source > evidence_count:
            score = score.model_copy(update={"source": None})
            removed += 1
        scores.append(score)
    return model.model_copy(update={"scores": scores}), removed
