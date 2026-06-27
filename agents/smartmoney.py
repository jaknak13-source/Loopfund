"""SmartMoneyAgent: follow the disclosed flows of people who may hold an
informational edge — US politicians (House/Senate disclosures), and corporate
insiders (SEC Form-4: CEOs, officers, directors). Deterministic, no LLM call, so
it is cheap and trustworthy on the M4. It turns these disclosures into a signed
per-ticker signal that feeds evidence.aggregate's numeric channel directly, and
surfaces fresh names the smart money bought (not just the current watchlist).

Coverage (honest): congressional disclosures carry direction + amount and are the
primary signed source here; SEC Form-4 presence is used as a corroborating insider-
activity flag (full buy/sell direction parsing of Form-4 XML, and 13F institutional
holdings, are future work — see ROADMAP). Disclosures lag the actual trade (days to
weeks) and are LEADS, not certainties — sized small by the decision/risk layer.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from agents.base import BaseAgent
from core.blackboard import Blackboard
from models_adapter.router import ModelRouter
from schemas import AgentReport, Citation, Confidence
from tools.registry import ToolRegistry

_BUY = {"purchase", "buy", "p", "purchase_full", "purchase_partial"}
_SELL = {"sale", "sell", "s", "sale_full", "sale_partial", "sale (full)", "sale (partial)"}

# scale that maps net weighted flow -> [-1,1] via tanh; tuned so a couple of
# meaningful disclosures register without saturating immediately.
_SCALE = 3.0
_HALFLIFE_DAYS = 45.0

# Tickers with no SEC Form-4 insiders: broad ETFs, commodities/futures, FX, crypto.
_NOT_SINGLE_STOCK = frozenset({
    "SPY", "QQQ", "VOO", "IVV", "DIA", "IWM", "VTI", "RSP", "MDY", "GLD", "SLV", "DBC",
    "DBB", "USO", "UNG", "COPX", "XLE", "XLF", "XLK", "GDX", "TLT", "HYG", "LQD", "EEM",
    "EFA", "ARKK", "SOXX", "SMH", "WEAT", "SOYB", "CORN",
})


def _likely_single_stock(ticker: str) -> bool:
    """Heuristic: skip ETFs/funds, crypto (BTC-USD), FX, and futures (=F) — they have no
    SEC insiders, so a Form-4 lookup is always empty."""
    t = (ticker or "").upper()
    if not t or t in _NOT_SINGLE_STOCK:
        return False
    if "-" in t or "=" in t or "." in t or "^" in t:  # BTC-USD, CL=F, BRK.B-ish, ^VIX
        return False
    return True


def _amount_weight(amount: str | None) -> float:
    """Map a disclosure amount band (e.g. '$1,001 - $15,000') to a log-scaled weight."""
    if not amount:
        return 1.0
    # strip thousands separators FIRST, else "$1,001 - $15,000" tokenizes to 1/1/15/0
    # and the largest bands wrongly get the smallest weight (non-monotonic/inverted).
    cleaned = str(amount).replace(",", "")
    nums = []
    cur = ""
    for ch in cleaned:
        if ch.isdigit():
            cur += ch
        elif cur:
            nums.append(int(cur))
            cur = ""
    if cur:
        nums.append(int(cur))
    if not nums:
        return 1.0
    mid = sum(nums) / len(nums)
    # $1k -> ~0.5, $50k -> ~1.0, $1M -> ~1.5 (log10 scaled, clamped)
    return max(0.4, min(2.0, math.log10(max(mid, 10.0)) / 3.0))


def _recency_weight(date_str: str | None, now: datetime) -> float:
    if not date_str:
        return 0.5
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            d = datetime.strptime(str(date_str)[:10], fmt).replace(tzinfo=timezone.utc)
            break
        except ValueError:
            d = None
    if d is None:
        return 0.5
    days = max(0.0, (now - d).total_seconds() / 86400.0)
    return 0.5 ** (days / _HALFLIFE_DAYS)


def score_flows(trades: list[dict], now_iso: str) -> dict[str, dict]:
    """Aggregate disclosed trades into a per-ticker signed score in [-1, 1].

    Returns {ticker: {score, buys, sells, net, actors}}. Pure + deterministic.
    """
    now = datetime.fromisoformat(now_iso)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    buckets: dict[str, dict] = {}
    for t in trades:
        tkr = str(t.get("ticker", "")).upper().strip()
        if not tkr or tkr in ("--", "N/A", "NONE"):
            continue
        typ = str(t.get("type", "")).lower().strip()
        if typ in _BUY:
            sign = 1.0
        elif typ in _SELL:
            sign = -1.0
        elif "purchase" in typ or "buy" in typ:
            sign = 1.0
        elif "sale" in typ or "sell" in typ:
            sign = -1.0
        else:
            continue
        w = _amount_weight(t.get("amount")) * _recency_weight(t.get("date"), now)
        b = buckets.setdefault(tkr, {"net": 0.0, "buys": 0, "sells": 0, "actors": []})
        b["net"] += sign * w
        if sign > 0:
            b["buys"] += 1
        else:
            b["sells"] += 1
        actor = t.get("rep") or t.get("insider") or t.get("filer")
        if actor and actor not in b["actors"]:
            b["actors"].append(str(actor))
    for b in buckets.values():
        b["score"] = max(-1.0, min(1.0, math.tanh(b["net"] / _SCALE)))
    return buckets


class SmartMoneyAgent(BaseAgent):
    name = "SmartMoneyAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 watchlist: list[str] | None = None) -> None:
        super().__init__(bb, router, tools)
        self.watchlist = watchlist or []

    async def run(self, cycle_id: str) -> AgentReport:
        tool_ids: list[str] = []
        signals: dict[str, float] = {}
        findings: list[str] = []
        cites: list[Citation] = []

        # --- reliable spine: SEC Form-4 insider buys/sells across the watchlist ---
        # (free, no key, works in real life — congress dataset below is best-effort.)
        # Target SINGLE STOCKS: ETFs/funds/crypto/commodities have no SEC insiders, so calling
        # insider_transactions on them always returns empty (wasted calls + no signal).
        candidates = [t for t in (self.watchlist or []) if _likely_single_stock(t)][:8]
        for tkr in candidates:
            try:
                ins, irec = await self.tools.call(self.name, "insider_transactions", ticker=tkr, max_filings=10)
                tool_ids.append(irec.id)
            except Exception:
                continue
            if not ins.get("available") or (ins.get("n_buys", 0) == 0 and ins.get("n_sells", 0) == 0):
                continue
            sc = float(ins.get("score", 0.0))
            if abs(sc) < 0.05:
                continue
            signals[tkr] = sc
            who = ", ".join(ins.get("buyers", [])[:2])
            verb = "BUYING" if sc > 0 else "selling"
            findings.append(f"{tkr}: insiders {verb} (score {sc:+.2f}, "
                            f"{ins.get('n_buys',0)} open-mkt buys / {ins.get('n_sells',0)} sales"
                            f"{'; ' + who if who else ''})")
            cites.append(Citation(source=f"https://www.sec.gov (Form 4 insider, {tkr})",
                                  claim=f"{tkr} insider open-market transactions",
                                  verified=True, primary=True, retrieved_at=datetime.now(timezone.utc)))

        # --- best-effort: politician disclosures (degrades cleanly if the feed is down) ---
        congress_ok = False
        try:
            res, rec = await self.tools.call(self.name, "congress_trades", limit=300)
            tool_ids.append(rec.id)
            trades = res.get("trades", []) if isinstance(res, dict) else []
            congress_ok = bool(res.get("available", True)) and bool(trades)
        except Exception:
            trades = []
        if congress_ok:
            cscores = score_flows(trades, datetime.now(timezone.utc).isoformat())
            cranked = sorted(cscores.items(), key=lambda kv: abs(kv[1]["score"]), reverse=True)
            for t, b in cranked:
                if abs(b["score"]) < 0.12:
                    continue
                # blend with insider signal if both present, else add (cap to 12 names)
                signals[t] = max(-1.0, min(1.0, signals.get(t, 0.0) + 0.6 * b["score"]))
                if len([f for f in findings if f.startswith(t + ":")]) == 0 and len(signals) <= 14:
                    direction = "bought" if b["score"] > 0 else "sold"
                    who = ", ".join(b["actors"][:2]) or "disclosed"
                    findings.append(f"{t}: politicians {direction} (score {b['score']:+.2f}; {who})")
            cites.append(Citation(source="US congressional stock disclosures",
                                  claim="politician trade flows", verified=False, primary=False,
                                  retrieved_at=datetime.now(timezone.utc)))
        else:
            findings.append("NOTE: congressional-disclosure feed unavailable this cycle "
                            "(free dataset down) — signal from SEC insider filings only.")

        # rank + emit numeric per-asset signal (the deterministic edge channel)
        ranked = sorted(signals.items(), key=lambda kv: abs(kv[1]), reverse=True)[:12]
        asset_signals = {t: round(s, 4) for t, s in ranked}
        assets = [t for t, _ in ranked]

        net = sum(s for _, s in ranked)
        if net > 0.15:
            stance = "bullish"
        elif net < -0.15:
            stance = "bearish"
        else:
            stance = "neutral"

        if not findings:
            findings = ["No material insider/political flows clustered this cycle."]
        cites.append(Citation(source="SEC EDGAR Form 4 (insider transactions)",
                              claim="aggregated smart-money flows", verified=True, primary=True,
                              retrieved_at=datetime.now(timezone.utc)))

        score = 0.55 if abs(net) > 0.3 else 0.45
        report = self.make_report(
            cycle_id=cycle_id,
            topic="smart money flows",
            summary=(f"Smart-money flows ({len(ranked)} names; SEC insiders"
                     f"{' + politicians' if congress_ok else ''}). Net lean: {stance}. Top: "
                     + (", ".join(f"{t}{s:+.2f}" for t, s in ranked[:5]) or "none")),
            confidence=Confidence(score=score, low=max(0.0, score - 0.15), high=min(1.0, score + 0.15),
                                  rationale="disclosed flows are lagged leads, not certainties"),
            stance=stance,
            assets=assets,
            asset_signals=asset_signals,
            findings=findings[:15],
            citations=cites,
            tool_calls=tool_ids,
        )
        self.bb.write_report(report)
        self.log.info("smartmoney_done", n_names=len(ranked), stance=stance, congress=congress_ok)
        return report
