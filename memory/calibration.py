"""Calibration: score past decisions and reports against realized outcomes so the
system learns. Produces Brier score (probability calibration), directional
precision, and learned agent priors that feed back into evidence weighting.

Pure functions over (decision/report, realized_forward_return) pairs. The
orchestrator supplies forward returns from price history; the math lives here.
"""

from __future__ import annotations

from agents.evidence import DEFAULT_PRIORS
from schemas import PortfolioDecision, TradeAction

_BULLISH = {TradeAction.BUY, TradeAction.ADD}
_BEARISH = {TradeAction.SELL, TradeAction.TRIM, TradeAction.HEDGE}


def directional_correct(action: TradeAction, fwd_return: float) -> bool | None:
    """Was the directional call right given the asset's forward return? None if N/A."""
    if action in _BULLISH:
        return fwd_return > 0
    if action in _BEARISH:
        return fwd_return < 0
    return None  # no_action / hold are not directional bets


def evaluate_decisions(pairs: list[tuple[PortfolioDecision, float]]) -> dict:
    """pairs: (decision, realized_forward_return_of_asset)."""
    brier_sum = 0.0
    n_brier = 0
    bull_hits = bull_n = bear_hits = bear_n = 0
    for d, ret in pairs:
        correct = directional_correct(d.action, ret)
        if correct is None:
            continue
        brier_sum += (d.confidence.score - (1.0 if correct else 0.0)) ** 2
        n_brier += 1
        if d.action in _BULLISH:
            bull_n += 1
            bull_hits += int(correct)
        elif d.action in _BEARISH:
            bear_n += 1
            bear_hits += int(correct)
    return {
        "n_scored": n_brier,
        "brier_score": (brier_sum / n_brier) if n_brier else None,  # lower is better; 0.25 = chance
        "bullish_precision": (bull_hits / bull_n) if bull_n else None,
        "bearish_precision": (bear_hits / bear_n) if bear_n else None,
        "hit_rate": ((bull_hits + bear_hits) / n_brier) if n_brier else None,
    }


def agent_hit_rates(outcomes: list[tuple[str, str, float]]) -> dict[str, float]:
    """outcomes: (agent, stance, realized_return). Hit rate of each agent's stance."""
    tally: dict[str, list[int]] = {}
    for agent, stance, ret in outcomes:
        if stance == "bullish":
            hit = ret > 0
        elif stance == "bearish":
            hit = ret < 0
        else:
            continue
        tally.setdefault(agent, []).append(int(hit))
    return {a: (sum(v) / len(v)) for a, v in tally.items() if v}


def learned_priors(hit_rates: dict[str, float], base: dict[str, float] | None = None,
                   blend: float = 0.5) -> dict[str, float]:
    """Adjust base priors by observed hit rate. prior *= (0.5 + hit_rate) blended
    with 1.0 by `blend`. Clamped to [0.2, 2.0]. Needs enough samples upstream.
    """
    base = base or DEFAULT_PRIORS
    out = dict(base)
    for agent, hr in hit_rates.items():
        factor = (1 - blend) + blend * (0.5 + hr)  # hr=0.5 -> ~1.0; hr=1 -> up; hr=0 -> down
        out[agent] = max(0.2, min(2.0, base.get(agent, 0.7) * factor))
    return out
