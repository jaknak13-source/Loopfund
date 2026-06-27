"""Transaction cost model (EUR). Configurable in risk_limits.yaml. Defaults model
a Trade-Republic-style 1 EUR flat fee plus an FX spread on non-EUR notional.
"""

from __future__ import annotations

from core.config import risk_limits


def compute_fee(notional_eur: float, ccy: str = "EUR") -> float:
    cfg = risk_limits().get("fees", {})
    model = cfg.get("model", "flat")
    flat = float(cfg.get("flat_eur", 1.0))
    fx_spread_bps = float(cfg.get("fx_spread_bps", 0.0))

    fee = flat if model == "flat" else flat  # tiered model can extend here
    if ccy.upper() != "EUR" and fx_spread_bps:
        fee += abs(notional_eur) * (fx_spread_bps / 10_000.0)
    return round(fee, 4)
