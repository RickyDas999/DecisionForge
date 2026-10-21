"""Turn a decision model and its analysis into a :class:`ComparisonResponse`.

Every sentence here is generated from numbers the engine computed, so the prose
can never disagree with the analysis: the recommendation is the simulation
winner, the confidence is its win probability, and each tradeoff is a flip point.
Existing consumers (UI, persistence, eval contracts) keep working unchanged.
"""

from __future__ import annotations

from app.decision.engine import _key
from app.models.decision import DecisionModel, DecisionReport
from app.models.specialists import ComparisonOption, ComparisonResponse

#: Midpoint at or above which a score is listed as an advantage (0-10 scale).
STRONG_AT = 7.0
#: Midpoint at or below which a score is listed as a disadvantage.
WEAK_AT = 4.0

_VERDICT_TEXT = {
    "robust": "a robust winner",
    "leaning": "a likely but not certain winner",
    "toss-up": "too close to call",
}


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _options(model: DecisionModel) -> list[ComparisonOption]:
    by_option: dict[str, ComparisonOption] = {
        _key(o): ComparisonOption(name=o) for o in model.options
    }
    for score in model.scores:
        option = by_option.get(_key(score.option))
        if option is None:
            continue
        mid = (score.low + score.high) / 2
        text = f"{score.criterion}: {mid:.0f}/10" + (f" ({score.note})" if score.note else "")
        if mid >= STRONG_AT:
            option.advantages.append(text)
        elif mid <= WEAK_AT:
            option.disadvantages.append(text)
    return list(by_option.values())


def _rationale(model: DecisionModel, report: DecisionReport) -> str:
    top = report.ranking[0]
    parts = [
        f"{top.option} has the highest weighted score ({top.expected_score:.1f}/10) and "
        f"ranked first in {_pct(top.win_probability)} of {report.simulations:,} simulations "
        f"that vary the weights and scores within their stated ranges."
    ]
    if len(report.ranking) > 1:
        runner = report.ranking[1]
        mids = {
            (_key(s.option), _key(s.criterion)): (s.low + s.high) / 2 for s in model.scores
        }
        contributions = []
        for crit in model.criteria:
            weight = report.weights.get(crit.name, 0.0)
            a = mids.get((_key(top.option), _key(crit.name)))
            b = mids.get((_key(runner.option), _key(crit.name)))
            if a is not None and b is not None and a > b:
                contributions.append((weight * (a - b), crit.name))
        drivers = [name for _, name in sorted(contributions, reverse=True)[:2]]
        if drivers:
            parts.append(f"Its lead over {runner.option} comes mostly from {' and '.join(drivers)}.")
    return " ".join(parts)


def _tradeoffs(report: DecisionReport) -> list[str]:
    return [
        f"If {p.criterion} carried {_pct(p.flip_weight)} of the weight "
        f"(now {_pct(p.current_weight)}), {p.new_winner} would win."
        for p in report.flip_points
    ]


def _limitations(model: DecisionModel, report: DecisionReport) -> list[str]:
    notes = [f"Assumption: {a}" for a in model.assumptions]
    notes.append("Scores are model estimates on a 0-10 scale; ranges show its uncertainty.")
    if report.total_scores and report.cited_scores == 0:
        notes.append("No score cites search evidence; all come from general knowledge.")
    if report.samples > 1 and report.disagreement is not None:
        notes.append(
            f"{report.samples} independent estimates were combined; they differed by "
            f"{report.disagreement * 10:.1f} points on average, which widened the ranges."
        )
    if report.invalid_citations:
        notes.append(
            f"{report.invalid_citations} score citation(s) named a search result that was "
            "never shown and were removed."
        )
    if report.gaps:
        notes.append(f"Not scored (treated as fully uncertain): {', '.join(report.gaps)}.")
    return notes


def to_comparison_response(model: DecisionModel, report: DecisionReport) -> ComparisonResponse:
    if report.verdict == "toss-up" and len(report.ranking) > 1:
        a, b = report.ranking[0], report.ranking[1]
        recommendation = (
            f"No clear winner: {a.option} ({_pct(a.win_probability)}) vs "
            f"{b.option} ({_pct(b.win_probability)}). Decide on the flip points below."
        )
    else:
        recommendation = (
            f"{report.winner}: {_VERDICT_TEXT[report.verdict]} "
            f"(wins {_pct(report.win_probability)} of simulations)."
        )
    return ComparisonResponse(
        question=model.question,
        options=_options(model),
        recommendation=recommendation,
        rationale=_rationale(model, report),
        important_tradeoffs=_tradeoffs(report),
        confidence=report.win_probability,
        limitations=_limitations(model, report),
        decision_model=model,
        decision_report=report,
    )
