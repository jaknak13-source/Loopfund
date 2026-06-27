"""Position sizing. Fractional Kelly (capped per house rules) and volatility
targeting. Conservative by construction — never sizes above the configured cap.
"""

from __future__ import annotations

from core.config import risk_limits


def kelly_fraction(win_prob: float, win_loss_ratio: float) -> float:
    """Kelly f* = p - (1-p)/b. Clipped to [0,1]. b = avg win / avg loss."""
    if win_loss_ratio <= 0:
        return 0.0
    f = win_prob - (1 - win_prob) / win_loss_ratio
    return max(0.0, min(1.0, f))


def sized_weight(win_prob: float, win_loss_ratio: float,
                 kelly_cap: float | None = None,
                 max_asset_weight: float | None = None) -> dict:
    """Return a recommended portfolio weight from Kelly, capped by house rules."""
    rl = risk_limits()
    cap = kelly_cap if kelly_cap is not None else float(rl.get("kelly_fraction_cap", 0.5))
    max_w = max_asset_weight if max_asset_weight is not None else float(rl.get("max_single_asset_weight", 0.20))

    f_full = kelly_fraction(win_prob, win_loss_ratio)
    f_capped = f_full * cap  # half-Kelly by default
    weight = min(f_capped, max_w)
    return {
        "kelly_full": f_full,
        "kelly_fraction_used": cap,
        "weight_before_asset_cap": f_capped,
        "recommended_weight": weight,
        "max_asset_weight": max_w,
    }


def vol_target_weight(asset_vol_annual: float, target_vol_annual: float = 0.15,
                      max_asset_weight: float | None = None) -> float:
    """Inverse-vol sizing: scale exposure so the position hits a target volatility."""
    if asset_vol_annual <= 0:
        return 0.0
    rl = risk_limits()
    max_w = max_asset_weight if max_asset_weight is not None else float(rl.get("max_single_asset_weight", 0.20))
    return min(target_vol_annual / asset_vol_annual, max_w)
