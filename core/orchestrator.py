"""The loop engine. One `run_cycle` does the full pipeline:
research/macro/fundamentals/sentiment/ipo/altdata/quant -> RiskAgent ->
DecisionAgent debate -> (cooldown-gated) dry execution -> mark-to-market ->
learning. Agent failures are logged and skipped, never fatal.

Cooldown: portfolio changes happen at most once per `decision.interval_hours`.
Human instructions are read each cycle and override default behavior.
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from agents.analysts import (
    AltDataAgent,
    FundamentalsAgent,
    IpoMnaAgent,
    MacroAgent,
    SentimentAgent,
)
from agents.briefing_loader import build_dynamic_agents
from agents.decision import DecisionAgent
from agents.memory_auditor import MemoryAuditorAgent
from agents.meta import MetaAgent
from agents.memory_agent import MemoryAgent
from agents.council import CouncilAgent
from agents.quant import QuantAgent
from agents.smartmoney import SmartMoneyAgent
from agents.quant_research import QuantResearchAgent
from agents.research import ResearchAgent
from agents.risk import RiskAgent
from core.backup import maybe_daily_backup
from core.blackboard import Blackboard
from core.config import data_dir, settings
from core.resilience import record_error
from core.watchlist import sample_watchlist
from config.universe import full_universe
from core.instructions import NO_TRADE, directive_text, parse_intent
from core.logging import get_logger
from execution.dry import DryExecution
from execution.risk_governor import (
    DERISK,
    assess,
    allow_buy,
    non_core_positions,
    stop_loss_hits,
    update_marks,
)
from execution.sim_ledger import SimLedger
from memory.learning import LearningStore
from memory.rag import RagMemory
from models_adapter.router import ModelRouter
from schemas import Confidence, PortfolioDecision, TradeAction
from tools.registry import ToolRegistry

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(
        self,
        *,
        blackboard: Blackboard,
        router: ModelRouter,
        data_tools: ToolRegistry,
        rag: RagMemory,
        ledger: SimLedger,
        watchlist: list[str] | None = None,
        state_path: Path | None = None,
        priors: dict[str, float] | None = None,
        execution=None,
        learning_path: Path | None = None,
    ) -> None:
        self.bb = blackboard
        self.router = router
        self.tools = data_tools
        self.rag = rag
        self.ledger = ledger
        self.watchlist = watchlist or ["SPY", "NVDA", "AAPL", "MSFT", "XOM"]
        self.state_path = state_path or (data_dir() / "state.json")
        self.memory = MemoryAgent(rag)
        self.execution = execution or DryExecution(data_tools, ledger)
        self.learning = LearningStore(path=learning_path)
        self.benchmark_symbol = "SPY"
        # float so short test runs can mature observations sub-day (e.g. 0.05 ~ 1.2h)
        self.horizon_days = float(settings().get("learning", {}).get("horizon_days", 5))

        wl = self.watchlist
        self.research = ResearchAgent(blackboard, router, data_tools, self.memory, wl)
        self.macro = MacroAgent(blackboard, router, data_tools, self.memory, wl)
        self.fundamentals = FundamentalsAgent(blackboard, router, data_tools, self.memory, wl)
        self.sentiment = SentimentAgent(blackboard, router, data_tools, self.memory, wl)
        self.ipo = IpoMnaAgent(blackboard, router, data_tools, self.memory, wl)
        self.altdata = AltDataAgent(blackboard, router, data_tools, self.memory, wl)
        self.quant = QuantAgent(blackboard, router, data_tools, watchlist=wl)
        self.smartmoney = SmartMoneyAgent(blackboard, router, data_tools, wl)
        self.risk = RiskAgent(blackboard, router, data_tools, self.memory, wl)
        self.quant_research = QuantResearchAgent(blackboard, router, data_tools, self.memory, wl)
        self.meta = MetaAgent(blackboard, router, data_tools, self.memory)
        self.council = CouncilAgent(blackboard, router, data_tools, self.memory)
        self.memory_auditor = MemoryAuditorAgent(blackboard, router, data_tools, self.memory)
        self.decision = DecisionAgent(blackboard, router, data_tools, self.memory, self.risk, priors)

        # apply previously learned knowledge
        learned = self.learning.priors()
        if learned:
            self.decision.priors = learned
        self.research.source_guidance = self.learning.source_guidance_text()

        self._state = self._load_state()

    # --- state ---
    def _load_state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"last_trade_iso": None, "scored_decision_ids": [], "marks": {}}

    def _save_state(self) -> None:
        self.state_path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")

    def _decision_cfg(self) -> dict:
        return settings().get("decision", {})

    def can_trade_now(self) -> bool:
        """Min time between actual portfolio CHANGES (the trade cooldown). Long for real
        management (24h-3d); falls back to interval_hours if not set separately."""
        last = self._state.get("last_trade_iso")
        if not last:
            return True
        d = self._decision_cfg()
        hours = float(d.get("trade_cooldown_hours", d.get("interval_hours", 24)))
        return datetime.now(timezone.utc) >= datetime.fromisoformat(last) + timedelta(hours=hours)

    # --- human instructions ---
    def active_intents(self) -> list[str]:
        intents = []
        for instr in self.bb.active_instructions():
            intent = instr.parsed_intent or parse_intent(instr.text)
            if intent:
                intents.append(intent)
        return intents

    # --- portfolio summary ---
    async def _position_prices(self, extra: tuple[str, ...] = ()) -> dict[str, float]:
        prices: dict[str, float] = {}
        for a in list(self.ledger.p.positions) + list(extra):
            if a in prices:
                continue
            p = await self._price_eur(a)
            if p is not None:
                prices[a] = p
        return prices

    async def portfolio_snapshot(self) -> dict:
        return self.ledger.mark_to_market(await self._position_prices())

    async def _portfolio_summary_text(self) -> str:
        """Portfolio in EUR (base ccy). Each holding shows entry vs CURRENT price in BOTH
        EUR and native currency + an as-of timestamp, so values are never mistaken for the
        wrong currency or treated as stale. ALL EUR figures are base-currency, not USD."""
        snap = await self.portfolio_snapshot()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        total = snap["total_value_eur"] or 1.0
        lines = []
        for a, p in self.ledger.p.positions.items():
            try:
                q = await self.execution._quote(a)  # (price_eur, native, ccy, fx)
            except Exception:
                q = None
            # holding age + fees paid so agents avoid fee-wasting churn (buy then trim fast)
            held_h = self._hours_since_last_buy(a)
            age_txt = (f"held {held_h/24:.1f}d" if held_h and held_h >= 24
                       else f"held {held_h:.1f}h" if held_h is not None else "held ?")
            fees = sum(t.fees_eur for t in self.bb.trades_for_asset(a))
            if q:
                px_eur, native, ccy, _ = q
                val = px_eur * p.qty
                wt = 100.0 * val / total
                pnl = (px_eur - p.avg_cost_eur) * p.qty
                # explicitly LONG with a SIGNED PnL so agents never infer 'short' or the
                # wrong direction (the portfolio is long-only; the sim cannot hold shorts).
                lines.append(f"LONG {a}: {wt:.1f}% of portfolio | {p.qty:.4f}sh €{val:.0f} | "
                             f"entry €{p.avg_cost_eur:.2f} -> NOW €{px_eur:.2f} (={native:.2f} {ccy}) | "
                             f"uPnL {pnl:+.2f} EUR ({'up' if pnl >= 0 else 'down'}) | "
                             f"{age_txt}, fees €{fees:.2f} paid (selling now re-pays a fee)")
            else:
                lines.append(f"LONG {a}: {p.qty:.4f}sh | entry €{p.avg_cost_eur:.2f} | current price unavailable")
        pos = "\n  ".join(lines) or "none (100% cash)"
        cash_pct = 100.0 * snap["cash_eur"] / total
        invested_pct = 100.0 - cash_pct
        return (f"[CURRENCY=EUR base. Prices as of {now}. EUR figures are NOT USD. The fund is "
                f"LONG-ONLY — every position below is a LONG; there are NO short positions.]\n"
                f"total=€{snap['total_value_eur']} | cash €{snap['cash_eur']} ({cash_pct:.1f}%) | "
                f"invested {invested_pct:.1f}% | realized {snap['realized_pnl_eur']:+} EUR | "
                f"unrealized {snap['unrealized_pnl_eur']:+} EUR\n"
                f"positions (all LONG, % of total):\n  {pos}")

    # --- passive core allocation ---
    async def _maybe_baseline(self) -> "object | None":
        """Deploy idle cash gradually toward a diversified ETF core so the fund
        stays invested like a basic PM. One step per cycle, respects risk caps."""
        cfg = settings().get("portfolio", {}).get("baseline", {})
        if not cfg.get("enabled"):
            return None
        weights = cfg.get("weights") or {}
        if not weights:
            return None
        step = float(cfg.get("deploy_step", 0.10))

        assets = set(self.ledger.p.positions) | set(weights)
        prices = await self.execution._prices_eur(assets)
        total = self.ledger.p.total_value(prices)
        if total <= 0:
            return None
        cur = self.ledger.p.weights(prices)
        gaps = {a: weights[a] - cur.get(a, 0.0) for a in weights if a in prices}
        if not gaps:
            return None
        target_asset = max(gaps, key=lambda k: gaps[k])
        if gaps[target_asset] < 0.02:  # core already built
            return None

        deploy_to = min(weights[target_asset], cur.get(target_asset, 0.0) + step)
        decision = PortfolioDecision(
            id=str(uuid.uuid4()), decision_date=date.today(), action=TradeAction.ADD,
            asset=target_asset, target_weight=deploy_to,
            reasoning=f"Passive core allocation: deploy idle cash toward {target_asset} "
                      f"(target {weights[target_asset]:.0%}, current {cur.get(target_asset, 0.0):.0%}).",
            key_assumptions=["diversified core reduces cash drag vs SP500"],
            known_risks=["beta exposure to a market drawdown"],
            confidence=Confidence(score=0.5, low=0.45, high=0.55, rationale="passive diversified core"),
            mode=settings().get("mode", "dry"),
        )
        trade = await self.execution.execute(decision)
        if trade and trade.status in ("filled", "closed"):
            self.bb.write_decision(decision)
            log.info("baseline_deploy", asset=target_asset, to_weight=deploy_to)
        return trade

    # --- learning ---
    async def _price_eur(self, asset: str) -> float | None:
        try:
            q = await self.execution._quote(asset)
            return q[0] if q else None
        except Exception:
            return None

    async def _learn(self, cycle_id: str, total_value_eur: float) -> dict:
        # 1. resolve matured observations -> update agent + source trust
        matured = self.learning.matured_assets(self.horizon_days)
        prices = {a: p for a in matured if (p := await self._price_eur(a)) is not None}
        res = self.learning.resolve(prices, self.horizon_days)
        for r in res["details"]:
            if not r["hit"]:
                self.memory.write_lesson(
                    title=f"{r['agent']} {r['stance']} on {r['asset']} was wrong",
                    body=(f"{r['agent']} was {r['stance']} on {r['asset']}; {self.horizon_days}d "
                          f"forward return {r['fwd_return']:.2%}. Sources: {r['sources']}."),
                    assets=[r["asset"]], outcome="incorrect")

        # refresh learned priors + source guidance for subsequent cycles
        learned = self.learning.priors()
        if learned:
            self.decision.priors = learned
        self.research.source_guidance = self.learning.source_guidance_text()

        # 2. SP500 benchmark
        spy = await self._price_eur(self.benchmark_symbol)
        self.learning.ensure_inception(spy, total_value_eur)
        bench = self.learning.benchmark(spy, total_value_eur)

        # 3. record this cycle's directional observations (for future maturity)
        entry_cache: dict[str, float | None] = {}
        for rep in self.bb.reports_for_cycle(cycle_id):
            if rep.stance not in ("bullish", "bearish"):
                continue
            sources = [c.source for c in rep.citations]
            for a in rep.assets[:5]:
                if a not in entry_cache:
                    entry_cache[a] = await self._price_eur(a)
                if entry_cache[a] is not None:
                    self.learning.add_observation(rep.agent, a, rep.stance, sources, entry_cache[a])

        # 4. weekly simulated top-up (your ~100 EUR/week)
        topup = self.learning.maybe_weekly_topup(
            float(settings().get("portfolio", {}).get("weekly_topup", 0.0)))
        if topup > 0:
            self.ledger.p.cash_eur += topup
            if self.ledger.store:
                self.ledger.store.save(self.ledger.p)
            # record the contribution so the benchmark stays honest: injected cash
            # raises the invested base AND buys notional SPY, never counts as a return.
            self.learning.record_contribution(topup, spy)

        self.learning.save()
        return {"resolved": res["resolved"], "benchmark": bench, "topup_eur": topup,
                "metrics": self.learning.metrics_snapshot()}

    # --- idle deep research ---
    async def deep_research(self) -> dict:
        """Run during idle periods: backtest a momentum signal on each watchlist
        asset and store a summary in memory. Cheap, deterministic, no LLM."""
        import uuid as _uuid
        from datetime import datetime as _dt, timezone as _tz

        from quant import backtest, factors
        from schemas import MemoryEntry

        results: dict[str, dict] = {}
        for tkr in self.watchlist:
            try:
                hist, _ = await self.tools.call("Orchestrator", "history", ticker=tkr, period="2y")
            except Exception:
                continue
            closes = [b["close"] for b in hist.get("bars", [])]
            if len(closes) < 150:
                continue
            sig = [1.0 if (factors.momentum(closes[: i + 1]) or 0) > 0 else 0.0
                   for i in range(len(closes))]
            results[tkr] = backtest.backtest_signal(closes, sig)

        summary = "; ".join(
            f"{t}: ret={r.get('total_return', 0):.2%} sharpe={r.get('sharpe', 0):.2f}"
            for t, r in results.items()
        ) or "no backtests produced"
        self.memory.rag.add(MemoryEntry(
            id=str(_uuid.uuid4()), created_at=_dt.now(_tz.utc), kind="model_output",
            title="Idle deep-research: momentum backtests", body=summary,
            tags=["backtest", "idle"]))

        # self-taught research: the agent writes + runs its own method (best-effort)
        invented = {}
        try:
            invented = await self.quant_research.research()
        except Exception as exc:
            log.error("quant_research_failed", error=f"{type(exc).__name__}: {exc}")

        # self-improvement: MetaAgent may author a new specialist agent (best-effort)
        meta_result = {}
        try:
            meta_result = await self.meta.improve()
        except Exception as exc:
            log.error("meta_improve_failed", error=f"{type(exc).__name__}: {exc}")

        # self-improvement: MetaAgent may codify a proven pattern into a reusable skill
        skill_result = {}
        try:
            skill_result = await self.meta.author_skill()
        except Exception as exc:
            log.error("meta_skill_failed", error=f"{type(exc).__name__}: {exc}")

        log.info("deep_research_done", n=len(results), invented=invented.get("ok"),
                 new_agent=meta_result.get("name"), new_skill=skill_result.get("name"))
        return {"backtests": results, "summary": summary, "invented_method": invented,
                "meta": meta_result, "skill": skill_result}

    # --- protective selling (risk governor) ---
    async def _sell_full(self, tag: str, asset: str) -> object | None:
        pos = self.ledger.p.positions.get(asset)
        if not pos:
            return None
        q = await self.execution._quote(asset)
        if not q:
            return None
        _eur, native, ccy, fx = q
        return self.ledger.sell(tag, asset, pos.qty, native, ccy, fx)

    async def _apply_stop_losses(self, prices: dict[str, float]) -> list:
        trades = []
        for a in stop_loss_hits(self.ledger.p, prices):
            t = await self._sell_full(f"stoploss-{a}", a)
            if t and t.status in ("filled", "closed"):
                trades.append(t)
                self.memory.write_lesson(
                    title=f"Stop loss hit on {a}",
                    body=f"{a} fell past the stop-loss threshold from entry; position exited to cap loss.",
                    assets=[a], outcome="incorrect")
                log.info("stop_loss_exit", asset=a)
        return trades

    async def _derisk(self) -> list:
        trades = []
        for a in non_core_positions(self.ledger.p):
            t = await self._sell_full(f"derisk-{a}", a)
            if t and t.status in ("filled", "closed"):
                trades.append(t)
                log.info("derisk_exit", asset=a)
        return trades

    # --- continuous research (runs between decision cycles so the LLM never idles) ---
    _RESEARCH_THEMES = [
        "macro regime, rates, inflation, FX, yield curve shifts",
        "geopolitics, sanctions, export controls, elections, policy",
        "energy & commodities: oil/gas, nuclear/uranium, metals, grids",
        "AI/semis/datacenter capex and the memory/component supply chain",
        "M&A, IPOs, SPACs, PE exits, 13F/insider/Congress flows",
        "social sentiment, retail/meme flows, narrative momentum",
        "undervalued / overlooked small & mid caps with catalysts",
        "crypto market structure, ETF flows, on-chain, halving cycles",
    ]

    async def _llm(self, system: str, user: str, profile: str = "default") -> str:
        from core.preamble import system_preamble
        from models_adapter.base import Message
        return await self.router.complete(
            "ResearchLoop", [Message("system", f"{system_preamble()}\n\n{system}"),
                             Message("user", user)], profile=profile)

    def _save_research(self, title: str, body: str, assets: list[str], kind: str = "research") -> None:
        import uuid as _u
        from datetime import datetime as _dt, timezone as _tz
        from schemas import MemoryEntry
        self.memory.rag.add(MemoryEntry(
            id=str(_u.uuid4()), created_at=_dt.now(_tz.utc), kind=kind,
            title=title[:120], body=body[:4000], assets=assets[:6], tags=["research-loop"]))
        self._emit("research", "ResearchLoop", title, body, assets=assets[:6])

    async def _gather(self, tool: str, **kw) -> str:
        try:
            r, _ = await self.tools.call("ResearchLoop", tool, _log=False, **kw)
            return f"{tool}: {str(r)[:700]}"
        except Exception as exc:
            return f"{tool}: unavailable ({type(exc).__name__})"

    async def research_task(self, idx: int) -> dict:
        """One focused deep-research unit. Rotates task type so over time the fund
        continuously deep-dives stocks, scans for undervaluation, invents quant
        methods, and researches themes/sentiment — saving findings to memory for
        future decisions. Never idles."""
        from core.sanitize import wrap_untrusted
        kind = idx % 5
        try:
            if kind == 0:  # single-stock deep dive
                uni = full_universe()
                # separate cursor incremented only on a deep dive, so it WALKS the whole
                # universe (incl small/mid caps) instead of re-diving the same ~11 names
                # (the old idx%len collided because idx was always a multiple of 5 here).
                cur = int(self._state.get("deep_dive_cursor", 0))
                tkr = uni[cur % len(uni)]
                self._state["deep_dive_cursor"] = cur + 1
                self._save_state()
                data = [await self._gather(t, ticker=tkr) for t in
                        ("price", "sec_financials", "estimate_fair_value", "recent_filings")]
                data.append(await self._gather("web_research",
                            query=f"{tkr} stock latest news catalyst guidance valuation", pages=3))
                note = await self._llm(
                    "You are a deep-dive equity analyst. From the data, write a concise sourced "
                    "deep-dive: business, financials, valuation vs fair value, catalysts, risks, "
                    "and a watch/buy/avoid lean. Flag anything unverified.",
                    f"Deep dive {tkr}:\n{wrap_untrusted(chr(10).join(data), tkr)}")
                self._save_research(f"Deep dive: {tkr}", note, [tkr])
                return {"task": "deep_dive", "ticker": tkr}

            if kind == 1:  # undervaluation scan over a batch
                uni = full_universe()
                batch = [uni[(idx * 5 + i) % len(uni)] for i in range(5)]
                fv = [await self._gather("estimate_fair_value", ticker=t) for t in batch]
                note = await self._llm(
                    "You scan for undervaluation. Given fair-value estimates, name the most "
                    "undervalued candidates (largest upside with sane assumptions) and why; "
                    "flag any with fragile inputs.",
                    f"Fair-value batch:\n{chr(10).join(fv)}")
                self._save_research(f"Undervaluation scan {batch}", note, batch)
                return {"task": "undervalued_scan", "batch": batch}

            if kind == 2:  # theme / trend research
                theme = self._RESEARCH_THEMES[idx % len(self._RESEARCH_THEMES)]
                wr = await self._gather("web_research", query=theme + " latest developments investing", pages=4)
                gd = await self._gather("gdelt_search", query=theme.split(",")[0], max_records=10)
                note = await self._llm(
                    "You research market themes. Summarize what's developing in this theme, the "
                    "shift/trend, who benefits (specific tickers, incl. non-obvious), and timing. "
                    "Trace second-order effects. Flag unverified.",
                    f"Theme: {theme}\n{wrap_untrusted(wr + chr(10) + gd, 'theme')}")
                self._save_research(f"Theme research: {theme[:50]}", note, [])
                return {"task": "theme", "theme": theme}

            if kind == 3:  # invent/test a quant method (self-coding)
                res = await self.quant_research.research()
                return {"task": "quant_method", "ok": res.get("ok")}

            # kind == 4: smart-money + sentiment scan
            cg = await self._gather("congress_trades", limit=25)
            pm = await self._gather("polymarket_markets", limit=10)
            rd = await self._gather("reddit_hot", subreddit="wallstreetbets", limit=12)
            note = await self._llm(
                "You track smart money + crowd sentiment. From Congress trades, prediction "
                "markets, and social, flag notable positioning, divergences (sentiment vs "
                "reality), and names worth verifying. Treat all as LEADS, never proof.",
                f"{wrap_untrusted(cg + chr(10) + pm + chr(10) + rd, 'signals')}")
            self._save_research("Smart-money & sentiment scan", note, [])
            return {"task": "smart_money"}
        except Exception as exc:
            log.error("research_task_failed", idx=idx, error=f"{type(exc).__name__}: {exc}")
            return {"task": "error", "error": str(exc)}

    def _reminder_hours(self) -> float:
        d = self._decision_cfg()
        return float(d.get("reminder_hours", d.get("trade_cooldown_hours", d.get("interval_hours", 24))))

    def decision_due(self) -> bool:
        """A REMINDER fires every reminder_hours/2 (the soft 'come to conclusions' nudge);
        every other one is a full 'you may trade' reminder. It's only a reminder — the
        agents may decide NO_ACTION freely; nothing is forced. Research runs between.

        Back-off: after consecutive NO_ACTION decisions the gap stretches (up to a cap), so
        when the fund is unsure it keeps RESEARCHING instead of re-deciding every interval."""
        last = self._state.get("last_decision_iso")
        if not last:
            return True
        base = self._reminder_hours() / 2
        cap = float(self._decision_cfg().get("no_action_backoff_max", 4))
        backoff = 1.0 + min(int(self._state.get("consecutive_no_action", 0)), int(cap))
        return datetime.now(timezone.utc) >= datetime.fromisoformat(last) + timedelta(hours=base * backoff)

    def _cash_discipline_note(self, invested_pct: float) -> str:
        """Gentle, graduated nudge against PERSISTENT idle cash (inflation drag) — never
        forces a trade; rationality and good analysis always come first."""
        if invested_pct >= 55:
            return ""  # well invested — nothing to nudge
        if invested_pct >= 35:
            return ("\nCAPITAL NOTE: ~{:.0f}% invested. Idle cash loses to inflation over time — "
                    "when a well-analyzed, rational opportunity exists, prefer deploying over "
                    "holding cash. Still: only with genuine conviction, never a forced trade.").format(invested_pct)
        return ("\nCAPITAL NOTE: only ~{:.0f}% invested — sitting on a lot of cash. Persistent idle "
                "cash steadily loses to inflation, so actively HUNT for rational, well-researched "
                "opportunities to deploy (diversified, small/quality positions and a small hedge are "
                "fine, within limits). Stay heavily in cash ONLY during genuine uncertainty/crash "
                "risk. Do NOT force a bad trade — but do not let capital sit idle indefinitely "
                "either.").format(invested_pct)

    def _reminder_directive(self) -> str:
        """Full trade-opportunity reminder every reminder_hours; interim conclusion
        checkpoint on the half-beats. Both may execute if confident."""
        last_full = self._state.get("last_full_reminder_iso")
        now = datetime.now(timezone.utc)
        is_full = (not last_full) or now >= datetime.fromisoformat(last_full) + timedelta(hours=self._reminder_hours())
        if is_full:
            self._state["last_full_reminder_iso"] = now.isoformat()
            return ("TRADE-OPPORTUNITY REMINDER: you MAY open/trim/rotate positions now. Act "
                    "only with genuine conviction; NO_ACTION is perfectly fine if not ready.")
        return ("INTERIM CHECKPOINT: update and record your conclusions/theses. You do NOT "
                "need to trade — but you MAY execute directly if a clear high-conviction "
                "opportunity exists right now. Otherwise NO_ACTION and keep researching.")

    # --- activity feed (Mind tab) ---
    def _emit(self, kind: str, agent: str, title: str, summary: str = "",
              cycle_id: str = "", **meta) -> None:
        """Append one activity event. Best-effort: never let observability break a cycle."""
        try:
            from schemas import ActivityEvent
            self.bb.write_activity(ActivityEvent(
                id=uuid.uuid4().hex, ts=datetime.now(timezone.utc), cycle_id=cycle_id,
                agent=agent, kind=kind, title=title[:160], summary=summary[:600], meta=meta))
        except Exception:
            pass

    def _peer_digest(self, cycle_id: str, limit: int = 16) -> str:
        """Compact summary of what agents have ALREADY reported this cycle, fed to the next
        agent so each one builds on / challenges peers instead of working blind."""
        rows = []
        for r in self.bb.reports_for_cycle(cycle_id)[:limit]:
            sig = ""
            if r.asset_signals:
                sig = " sig=" + ",".join(f"{a}{v:+.2f}" for a, v in list(r.asset_signals.items())[:3])
            key = ("; ".join(r.findings[:1]) if r.findings else "")
            rows.append(f"[{r.agent}] {r.stance} ({r.confidence.score:.2f}) "
                        f"{(r.summary or '')[:160]}{sig}" + (f" | {key}" if key else ""))
        return "\n".join(rows)

    # --- anti-churn + multi-buy helpers ---
    def _hours_since_last_buy(self, asset: str) -> float | None:
        """Hours since the most recent BUY of this asset (None if never bought)."""
        buys = [t for t in self.bb.trades_for_asset(asset) if t.side == "buy"]
        if not buys:
            return None
        last = max(buys, key=lambda t: t.placed_at).placed_at
        return (datetime.now(timezone.utc) - last).total_seconds() / 3600.0

    def _churn_blocked(self, asset: str) -> bool:
        """True if trimming/selling `asset` now would be churn: bought within the
        min-hold window (fees on both legs). Stop-loss / de-risk paths bypass this."""
        min_hold = float(settings().get("decision", {}).get("min_hold_hours", 24))
        if min_hold <= 0:
            return False
        held = self._hours_since_last_buy(asset)
        return held is not None and held < min_hold

    async def _execute_additional_buys(self, primary, risk_state, cycle_id) -> None:
        """Open each validated extra high-conviction buy (risk-checked like the primary)."""
        for ab in primary.additional_buys:
            asset = str(ab.get("asset", "")).upper()
            if not asset or not allow_buy(asset, risk_state):
                continue
            sub = PortfolioDecision(
                id=str(uuid.uuid4()), decision_date=date.today(), created_at=datetime.now(timezone.utc),
                action=TradeAction.BUY, asset=asset,
                target_weight=float(ab.get("target_weight") or 0.05),
                reasoning=f"[multi-buy] {ab.get('reasoning', '')}"[:2000],
                key_assumptions=["high-conviction co-buy this cycle"],
                known_risks=["sized within caps; corroboration-checked"],
                confidence=primary.confidence,
                contributing_reports=primary.contributing_reports,
                mode=primary.mode, block_reason="traded",
            )
            try:
                t = await self.execution.execute(sub)
                if t:
                    self.bb.write_decision(sub)
                    log.info("multi_buy_executed", asset=asset, weight=sub.target_weight)
            except Exception as exc:
                log.error("multi_buy_failed", asset=asset, error=f"{type(exc).__name__}: {exc}")

    # --- the cycle ---
    async def run_cycle(self, cycle_id: str | None = None) -> dict:
        cycle_id = cycle_id or f"cycle-{uuid.uuid4().hex[:8]}"
        from core.cost import cost_meter
        _cost_start = cost_meter().snapshot()["total_usd"]
        intents = self.active_intents()
        directive = directive_text(intents)
        no_trade = NO_TRADE in intents

        # risk assessment up front (drawdown brake) — informs the decision + gates trades
        today = datetime.now(timezone.utc).date().isoformat()
        pre_prices = await self._position_prices()
        pre_total = self.ledger.p.total_value(pre_prices)
        marks = self._state.setdefault("marks", {})
        update_marks(marks, pre_total, today)
        risk = assess(pre_total, marks)
        self._state["last_decision_iso"] = datetime.now(timezone.utc).isoformat()
        self._save_state()
        invested_pct = 100.0 * (pre_total - self.ledger.p.cash_eur) / pre_total if pre_total > 0 else 0.0
        directive = (f"{directive} | RISK STATE: {risk['state']} ({risk['reason']})\n"
                     f"{self._reminder_directive()}{self._cash_discipline_note(invested_pct)}")
        log.info("cycle_start", cycle_id=cycle_id, intents=intents, risk=risk["state"],
                 drawdown=round(risk["drawdown"], 4))

        # rotate the focus list across the whole universe (sweeps large/mid/small caps,
        # ETFs, commodities, FX, crypto over cycles) + always include held positions,
        # and make every agent portfolio-aware this cycle.
        held = list(self.ledger.p.positions)
        cycle_idx = int(self._state.get("cycle_count", 0))
        self._state["cycle_count"] = cycle_idx + 1
        self.watchlist = sample_watchlist(held, cycle_idx)
        # cross-pollinate: pull names the research loop recently flagged (deep dives,
        # undervaluation scans) into THIS cycle's watchlist, so a discovery like 'META
        # undervalued' gets analyzed by EVERY agent from all angles — not left in one note.
        try:
            flagged: list[str] = []
            for m in self.bb.memory_by_kind("research", limit=6):
                flagged += [a for a in (m.assets or []) if a]
            for a in dict.fromkeys(flagged):  # de-dup, preserve order
                if a not in self.watchlist:
                    self.watchlist.insert(0, a)
            self.watchlist = self.watchlist[:30]
        except Exception:
            pass
        pf_text = await self._portfolio_summary_text()
        for ag in (self.research, self.macro, self.fundamentals, self.sentiment,
                   self.ipo, self.altdata, self.risk, self.quant_research):
            ag.watchlist = self.watchlist
            ag.portfolio_context = pf_text
        self.smartmoney.watchlist = self.watchlist
        self.quant.watchlist = self.watchlist[:10]  # MC per ticker is heavy — cap it
        log.info("watchlist", cycle=cycle_idx, names=self.watchlist[:12], n=len(self.watchlist))

        # data + analysis agents (serialized inference handled by router)
        core_agents = [self.research, self.macro, self.fundamentals, self.sentiment,
                       self.ipo, self.altdata, self.quant, self.smartmoney]
        # self-extending: markdown-defined agents, re-scanned each cycle
        dynamic_agents = build_dynamic_agents(self.bb, self.router, self.tools, self.memory,
                                              self.watchlist, schedule="cycle", cycle_index=cycle_idx)
        for ag in dynamic_agents:
            ag.portfolio_context = pf_text
        # RiskAgent runs last so it can stress-test every peer report (incl. dynamic)
        all_agents = core_agents + dynamic_agents + [self.risk]
        self._emit("status", "Orchestrator", f"Cycle started — {len(all_agents)} agents",
                   f"risk={risk['state']}, watchlist={self.watchlist[:8]}", cycle_id=cycle_id,
                   phase="analysis", agents=[a.name for a in all_agents])
        for agent in all_agents:
            # feed each agent what its peers have ALREADY found this cycle, so later agents
            # build on / challenge earlier ones (true cross-agent visibility, not blind silos).
            try:
                agent.peer_context = self._peer_digest(cycle_id)
            except Exception:
                pass
            self._emit("status", agent.name, f"{agent.name} analyzing…", cycle_id=cycle_id,
                       phase="analysis", state="running")
            try:
                await agent.run(cycle_id)
                rep = next((r for r in reversed(self.bb.reports_for_cycle(cycle_id))
                            if r.agent == agent.name), None)
                if rep is not None:
                    self._emit("thinking", agent.name,
                               f"{agent.name}: {rep.stance} (conf {rep.confidence.score:.2f})",
                               rep.summary, cycle_id=cycle_id, stance=rep.stance,
                               confidence=rep.confidence.score, assets=rep.assets[:8],
                               findings=rep.findings[:5])
            except Exception as exc:  # one bad agent must not kill the cycle
                log.error("agent_failed", agent=agent.name, error=f"{type(exc).__name__}: {exc}")
                self._emit("error", agent.name, f"{agent.name} failed",
                           f"{type(exc).__name__}: {exc}", cycle_id=cycle_id)
        if dynamic_agents:
            log.info("dynamic_agents_ran", names=[a.name for a in dynamic_agents])

        portfolio_summary = await self._portfolio_summary_text()

        # deliberation: the council makes the agents work TOGETHER on the top candidates —
        # a bull/bear/synthesis debate across all angles and past/present/future — before
        # the decision, so ideas are evaluated deeply instead of judged in one shallow shot.
        council_dossier = ""
        try:
            from agents import evidence as _ev
            agg_for_council = _ev.aggregate(self.bb.reports_for_cycle(cycle_id), self.decision.priors)
            council_dossier = await self.council.deliberate(cycle_id, agg_for_council, portfolio_summary)
            self._emit("thinking", "CouncilAgent", "Deliberation (bull/bear/synthesis on top names)",
                       council_dossier[:600], cycle_id=cycle_id)
        except Exception as exc:
            log.error("council_failed", error=f"{type(exc).__name__}: {exc}")

        # current position weights (%), so the decision can ADD to a conviction name instead of
        # no-op'ing a buy whose target sits below the existing holding.
        held_w: dict[str, float] = {}
        if pre_total and pre_total > 0:
            for _a, _p in self.ledger.p.positions.items():
                _px = pre_prices.get(_a)
                if _px:
                    held_w[_a] = 100.0 * (_px * _p.qty) / pre_total
        decision = await self.decision.run(cycle_id, portfolio_summary, directive,
                                           council_dossier=council_dossier, holdings=held_w)
        self._emit("decision", "DecisionAgent",
                   f"{decision.action.value.upper()} {decision.asset or ''}".strip(),
                   decision.reasoning, cycle_id=cycle_id, action=decision.action.value,
                   asset=decision.asset, target_weight=decision.target_weight,
                   confidence=decision.confidence.score, block_reason=decision.block_reason)

        # back-off bookkeeping: count consecutive NO_ACTIONs so decision_due() stretches
        # the gap (research more, decide less) when the fund is repeatedly unsure.
        if decision.action == TradeAction.NO_ACTION:
            self._state["consecutive_no_action"] = int(self._state.get("consecutive_no_action", 0)) + 1
        else:
            self._state["consecutive_no_action"] = 0
        self._save_state()

        executed = None
        protective = []
        if not no_trade:
            # 1. protective exits ALWAYS run (bypass cooldown): stop-losses, then de-risk
            protective += await self._apply_stop_losses(pre_prices)
            if risk["state"] == DERISK:
                protective += await self._derisk()

            if risk["state"] != DERISK:
                # 2. active decision — execute directly when the agents are CONFIDENT
                # (no forced timer; the decision cycle only runs at reminders, and
                # DecisionAgent already returns NO_ACTION when not ready/uncertain).
                is_buy = decision.action in (TradeAction.BUY, TradeAction.ADD)
                is_reduce = decision.action in (TradeAction.TRIM, TradeAction.SELL)
                if decision.action != TradeAction.NO_ACTION:
                    if is_buy and decision.asset and not allow_buy(decision.asset, risk["state"]):
                        log.info("buy_blocked_by_risk", asset=decision.asset, state=risk["state"])
                    elif is_reduce and decision.asset and self._churn_blocked(decision.asset):
                        # anti-churn: don't pay round-trip fees reversing a freshly-opened
                        # position. Stop-losses + de-risk run ABOVE this and bypass the guard.
                        log.info("churn_blocked", asset=decision.asset,
                                 held_hours=round(self._hours_since_last_buy(decision.asset) or 0, 1))
                    else:
                        try:
                            executed = await self.execution.execute(decision)
                            # multi-buy: open extra high-conviction names this cycle
                            if executed and decision.additional_buys:
                                await self._execute_additional_buys(decision, risk["state"], cycle_id)
                        except Exception as exc:
                            log.error("execution_failed", error=f"{type(exc).__name__}: {exc}")
                # 3. passive core deploy if nothing else traded (light anchor)
                if executed is None:
                    try:
                        executed = await self._maybe_baseline()
                    except Exception as exc:
                        log.error("baseline_failed", error=f"{type(exc).__name__}: {exc}")

        if (executed and executed.status in ("filled", "closed")) or protective:
            self._state["last_trade_iso"] = datetime.now(timezone.utc).isoformat()
            self._save_state()
        elif no_trade:
            log.info("execution_skipped_human_no_trade", cycle_id=cycle_id)

        snap = await self.portfolio_snapshot()

        learning = {}
        try:
            learning = await self._learn(cycle_id, snap["total_value_eur"])
        except Exception as exc:  # learning is best-effort, never fatal
            log.error("learning_failed", error=f"{type(exc).__name__}: {exc}")

        # daily maintenance: real-day backup + memory re-verification audit
        daily = {}
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            bkp = maybe_daily_backup(self._state)
            if bkp:
                daily["backup"] = bkp
            if self._state.get("last_audit_date") != today:
                daily["audit"] = await self.memory_auditor.audit()
                pruned = self.rag.prune(int(settings().get("memory", {}).get("max_entries", 5000)))
                if pruned:
                    daily["pruned"] = pruned
                # keep high-volume audit tables bounded for long runs
                tc_pruned = self.bb.store.prune_table("tool_calls", keep=3000)
                self.bb.store.prune_table("reports", keep=2000)
                self.bb.store.prune_table("activity",
                    keep=int(settings().get("memory", {}).get("activity_max", 4000)))
                if tc_pruned:
                    daily["tool_calls_pruned"] = tc_pruned
                self._state["last_audit_date"] = today
            self._save_state()
        except Exception as exc:
            record_error("daily_maintenance", exc)

        result = {
            "cycle_id": cycle_id,
            "decision": decision.model_dump(mode="json"),
            "executed_trade_id": executed.id if executed else None,
            "protective_exits": [t.asset for t in protective],
            "risk": risk,
            "portfolio": snap,
            "intents": intents,
            "memory_size": self.rag.size(),
            "learning": learning,
            "daily": daily,
            "cost_usd": round(cost_meter().snapshot()["total_usd"] - _cost_start, 4),
        }
        log.info("cycle_done", cycle_id=cycle_id, action=decision.action.value,
                 cost_usd=result["cost_usd"],
                 traded=bool(executed), protective=len(protective),
                 risk=risk["state"], total=snap["total_value_eur"])
        return result
