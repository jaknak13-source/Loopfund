"""Portfolio-level risk governor — the brake that prevents a slow bleed turning
into a catastrophic drawdown. Tracks the high-water mark and the day's starting
equity, classifies a risk state, and tells the orchestrator what is allowed.

States:
  normal  — trade as usual
  reduce  — >soft drawdown OR >daily loss: NO new single-stock/crypto risk, ETF core only
  derisk  — >hard drawdown: sell non-core positions, raise cash, NO buys at all

It also flags individual positions that breached their stop loss. Pure functions
over (portfolio, prices, marks dict); the orchestrator persists the marks.
"""

from __future__ import annotations

from core.config import risk_limits
from execution.portfolio import Portfolio

NORMAL, REDUCE, DERISK = "normal", "reduce", "derisk"


def _broad_etfs() -> set[str]:
    return {s.upper() for s in risk_limits().get("broad_etfs", [])}


def update_marks(marks: dict, total: float, today: str) -> dict:
    """Update high-water mark and day-start equity. `marks` mutated and returned."""
    marks["hwm"] = max(marks.get("hwm") or total, total)
    if marks.get("day_date") != today:
        marks["day_date"] = today
        marks["day_start_equity"] = total
    marks.setdefault("day_start_equity", total)
    return marks


def drawdown(total: float, hwm: float | None) -> float:
    if not hwm or hwm <= 0:
        return 0.0
    return total / hwm - 1.0  # negative when below peak


def day_change(total: float, day_start: float | None) -> float:
    if not day_start or day_start <= 0:
        return 0.0
    return total / day_start - 1.0


def assess(total: float, marks: dict) -> dict:
    rl = risk_limits()
    dd = drawdown(total, marks.get("hwm"))
    dc = day_change(total, marks.get("day_start_equity"))
    if dd <= -float(rl.get("max_drawdown_hard", 0.15)):
        state = DERISK
    elif dd <= -float(rl.get("max_drawdown_soft", 0.08)) or dc <= -float(rl.get("daily_loss_limit", 0.06)):
        state = REDUCE
    else:
        state = NORMAL
    return {"state": state, "drawdown": dd, "day_change": dc,
            "hwm": marks.get("hwm"), "reason": _reason(state, dd, dc)}


def _reason(state: str, dd: float, dc: float) -> str:
    if state == DERISK:
        return f"drawdown {dd:.1%} breached hard limit — de-risking to cash/core"
    if state == REDUCE:
        return f"drawdown {dd:.1%} / day {dc:.1%} — new risk restricted to ETF core"
    return "within risk budget"


def allow_buy(asset: str, state: str) -> bool:
    if state == DERISK:
        return False
    if state == REDUCE:
        return asset.upper() in _broad_etfs()  # defensive core only
    return True


def stop_loss_hits(portfolio: Portfolio, prices_eur: dict[str, float]) -> list[str]:
    sl = float(risk_limits().get("stop_loss_pct", 0.20))
    hits = []
    for a, pos in portfolio.positions.items():
        px = prices_eur.get(a)
        if px and pos.avg_cost_eur > 0 and (px / pos.avg_cost_eur - 1.0) <= -sl:
            hits.append(a)
    return hits


def non_core_positions(portfolio: Portfolio) -> list[str]:
    core = _broad_etfs()
    return [a for a in portfolio.positions if a.upper() not in core]
