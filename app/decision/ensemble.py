"""Combine two independently extracted decision models into one.

When the model is sampled twice and the samples disagree, that disagreement is
real uncertainty, so it should widen the score ranges rather than be averaged
away:

* **Scores** present in both samples take the *envelope* ``[min(low), max(high)]``.
* **Weights** are averaged, counting a criterion one sample left out as weight 0.
* **Options** come from the first sample (the anchor); the second sample can
  only add evidence about them, not new options.

The merged model then goes through the normal engine, so a disagreement shows
up as lower win probabilities and more flip points.
"""

from __future__ import annotations

from app.decision.engine import _key
from app.models.decision import Criterion, DecisionModel, Score

#: Most assumptions kept after merging both samples' lists.
_MAX_ASSUMPTIONS = 4


def _scores_by_cell(model: DecisionModel) -> dict[tuple[str, str], Score]:
    cells: dict[tuple[str, str], Score] = {}
    for score in model.scores:
        cells.setdefault((_key(score.option), _key(score.criterion)), score)
    return cells


def merge_models(first: DecisionModel, second: DecisionModel) -> DecisionModel:
    """One model whose ranges cover both samples' estimates."""
    weights: dict[str, list[float]] = {}
    names: dict[str, str] = {}
    for sample in (first, second):
        for criterion in sample.criteria:
            key = _key(criterion.name)
            names.setdefault(key, criterion.name)
            weights.setdefault(key, []).append(criterion.weight)
    criteria = [Criterion(name=names[k], weight=sum(ws) / 2) for k, ws in weights.items()]

    options = {_key(o) for o in first.options}
    a, b = _scores_by_cell(first), _scores_by_cell(second)
    scores: list[Score] = []
    for cell in list(a) + [c for c in b if c not in a]:
        if cell[0] not in options or cell[1] not in weights:
            continue
        x, y = a.get(cell), b.get(cell)
        if x is not None and y is not None:
            scores.append(x.model_copy(update={
                "low": min(x.low, y.low),
                "high": max(x.high, y.high),
                "source": x.source if x.source is not None else y.source,
            }))
        else:
            scores.append(x or y)

    assumptions = list(dict.fromkeys(first.assumptions + second.assumptions))
    return DecisionModel(
        question=first.question,
        options=first.options,
        criteria=criteria,
        scores=scores,
        assumptions=assumptions[:_MAX_ASSUMPTIONS],
    )


def disagreement(first: DecisionModel, second: DecisionModel) -> float | None:
    """Mean absolute gap between the samples' score midpoints, on a 0-1 scale.

    0 means identical estimates; 0.3 means the samples were 3 points apart on
    the 0-10 scale on average. ``None`` if they share no scored cell.
    """
    a, b = _scores_by_cell(first), _scores_by_cell(second)
    shared = [cell for cell in a if cell in b]
    if not shared:
        return None
    gaps = [
        abs((a[c].low + a[c].high) - (b[c].low + b[c].high)) / 2 / 10 for c in shared
    ]
    return round(sum(gaps) / len(gaps), 3)
