"""Evidence-weighted aggregation of agent reports. Resolves disagreement by
weighting (not majority vote): each report contributes by its confidence, the
agent's prior reliability, and its source quality. Unverified claims are penalized.

Agent priors start static and are updated by the calibration loop (Phase 6),
which can pass an overrides dict.
"""

from __future__ import annotations

from core.sources import is_credible, registrable_domain
from schemas import AgentReport

# How much weight a deterministic numeric signal (asset_signals) carries relative to
# the stance-sign path. Numeric edge is model-independent, so it gets full weight.
_NUMERIC_GAIN = 1.0

DEFAULT_PRIORS: dict[str, float] = {
    "QuantAgent": 1.2,
    "FundamentalsAgent": 1.1,
    "MacroAgent": 1.0,
    "RiskAgent": 1.0,
    "SmartMoneyAgent": 0.9,
    "ResearchAgent": 0.8,
    "IpoMnaAgent": 0.7,
    "SentimentAgent": 0.6,
    "AltDataAgent": 0.5,
}

_SIGN = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0, "uncertain": 0.0}


def _safe_abs(x) -> float:
    try:
        f = abs(float(x))
        return f if f == f else 0.0  # NaN -> 0
    except (TypeError, ValueError):
        return 0.0


def _source_quality(r: AgentReport) -> float:
    """1.0 baseline; bonus for verified primary citations; penalty for unverified."""
    q = 1.0
    if any(c.verified and c.primary for c in r.citations):
        q += 0.2
    q -= 0.1 * min(3, len(r.unverified_claims))
    return max(0.3, q)


def report_weight(r: AgentReport, priors: dict[str, float] | None = None) -> float:
    p = (priors or DEFAULT_PRIORS).get(r.agent, 0.7)
    return r.confidence.score * p * _source_quality(r)


def aggregate(reports: list[AgentReport], priors: dict[str, float] | None = None) -> dict:
    """Return per-asset net signal, overall market signal, and total weight."""
    per_asset: dict[str, float] = {}
    market_signal = 0.0
    total_weight = 0.0
    risk_signal = 0.0
    # per-asset corroboration evidence: distinct credible web domains AND distinct independent
    # analysts who took a directional view (STRATEGY.md: "several agents independently agreeing
    # DO count" + first-party market/SEC/quant data counts). Either path can satisfy the >=2 rule.
    domains: dict[str, set[str]] = {}
    supporters: dict[str, set[str]] = {}
    _NON_ANALYST = {"RiskAgent", "DecisionAgent", "CouncilAgent", "MetaAgent"}

    for r in reports:
        w = report_weight(r, priors)
        sign = _SIGN.get(r.stance, 0.0)
        total_weight += w
        if r.agent == "RiskAgent":
            risk_signal += w * sign  # usually <= 0; a brake on bullishness
        if r.assets:
            for a in r.assets:
                per_asset[a] = per_asset.get(a, 0.0) + w * sign
        else:
            market_signal += w * sign

        # deterministic numeric edge — stance-independent, never zeroed by a neutral label
        for a, s in (r.asset_signals or {}).items():
            try:
                contrib = w * _NUMERIC_GAIN * max(-1.0, min(1.0, float(s)))
            except (TypeError, ValueError):
                continue
            per_asset[a] = per_asset.get(a, 0.0) + contrib

        # corroboration source 1: distinct credible web domains
        cred = {registrable_domain(c.source) for c in r.citations
                if c.verified and is_credible(c.source)}
        cred.discard("")
        if cred:
            for a in r.assets:
                domains.setdefault(a, set()).update(cred)

        # corroboration source 2: an INDEPENDENT analyst with a directional read on the name
        # (a committed bullish/bearish stance, or a non-trivial deterministic signal).
        if r.agent not in _NON_ANALYST:
            engaged = set(r.assets) if r.stance in ("bullish", "bearish") else set()
            engaged |= {a for a, s in (r.asset_signals or {}).items()
                        if _safe_abs(s) > 0.05}
            for a in engaged:
                supporters.setdefault(a, set()).add(r.agent)

    # an asset is corroborated by distinct credible domains PLUS distinct agreeing analysts
    assets_seen = set(domains) | set(supporters)
    corroboration = {a: len(domains.get(a, set())) + len(supporters.get(a, set()))
                     for a in assets_seen}
    ranked = sorted(per_asset.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "per_asset": per_asset,
        "ranked": ranked,
        "market_signal": market_signal,
        "risk_signal": risk_signal,
        "total_weight": total_weight,
        "corroboration": corroboration,
        "top_long": ranked[0] if ranked else None,
        "top_short": ranked[-1] if ranked else None,
    }
