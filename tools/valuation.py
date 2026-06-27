"""estimate_fair_value tool: pulls real SEC financials + current price, runs a DCF
and a multiples cross-check, and returns a fair-value band + upside/downside vs price.
Transparent assumptions; degrades gracefully for non-US/missing data."""

from __future__ import annotations

from core.logging import get_logger
from quant import valuation
from tools import filings, market

log = get_logger("valuation")


async def estimate_fair_value(ticker: str, discount: float = 0.10, peer_pe: float = 18.0) -> dict:
    sec = await filings.sec_financials(ticker)
    f = sec.get("financials") or {}
    ni = f.get("net_income")
    eps = f.get("eps_diluted")
    if ni is None and eps is None:
        return {"ticker": ticker, "available": False,
                "reason": "no SEC earnings (non-US filer or missing) — value qualitatively"}

    shares = (ni / eps) if (ni and eps and eps != 0) else None
    net_debt = (f.get("long_term_debt") or 0.0) - (f.get("cash") or 0.0)
    growth = f.get("revenue_yoy")
    growth = growth if growth is not None else 0.08

    d = valuation.dcf(ni, growth, discount=discount, shares=shares, net_debt=net_debt) if ni else {}
    dcf_ps = d.get("fair_value_per_share")
    mult_ps = valuation.multiples_value(eps, peer_pe)
    fair = valuation.blend(dcf_ps, mult_ps)

    px = await market.get_price(ticker)
    price = px.get("price")
    implied_growth = valuation.reverse_dcf(price, ni, shares, discount=discount) if (price and ni and shares) else None
    upside = (fair / price - 1.0) if (fair and price) else None

    return {
        "ticker": ticker, "current_price": price, "ccy": px.get("ccy"),
        "fair_value_dcf": dcf_ps, "fair_value_multiples": mult_ps, "fair_value_blend": fair,
        "upside_pct": (round(upside * 100, 1) if upside is not None else None),
        "price_implied_growth": implied_growth,
        "inputs": {"net_income": ni, "eps": eps, "shares_est": shares, "net_debt": net_debt,
                   "growth_used": round(growth, 4), "discount": discount, "peer_pe": peer_pe},
        "caveat": "DCF on earnings proxy with explicit assumptions — a guide, not precise truth. Verify drivers.",
        "source": "dcf+multiples on SEC XBRL",
    }
