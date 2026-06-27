"""Fair-value estimation: a transparent DCF + a multiples cross-check. Assumptions
are explicit and returned with the output (no false precision). Used to give the
fund real valuation evidence and upside/downside targets, not just LLM guesses.
"""

from __future__ import annotations


def dcf(cash_flow: float, growth: float, *, discount: float = 0.10, years: int = 5,
        terminal_growth: float = 0.025, shares: float | None = None,
        net_debt: float = 0.0) -> dict:
    """Discounted-cash-flow value. Projects `cash_flow` growing at `growth` for
    `years`, adds a Gordon terminal value, discounts to PV. Returns equity value
    and per-share fair value (if shares given), with the assumptions used."""
    growth = max(-0.30, min(0.40, growth))
    terminal_growth = min(terminal_growth, discount - 0.01)  # keep TV finite/sane
    pv, cf = 0.0, cash_flow
    for y in range(1, years + 1):
        cf *= (1 + growth)
        pv += cf / ((1 + discount) ** y)
    terminal = cf * (1 + terminal_growth) / (discount - terminal_growth)
    pv += terminal / ((1 + discount) ** years)
    equity = pv - net_debt
    per_share = (equity / shares) if shares and shares > 0 else None
    return {
        "enterprise_value": pv,
        "equity_value": equity,
        "fair_value_per_share": per_share,
        "assumptions": {"cash_flow": cash_flow, "growth": growth, "discount": discount,
                        "years": years, "terminal_growth": terminal_growth,
                        "shares": shares, "net_debt": net_debt},
    }


def reverse_dcf(price: float, cash_flow: float, shares: float, *, discount: float = 0.10,
                years: int = 5, terminal_growth: float = 0.025, net_debt: float = 0.0) -> float | None:
    """Growth rate the current price implies (is the market's expectation reasonable?)."""
    if not (price and shares and cash_flow):
        return None
    target_equity = price * shares + net_debt
    lo, hi = -0.30, 0.40
    for _ in range(60):  # bisection on growth
        mid = (lo + hi) / 2
        eq = dcf(cash_flow, mid, discount=discount, years=years,
                 terminal_growth=terminal_growth, shares=shares, net_debt=net_debt)["equity_value"]
        if eq < target_equity:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def multiples_value(eps: float | None, peer_pe: float = 18.0) -> float | None:
    """Simple relative value: EPS x a peer/market P/E."""
    if eps is None:
        return None
    return eps * peer_pe


def blend(dcf_ps: float | None, mult_ps: float | None) -> float | None:
    vals = [v for v in (dcf_ps, mult_ps) if v is not None and v > 0]
    return sum(vals) / len(vals) if vals else None
