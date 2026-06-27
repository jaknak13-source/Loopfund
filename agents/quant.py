"""QuantAgent: runs reproducible numeric models (factors, Monte Carlo, vol, Kelly
sizing, regime) over a watchlist, saves an artifact, and reports structured
numbers. The math is deterministic and does not depend on the LLM, so its output
is trustworthy even when the model is weak or offline.
"""

from __future__ import annotations

import math

from agents.base import BaseAgent
from core.blackboard import Blackboard
from models_adapter.router import ModelRouter
from quant import factors, montecarlo, regime
from quant.artifacts import save_artifact
from quant.sizing import sized_weight, vol_target_weight
from quant.stats import annualized_vol, closes_to_returns
from datetime import datetime, timezone

from schemas import AgentReport, Citation, Confidence
from tools.registry import ToolRegistry

DEFAULT_WATCHLIST = ["SPY", "NVDA", "AAPL", "MSFT", "XOM"]


class QuantAgent(BaseAgent):
    name = "QuantAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 watchlist: list[str] | None = None, index_symbol: str = "SPY") -> None:
        super().__init__(bb, router, tools)
        self.watchlist = watchlist or list(DEFAULT_WATCHLIST)
        self.index_symbol = index_symbol

    async def _closes(self, ticker: str) -> list[float]:
        res, _rec = await self.tools.call(self.name, "history", ticker=ticker, period="1y")
        return [b["close"] for b in res.get("bars", [])]

    async def run(self, cycle_id: str) -> AgentReport:
        tool_ids: list[str] = []
        per_asset: dict[str, dict] = {}

        # market regime from the index
        idx_closes = await self._closes(self.index_symbol)
        reg = regime.detect_regime(idx_closes)

        for tkr in self.watchlist:
            closes = await self._closes(tkr)
            if len(closes) < 30:
                per_asset[tkr] = {"error": "insufficient history", "n": len(closes)}
                continue
            rets = closes_to_returns(closes)
            mc = montecarlo.simulate_from_history(closes, horizon_days=21, n_paths=5000)
            facs = factors.factor_scores(closes)
            vol = annualized_vol(rets)

            win_prob = (1.0 - mc["prob_loss"]) if mc else 0.5
            # crude win/loss ratio from MC tails
            wl = abs(mc["p95_price"] - mc["start_price"]) / max(1e-9, abs(mc["start_price"] - mc["p05_price"])) if mc else 1.0
            size = sized_weight(win_prob, wl)
            vt = vol_target_weight(vol)
            per_asset[tkr] = {
                "factors": facs,
                "annual_vol": vol,
                "monte_carlo": mc,
                "kelly_sizing": size,
                "vol_target_weight": vt,
            }

        artifact = {"cycle_id": cycle_id, "regime": reg, "assets": per_asset}
        path = save_artifact("quant_cycle", artifact)

        report = self._build_report(cycle_id, reg, per_asset, str(path), tool_ids)
        self.bb.write_report(report)
        self.log.info("quant_done", regime=reg["regime"], n_assets=len(per_asset), artifact=str(path))
        return report

    def _build_report(self, cycle_id, reg, per_asset, artifact_path, tool_ids) -> AgentReport:
        # drop assets whose models produced NaN/inf (bad/short history) — they were leaking
        # 'nan' into expected return/vol/signal and confusing every downstream agent.
        valid = {k: v for k, v in per_asset.items()
                 if "error" not in v and not _has_bad_numbers(v)}
        # rank by Kelly-recommended weight
        ranked = sorted(
            valid.items(), key=lambda kv: kv[1]["kelly_sizing"]["recommended_weight"], reverse=True
        )
        findings = [f"Regime: {reg['regime']} (vol={_fmt(reg.get('annual_vol'))}, trend={_fmt(reg.get('trend'))})"]
        for tkr, v in ranked[:5]:
            mc = v["monte_carlo"]
            findings.append(
                f"{tkr}: 21d E[ret]={_fmt(mc['expected_return'])}, P(loss)={_fmt(mc['prob_loss'])}, "
                f"vol={_fmt(v['annual_vol'])}, kelly_w={_fmt(v['kelly_sizing']['recommended_weight'])}, "
                f"mom={_fmt((v['factors'] or {}).get('momentum_12_1'))}"
            )

        # deterministic per-asset numeric signal in [-1, 1]: a composite of 21d expected
        # return (scaled), 12-1 momentum, and a volatility penalty. This is the trustworthy,
        # model-independent edge — it flows into evidence.aggregate directly (stance-agnostic).
        asset_signals = {tkr: _signal(v) for tkr, v in valid.items()}

        # stance: align to regime, then numeric breadth so a flat regime still leans with the
        # weight of positive- vs negative-signal names instead of defaulting to neutral.
        pos = sum(1 for s in asset_signals.values() if s > 0.05)
        neg = sum(1 for s in asset_signals.values() if s < -0.05)
        if reg["regime"] == "risk_off":
            stance = "bearish"
        elif reg["regime"] == "risk_on" and pos >= max(1, len(valid) // 2):
            stance = "bullish"
        elif pos > neg and pos >= max(1, len(valid) // 2):
            stance = "bullish"
        elif neg > pos and neg >= max(1, len(valid) // 2):
            stance = "bearish"
        else:
            stance = "neutral"

        # confidence reflects the actual diagnostics, not a constant: a clear regime, more
        # modeled names, and more strong signals = a more trustworthy deterministic read
        # (a verified quant computation should be allowed to exceed the old 0.55 cap).
        n_strong = sum(1 for s in asset_signals.values() if abs(s) > 0.3)
        score = (0.45 + (0.10 if reg["regime"] in ("risk_on", "risk_off") else 0.0)
                 + min(0.15, 0.03 * n_strong) + min(0.05, 0.01 * len(valid)))
        score = round(min(0.78, score), 3)
        rationale = (f"deterministic MC/factor/Kelly on 1y history; regime={reg['regime']}, "
                     f"{len(valid)} names modeled, {n_strong} with strong (|signal|>0.3) reads")
        return self.make_report(
            cycle_id=cycle_id,
            topic="quant models",
            summary=(f"Quant cycle: regime={reg['regime']}, {len(valid)} assets modeled "
                     f"(Monte Carlo + factors + Kelly). Artifact: {artifact_path}"),
            confidence=Confidence(score=score, low=max(0.0, score - 0.12), high=min(1.0, score + 0.12),
                                  rationale=rationale),
            stance=stance,
            assets=list(valid.keys()),
            asset_signals=asset_signals,
            findings=findings,
            citations=[Citation(source="quant models (Monte Carlo/factors/Kelly on 1y exchange price history)",
                                claim="computed risk/return metrics", verified=True, primary=False,
                                retrieved_at=datetime.now(timezone.utc))],
            tool_calls=tool_ids,
        )


def _num(x) -> float:
    """NaN/inf/None -> 0.0 (so bad model output never poisons a signal)."""
    try:
        f = float(x)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _has_bad_numbers(v: dict) -> bool:
    mc = v.get("monte_carlo") or {}
    for x in (mc.get("expected_return"), mc.get("prob_loss"), v.get("annual_vol")):
        try:
            if x is not None and not math.isfinite(float(x)):
                return True
        except (TypeError, ValueError):
            return True
    return False


def _signal(v: dict) -> float:
    """Composite per-asset signal in [-1, 1] from deterministic models.

    21d expected return (the dominant term, scaled so ~+/-5% maps to ~+/-0.7),
    plus a momentum tilt, minus a volatility penalty so high-vol names are damped.
    """
    mc = v.get("monte_carlo") or {}
    ev = _num(mc.get("expected_return"))
    mom = _num((v.get("factors") or {}).get("momentum_12_1"))
    vol = _num(v.get("annual_vol"))
    raw = 14.0 * ev + 0.5 * mom - 0.3 * max(0.0, vol - 0.2)
    return max(-1.0, min(1.0, raw))


def _fmt(x) -> str:
    if x is None:
        return "n/a"
    try:
        return f"{float(x):.3f}"
    except (TypeError, ValueError):
        return str(x)
