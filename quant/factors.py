"""Simple factor scores from price history: momentum, volatility, trend.
Cross-sectional ranking helps compare candidates on a common scale.
"""

from __future__ import annotations

import numpy as np

from quant.stats import annualized_vol, closes_to_returns


def momentum(closes: list[float], lookback: int = 126, skip: int = 21) -> float | None:
    """Total return over `lookback` periods, skipping the most recent `skip`
    (classic 12-1 style momentum to avoid short-term reversal)."""
    arr = np.asarray(closes, dtype=float)
    if arr.size < lookback + skip + 1:
        return None
    end = -skip if skip else -1
    start = end - lookback
    return float(arr[end] / arr[start] - 1.0)


def trend_strength(closes: list[float], window: int = 50) -> float | None:
    """Fraction of recent closes above their moving average (0..1)."""
    arr = np.asarray(closes, dtype=float)
    if arr.size < window + 5:
        return None
    ma = np.convolve(arr, np.ones(window) / window, mode="valid")
    recent = arr[window - 1 :]
    return float(np.mean(recent >= ma))


def factor_scores(closes: list[float]) -> dict:
    rets = closes_to_returns(closes)
    return {
        "momentum_12_1": momentum(closes),
        "trend_strength": trend_strength(closes),
        "annual_vol": annualized_vol(rets) if rets.size else None,
        "n_obs": int(len(closes)),
    }


def zscore_rank(values: dict[str, float | None]) -> dict[str, float]:
    """Cross-sectional z-score of a factor across assets (ignores Nones)."""
    items = [(k, v) for k, v in values.items() if v is not None]
    if len(items) < 2:
        return {k: 0.0 for k, _ in items}
    arr = np.array([v for _, v in items], dtype=float)
    mu, sd = float(np.mean(arr)), float(np.std(arr, ddof=1))
    if sd == 0:
        return {k: 0.0 for k, _ in items}
    return {k: float((v - mu) / sd) for k, v in items}
