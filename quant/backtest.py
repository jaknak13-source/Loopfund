"""Minimal vectorized backtest. Given a price series and a signal series in
[-1, 1] (target exposure), compute equity curve, Sharpe, and max drawdown.
Used in dry mode and idle deep-research to sanity-check a signal before trusting it.
"""

from __future__ import annotations

import numpy as np

from quant.stats import closes_to_returns, max_drawdown, sharpe


def backtest_signal(closes: list[float], signal: list[float], cost_bps: float = 5.0) -> dict:
    """signal[t] is the exposure held INTO period t+1's return. Includes turnover cost."""
    rets = closes_to_returns(closes)
    if rets.size == 0:
        return {"error": "insufficient data"}
    sig = np.asarray(signal, dtype=float)
    # align: use signal[:-1] against rets (signal decided before the return)
    if sig.size >= rets.size + 1:
        sig = sig[: rets.size]
    elif sig.size < rets.size:
        sig = np.pad(sig, (0, rets.size - sig.size), constant_values=sig[-1] if sig.size else 0.0)

    turnover = np.abs(np.diff(np.concatenate([[0.0], sig])))
    cost = turnover * (cost_bps / 10_000.0)
    strat_rets = sig * rets - cost
    equity = np.cumprod(1 + strat_rets)
    return {
        "total_return": float(equity[-1] - 1.0),
        "sharpe": sharpe(strat_rets),
        "max_drawdown": max_drawdown(equity),
        "n_periods": int(rets.size),
        "avg_exposure": float(np.mean(sig)),
        "cost_drag": float(np.sum(cost)),
    }
