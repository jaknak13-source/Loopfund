"""Monte Carlo simulation of future price paths (geometric Brownian motion) for
scenario analysis and expected-value estimation. Seeded for reproducibility.
"""

from __future__ import annotations

import numpy as np

from quant.stats import closes_to_returns


def simulate_gbm(
    start_price: float,
    mu_daily: float,
    sigma_daily: float,
    horizon_days: int = 21,
    n_paths: int = 10_000,
    seed: int = 42,
) -> dict:
    """Simulate terminal prices and summarize the distribution.

    Returns expected price, percentile band, prob(loss), and expected return.
    """
    rng = np.random.default_rng(seed)
    shocks = rng.normal(
        loc=(mu_daily - 0.5 * sigma_daily ** 2),
        scale=sigma_daily,
        size=(n_paths, horizon_days),
    )
    log_paths = np.cumsum(shocks, axis=1)
    terminal = start_price * np.exp(log_paths[:, -1])
    ret = terminal / start_price - 1.0
    return {
        "start_price": start_price,
        "horizon_days": horizon_days,
        "n_paths": n_paths,
        "expected_price": float(np.mean(terminal)),
        "median_price": float(np.median(terminal)),
        "p05_price": float(np.percentile(terminal, 5)),
        "p95_price": float(np.percentile(terminal, 95)),
        "expected_return": float(np.mean(ret)),
        "prob_loss": float(np.mean(ret < 0)),
        "var95_return": float(np.percentile(ret, 5)),  # 95% VaR (loss tail)
        "cvar95_return": float(np.mean(ret[ret <= np.percentile(ret, 5)])) if n_paths else 0.0,
    }


def simulate_from_history(closes: list[float], horizon_days: int = 21,
                          n_paths: int = 10_000, seed: int = 42) -> dict | None:
    """Estimate drift/vol from historical closes, then simulate forward."""
    rets = closes_to_returns(closes)
    if rets.size < 20:
        return None
    mu = float(np.mean(rets))
    sigma = float(np.std(rets, ddof=1))
    return simulate_gbm(closes[-1], mu, sigma, horizon_days, n_paths, seed)
