"""Shared numeric helpers: returns, volatility, correlation with shrinkage."""

from __future__ import annotations

import numpy as np


def closes_to_returns(closes: list[float]) -> np.ndarray:
    arr = np.asarray(closes, dtype=float)
    if arr.size < 2:
        return np.array([])
    return np.diff(arr) / arr[:-1]


def annualized_vol(returns: np.ndarray, periods_per_year: int = 252) -> float:
    if returns.size < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def ewma_vol(returns: np.ndarray, lam: float = 0.94, periods_per_year: int = 252) -> float:
    """RiskMetrics-style EWMA volatility (more responsive than plain stdev)."""
    if returns.size < 2:
        return 0.0
    var = returns[0] ** 2
    for r in returns[1:]:
        var = lam * var + (1 - lam) * r ** 2
    return float(np.sqrt(var) * np.sqrt(periods_per_year))


def annualized_return(returns: np.ndarray, periods_per_year: int = 252) -> float:
    if returns.size == 0:
        return 0.0
    return float(np.mean(returns) * periods_per_year)


def sharpe(returns: np.ndarray, rf: float = 0.0, periods_per_year: int = 252) -> float:
    if returns.size < 2:
        return 0.0
    excess = returns - rf / periods_per_year
    sd = np.std(excess, ddof=1)
    if sd == 0:
        return 0.0
    return float(np.mean(excess) / sd * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: np.ndarray) -> float:
    if equity_curve.size == 0:
        return 0.0
    peak = np.maximum.accumulate(equity_curve)
    dd = (equity_curve - peak) / peak
    return float(dd.min())


def shrink_corr(returns_matrix: np.ndarray, shrink: float = 0.2) -> np.ndarray:
    """Correlation matrix shrunk toward the identity (Ledoit-Wolf-lite). Stabilizes
    estimates when samples are few relative to assets.
    """
    if returns_matrix.ndim != 2 or returns_matrix.shape[0] < 2:
        return np.array([[1.0]])
    corr = np.corrcoef(returns_matrix, rowvar=False)
    corr = np.nan_to_num(corr, nan=0.0)
    ident = np.eye(corr.shape[0])
    return (1 - shrink) * corr + shrink * ident
