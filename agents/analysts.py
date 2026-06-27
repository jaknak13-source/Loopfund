"""Concrete LLM analyst agents. Each gathers a different slice of free data and
produces a structured report. Honest about coverage gaps (esp. alt-data, where
free sources are thin).
"""

from __future__ import annotations

from agents.analyst import LLMAnalystAgent


def _fmt_articles(arts: list[dict], limit: int = 25) -> tuple[str, list[dict]]:
    lines, cites = [], []
    for a in arts[:limit]:
        t = a.get("title", "")
        if not t:
            continue
        lines.append(f"- {t}")
        cites.append({"source": a.get("link") or a.get("source", ""), "claim": t,
                      "verified": False, "primary": False})
    return "\n".join(lines), cites


class MacroAgent(LLMAnalystAgent):
    name = "MacroAgent"
    topic = "macro regime"
    trusted_data = True  # rates/vol/FX/commodity series are first-party market data, not web text
    role_system = (
        "You are the MacroAgent. Track rates, inflation, growth, FX, commodities, "
        "and geopolitics. Build a regime view and name the dominant macro risk. "
        "Trace indirect impact chains (e.g. weather -> commodity -> input cost -> sector)."
    )

    async def gather(self, cycle_id):
        tool_ids, ctx, cites = [], [], []
        snap, rec = await self.tools.call(self.name, "macro_snapshot")
        tool_ids.append(rec.id)
        if snap.get("available", True):
            ctx.append(f"Macro series (latest, source={snap.get('source', 'fred')}):\n" + "\n".join(
                f"- {k}: {v}" for k, v in (snap.get("series") or {}).items() if v is not None))
            if snap.get("tilt"):
                ctx.append(f"Macro tilt (21d): {snap['tilt']}")
            if snap.get("yield_curve"):
                yc = snap["yield_curve"]
                ctx.append(f"Yield curve (COMPUTED, use this label — do not re-derive): "
                           f"{yc['label']}, spread {yc['spread_pp']}pp (10y {yc['long_10y']} "
                           f"vs short {yc['short_5y']}).")
            cites.append({"source": f"market data macro proxies ({snap.get('source','')})",
                          "claim": "rates/vol/dollar/commodity levels and 21d changes",
                          "verified": True, "primary": False})
        else:
            ctx.append("Macro series: UNAVAILABLE — rely on news, flag low confidence.")
        try:
            geo, rec2 = await self.tools.call(self.name, "gdelt_search",
                                              query="central bank OR sanctions OR war OR tariffs OR election",
                                              max_records=12)
            tool_ids.append(rec2.id)
            txt, c = _fmt_articles(geo.get("articles", []))
            ctx.append("Geopolitical/policy headlines:\n" + txt)
            cites += c
        except Exception:
            pass
        return "\n\n".join(ctx), tool_ids, cites


class FundamentalsAgent(LLMAnalystAgent):
    name = "FundamentalsAgent"
    topic = "fundamentals"
    trusted_data = True  # SEC XBRL + exchange market metrics are first-party, verified data
    role_system = (
        "You are the FundamentalsAgent. Judge valuation, growth, margins, leverage, "
        "and quality from the figures given. Distinguish cheap-for-a-reason from "
        "genuinely mispriced. Do not invent numbers you were not given."
    )

    async def gather(self, cycle_id):
        tool_ids, ctx, cites = [], [], []
        for tkr in self.watchlist[:6]:
            res, rec = await self.tools.call(self.name, "fundamentals", ticker=tkr)
            tool_ids.append(rec.id)
            f = res.get("fundamentals") or {}
            line = (f"{tkr}: " + ", ".join(f"{k}={v}" for k, v in f.items() if v is not None)
                    if f else f"{tkr}: market fundamentals unavailable")
            if f:  # market data = a credible (secondary) source
                cites.append({"source": f"market data ({tkr})", "claim": f"{tkr} valuation/metrics",
                              "verified": True, "primary": False})
            # real SEC XBRL financials (US filers) — actual filing data = PRIMARY, verified
            try:
                sec, recs = await self.tools.call(self.name, "sec_financials", ticker=tkr)
                tool_ids.append(recs.id)
                sf = sec.get("financials") or {}
                if sf:
                    keep = {k: sf[k] for k in ("revenue", "net_margin", "operating_margin",
                                               "revenue_yoy", "debt_to_equity", "eps_diluted")
                            if sf.get(k) is not None}
                    if keep:
                        line += " | SEC: " + ", ".join(f"{k}={v}" for k, v in keep.items())
                        cites.append({"source": f"SEC EDGAR XBRL CIK {sec.get('cik')} ({tkr})",
                                      "claim": f"{tkr} audited financials", "verified": True, "primary": True})
            except Exception:
                pass
            ctx.append(line)
        return "Fundamentals snapshot (market + SEC XBRL filings):\n" + "\n".join(ctx), tool_ids, cites


class SentimentAgent(LLMAnalystAgent):
    name = "SentimentAgent"
    topic = "sentiment"
    role_system = (
        "You are the SentimentAgent. Read crowd/social sentiment and flag "
        "manipulation or hype risk. Social posts are LEADS, never evidence. "
        "Estimate whether sentiment confirms or contradicts fundamentals."
    )

    async def gather(self, cycle_id):
        tool_ids, ctx, cites = [], [], []
        self._asset_signals = {}  # deterministic per-ticker social tilt (a small LEAD)
        for sub in ("investing", "wallstreetbets"):
            res, rec = await self.tools.call(self.name, "reddit_hot", subreddit=sub, limit=10)
            tool_ids.append(rec.id)
            if res.get("available", True):
                titles = [p.get("title", "") for p in res.get("posts", [])]
                ctx.append(f"r/{sub} hot:\n" + "\n".join(f"- {t}" for t in titles if t))
            else:
                ctx.append(f"r/{sub}: unavailable ({res.get('reason')})")
        for tkr in self.watchlist[:5]:
            res, rec = await self.tools.call(self.name, "stocktwits_symbol", symbol=tkr, limit=15)
            tool_ids.append(rec.id)
            msgs = res.get("messages", [])
            if msgs:
                bull = sum(1 for m in msgs if m.get("sentiment") == "Bullish")
                bear = sum(1 for m in msgs if m.get("sentiment") == "Bearish")
                tot = bull + bear
                if tot >= 3:  # need a minimum sample to be meaningful
                    # signed net, scaled small (±0.3 max) — sentiment is a LEAD, not evidence
                    net = round(0.3 * (bull - bear) / tot, 3)
                    self._asset_signals[tkr.upper()] = net
                    ctx.append(f"StockTwits {tkr}: {bull} bullish / {bear} bearish of {len(msgs)} "
                               f"(net social tilt {net:+.2f}, treat as a small lead)")
        return "\n\n".join(ctx), tool_ids, cites


class IpoMnaAgent(LLMAnalystAgent):
    name = "IpoMnaAgent"
    topic = "ipo and m&a"
    role_system = (
        "You are the IPO & M&A agent. Spot upcoming IPOs, SPACs, S-1 filings, and "
        "merger/acquisition activity, and where PE/strategics are moving. Treat "
        "rumors as unverified until a filing or official release confirms them."
    )

    async def gather(self, cycle_id):
        tool_ids, ctx, cites = [], [], []
        try:
            res, rec = await self.tools.call(self.name, "gdelt_search",
                                             query="IPO OR S-1 filing OR merger OR acquisition OR buyout OR SPAC",
                                             max_records=15)
            tool_ids.append(rec.id)
            txt, c = _fmt_articles(res.get("articles", []))
            ctx.append("Deal/IPO headlines:\n" + txt)
            cites += c
        except Exception:
            ctx.append("Deal headlines unavailable.")
        for tkr in self.watchlist[:4]:
            res, rec = await self.tools.call(self.name, "recent_filings", ticker=tkr, limit=5)
            tool_ids.append(rec.id)
            fl = res.get("filings", [])
            if fl:
                ctx.append(f"{tkr} recent SEC filings: " + ", ".join(f"{x['form']}({x['date']})" for x in fl))
        return "\n\n".join(ctx), tool_ids, cites


class AltDataAgent(LLMAnalystAgent):
    name = "AltDataAgent"
    topic = "alternative data"
    role_system = (
        "You are the AltDataAgent. Use non-traditional signals (hiring, patents, "
        "shipping, web/app trends) where free data exists. BE HONEST about coverage "
        "gaps: most alt-data needs paid feeds. Do not fabricate datasets you lack."
    )

    async def gather(self, cycle_id):
        tool_ids, ctx, cites = [], [], []
        for q in ("hiring layoffs job postings tech", "patent filing semiconductor AI", "shipping container port volume"):
            try:
                res, rec = await self.tools.call(self.name, "gdelt_search", query=q, max_records=8)
                tool_ids.append(rec.id)
                txt, c = _fmt_articles(res.get("articles", []), limit=8)
                if txt:
                    ctx.append(f"[{q}]\n{txt}")
                    cites += c
            except Exception:
                continue
        ctx.append("NOTE: free alt-data coverage is thin (no satellite/web-traffic feeds). "
                   "Treat these as weak proxies only.")
        return "\n\n".join(ctx), tool_ids, cites
