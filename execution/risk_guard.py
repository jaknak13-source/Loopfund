"""Pre-trade risk enforcement. Validates a proposed order against the house-rule
hard limits BEFORE it reaches the ledger. Code-level backstop independent of the
LLM, so a hallucinated decision still cannot breach concentration or cash rules.
"""

from __future__ import annotations

from core.config import risk_limits
from execution.portfolio import Portfolio

# Minimal crypto classification (standard assets only per house rules).
_CRYPTO = {"BTC-USD", "BTC-EUR", "ETH-USD", "ETH-EUR", "BTC", "ETH"}


def is_crypto(asset: str) -> bool:
    a = asset.upper()
    return a in _CRYPTO or a.endswith("-USD") and a.split("-")[0] in {"BTC", "ETH", "SOL", "XRP", "ADA"}


def cap_for(asset: str) -> float:
    """The max single-position weight allowed for this asset. Broad ETFs get a
    higher cap than single stocks because they are already diversified."""
    rl = risk_limits()
    broad = {s.upper() for s in rl.get("broad_etfs", [])}
    if asset.upper() in broad:
        return float(rl.get("max_etf_weight", 0.50))
    return float(rl.get("max_single_asset_weight", 0.20))


def validate_buy(portfolio: Portfolio, asset: str, eur_amount: float, fee_eur: float,
                 prices_eur: dict[str, float]) -> tuple[bool, str]:
    rl = risk_limits()
    total = portfolio.total_value(prices_eur)
    if total <= 0:
        return False, "portfolio has no value"
    if eur_amount <= 0:
        return False, "non-positive order size"

    cur_asset_val = 0.0
    pos = portfolio.positions.get(asset)
    if pos and asset in prices_eur:
        cur_asset_val = pos.qty * prices_eur[asset]

    post_weight = (cur_asset_val + eur_amount) / total
    max_w = cap_for(asset)
    if post_weight > max_w + 1e-9:
        return False, f"would breach single-asset cap ({post_weight:.2%} > {max_w:.0%})"

    post_cash = portfolio.cash_eur - eur_amount - fee_eur
    min_cash = float(rl.get("min_cash_buffer", 0.05)) * total
    if post_cash < min_cash - 1e-9:
        return False, f"would breach min cash buffer (post cash {post_cash:.2f} < {min_cash:.2f})"

    if is_crypto(asset):
        crypto_val = sum(
            p.qty * prices_eur.get(a, 0.0) for a, p in portfolio.positions.items() if is_crypto(a)
        )
        max_crypto = float(rl.get("max_crypto_weight", 0.10))
        if (crypto_val + eur_amount) / total > max_crypto + 1e-9:
            return False, f"would breach crypto cap ({max_crypto:.0%})"

    if not bool(rl.get("allow_leverage", False)) and eur_amount + fee_eur > portfolio.cash_eur + 1e-9:
        return False, "insufficient cash (no leverage allowed)"

    return True, "ok"
