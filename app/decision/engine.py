"""Score a :class:`DecisionModel`, simulate its uncertainty, find its flip points.

* **Expected score**: weights (normalized) times the midpoint of each 0-10 range.
* **Monte Carlo**: each simulation draws weights from a Dirichlet centred on the
  stated weights and every score uniformly from its low-high range, then records
  the winner. The share of wins is the option's ``win_probability``. Wide ranges
  and close options give honest, low probabilities instead of a made-up
  confidence number.
* **Flip points**: for each criterion, the weight at which the winner changes
  (other weights rescaled proportionally). Each option's score is linear in that
  weight, so the crossing is solved exactly rather than searched for.

The random seed is derived from the model's content, so the same model always
produces the same report (important for record/replay and tests).
"""

from __future__ import annotations

import hashlib

import numpy as np

from app.models.decision import DecisionModel, DecisionReport, FlipPoint, OptionResult

DEFAULT_SIMULATIONS = 4000
#: Dirichlet concentration: higher = weights treated as more certain.
DEFAULT_WEIGHT_CONCENTRATION = 30.0
#: Win probability needed for each verdict.
ROBUST_AT = 0.8
LEANING_AT = 0.6


def _key(name: str) -> str:
    return " ".join(name.lower().split())


def _matrices(model: DecisionModel) -> tuple[np.ndarray, np.ndarray, list[str], int]:
    """``(low, high)`` arrays shaped (options, criteria), gaps, and cited count."""
    n_opt, n_crit = len(model.options), len(model.criteria)
    low = np.zeros((n_opt, n_crit))
    high = np.full((n_opt, n_crit), 10.0)
    seen = np.zeros((n_opt, n_crit), dtype=bool)
    opt_index = {_key(o): i for i, o in enumerate(model.options)}
    crit_index = {_key(c.name): j for j, c in enumerate(model.criteria)}
    cited = 0
    for score in model.scores:
        i, j = opt_index.get(_key(score.option)), crit_index.get(_key(score.criterion))
        if i is None or j is None or seen[i, j]:
            continue
        low[i, j], high[i, j] = score.low, score.high
        seen[i, j] = True
        cited += score.source is not None
    gaps = [
        f"{model.options[i]} / {model.criteria[j].name}"
        for i in range(n_opt)
        for j in range(n_crit)
        if not seen[i, j]
    ]
    return low, high, gaps, cited


def _seed(model: DecisionModel) -> int:
    digest = hashlib.sha256(model.model_dump_json().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _flip_points(mid: np.ndarray, weights: np.ndarray, names: list[str],
                 options: list[str]) -> list[FlipPoint]:
    winner = int(np.argmax(mid @ weights))
    points: list[FlipPoint] = []
    for c, w_c in enumerate(weights):
        if w_c >= 1.0:
            continue
        others = np.delete(np.arange(len(weights)), c)
        # Score of every option if criterion c is ignored (others renormalized).
        rest = mid[:, others] @ (weights[others] / (1.0 - w_c))
        best: tuple[float, int] | None = None
        for o in range(len(options)):
            if o == winner:
                continue
            # D(t) = t*(m_wc - m_oc) + (1-t)*(R_w - R_o); find the root in [0, 1].
            a = rest[winner] - rest[o]
            b = mid[winner, c] - mid[o, c]
            if np.isclose(a, b):
                continue
            t = a / (a - b)
            if not 0.0 <= t <= 1.0:
                continue
            # Confirm the overall winner really changes just past the crossing.
            probe = min(1.0, t + 1e-6) if t > w_c else max(0.0, t - 1e-6)
            w_probe = np.empty_like(weights)
            w_probe[others] = weights[others] * (1.0 - probe) / (1.0 - w_c)
            w_probe[c] = probe
            if int(np.argmax(mid @ w_probe)) == winner:
                continue
            if best is None or abs(t - w_c) < abs(best[0] - w_c):
                best = (float(t), int(np.argmax(mid @ w_probe)))
        if best is not None:
            t, new = best
            points.append(FlipPoint(
                criterion=names[c],
                current_weight=round(float(w_c), 3),
                flip_weight=round(t, 3),
                new_winner=options[new],
                direction="increase" if t > w_c else "decrease",
            ))
    points.sort(key=lambda p: abs(p.flip_weight - p.current_weight))
    return points


def analyze(
    model: DecisionModel,
    *,
    simulations: int = DEFAULT_SIMULATIONS,
    weight_concentration: float = DEFAULT_WEIGHT_CONCENTRATION,
) -> DecisionReport:
    """Run the full deterministic analysis of ``model``."""
    low, high, gaps, cited = _matrices(model)
    raw = np.array([c.weight for c in model.criteria], dtype=float)
    weights = raw / raw.sum()
    mid = (low + high) / 2.0
    expected = mid @ weights

    rng = np.random.default_rng(_seed(model))
    sampled_w = rng.dirichlet(weights * weight_concentration, size=simulations)
    sampled_s = rng.uniform(low, high, size=(simulations, *low.shape))
    totals = np.einsum("soc,sc->so", sampled_s, sampled_w)
    wins = np.bincount(np.argmax(totals, axis=1), minlength=len(model.options))
    win_prob = wins / simulations

    # Rank by win probability, then expected score.
    order = sorted(range(len(model.options)), key=lambda i: (-win_prob[i], -expected[i]))
    ranking = [
        OptionResult(
            option=model.options[i],
            expected_score=round(float(expected[i]), 2),
            win_probability=round(float(win_prob[i]), 3),
            rank=rank,
        )
        for rank, i in enumerate(order, start=1)
    ]
    top = ranking[0]
    verdict = ("robust" if top.win_probability >= ROBUST_AT
               else "leaning" if top.win_probability >= LEANING_AT else "toss-up")
    names = [c.name for c in model.criteria]
    return DecisionReport(
        winner=top.option,
        verdict=verdict,
        win_probability=top.win_probability,
        ranking=ranking,
        flip_points=_flip_points(mid, weights, names, model.options),
        weights={n: round(float(w), 3) for n, w in zip(names, weights)},
        simulations=simulations,
        gaps=gaps,
        cited_scores=cited,
        total_scores=len(model.options) * len(model.criteria) - len(gaps),
    )
