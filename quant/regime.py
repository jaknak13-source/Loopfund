"""Lightweight market regime detection. Pure numpy: classifies the current regime
from trend and volatility of a broad index series. Avoids heavy HMM deps while
giving the MacroAgent a usable risk-on / risk-off / high-vol label.
"""

from __future__ import annotations

import numpy as np

from quant.stats import annualized_vol, closes_to_returns


def detect_regime(index_closes: list[float], vol_high: float = 0.25, vol_low: float = 0.12) -> dict:
    """Return regime label + features. Input: closes of a broad index (e.g. SPY)."""
    rets = closes_to_returns(index_closes)
    if rets.size < 30:
        return {"regime": "unknown", "reason": "insufficient data", "annual_vol": None, "trend": None}

    recent = rets[-63:] if rets.size >= 63 else rets
    vol = annualized_vol(recent)
    trend = float(np.mean(recent) * 252)  # annualized drift proxy

    # Separate the two axes. The old gate ANDed a positive trend with vol<=vol_low,
    # which is unreachable for real equity uptrends (they carry vol>0.12), so risk_on
    # almost never fired and every cycle collapsed to neutral. Now: a positive trend
    # below the high-vol ceiling is risk_on; only genuine crash-vol forces high_vol.
    if vol >= vol_high:
        regime = "high_volatility"
    elif trend < -0.05:
        regime = "risk_off"
    elif trend > 0.05:
        regime = "risk_on"
    else:
        regime = "neutral"

    # Continuous risk_on score so sizing can scale instead of flipping a binary gate.
    risk_on_score = float(np.clip(trend / max(vol, 1e-6), -3.0, 3.0))

    return {
        "regime": regime,
        "annual_vol": vol,
        "trend": trend,
        "risk_on_score": risk_on_score,
        "vol_band": {"high": vol_high, "low": vol_low},
    }
