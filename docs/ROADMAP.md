# Roadmap: future work (not yet implemented)

Backlog of ideas for a more proactive, autonomous local research system. Nothing
here is built yet; it is implemented deliberately, one tested increment at a time.
Philosophy to preserve: **proactive, curious, creative, open to new approaches,
takes as much time as it needs, never forces a decision, always logical and
evidence-driven.**

## Guiding principles (apply to everything below)
- Take time over conviction: a thesis can develop over days/weeks; NO_ACTION is
  always valid; never trade to "do something."
- Curiosity + novelty: actively seek new sources, angles, and methods, not just
  re-read known ones.
- Verify everything; cross-check; treat memory/web as untrusted until confirmed.
- Every new method must prove itself in backtest/dry-run before it earns trust.
- Keep it modular: new tool = drop a file; new agent = drop a briefing.

---

## 0. Already built (don't rebuild, extend)
Core loop, 12 agents + dynamic markdown agents + MetaAgent, evidence-weighted
decision, RiskGovernor (drawdown brakes/stop-loss), passive core, SimLedger (EUR,
FX, fees), learning loop (agent + source trust, SP500 benchmark), bounded RAG +
daily audit, backups/restore, prompt-injection defense, code sandbox, web/weather/
vision tools, adaptive query generation, tabbed dashboard, all settings in UI.

---

## 1. Proactive / agentic research
- **Iterative browse loop (ReAct):** let an agent read a page, decide which links
  to click next, and go 2-3 hops deep: real web exploration, not one-shot fetch.
- **Source discovery:** find and trial new sources automatically; promote ones that
  prove reliable (source-trust already scores; add discovery + auto-RSS-detect).
- **Browser automation (Playwright):** render JS-heavy sites, dismiss cookie walls,
  read charts/tables, scroll infinite feeds, screenshot for the vision model.
- **More channels:** Twitter/X, Reddit, Telegram, Substack, StockTwits,
  YouTube/podcast earnings-call transcription (whisper), company IR pages, forums.
- **Curiosity engine:** novelty-seeking; prioritize under-explored tickers/themes;
  rotate angles; add randomness + "what am I not looking at?" critic.
- **Multi-search-engine:** beyond DuckDuckGo (Brave/SearXNG/Google CSE, news APIs).

## 2. More data sources (free/alt first; flag paid)
- SEC EDGAR full-text + **XBRL financial-statement parsing** (real fundamentals),
  Form 4 insider trades, 13F institutional holdings, S-1/424B for IPOs.
- Earnings-call transcripts + guidance extraction.
- Congress/Senate trades (Quiver/Capitol Trades), lobbying, gov contract awards.
- Options flow, IV, put/call ratio, short interest, gamma exposure (free where possible).
- Google Trends, app-store ranks, web-traffic estimates, GitHub/dev activity,
  Wikipedia pageviews, job postings (demand/adoption proxies).
- Shipping/AIS, satellite tiles (parking lots, ships, crops), commodity spot/futures.
- Crypto on-chain (exchange flows, accumulation), ETF flows, funding rates.
- Prediction markets (Polymarket/Kalshi) as **sentiment/probability**, not for trades.
- FX/macro: ECB, BIS, IMF, World Bank, Treasury auctions, yield curve.

## 3. Vision / multimodal
- Read charts and extract levels/trends; parking-lot / ship-count from satellite;
  parse scanned PDFs/filings; interpret dashboard screenshots; OCR tables.
- Dedicated vision model already wired (analyze_image); build agents that use it.

## 4. Quant / analytical depth
- Proper **factor models** (Fama-French + momentum/quality/low-vol) + attribution.
- **Statistical arbitrage / pairs** (cointegration, Kalman hedge ratios).
- **Regime detection** via HMM (hmmlearn) + clustering; regime-conditional strategy.
- **Volatility**: GARCH (arch), realized/implied spread, vol-of-vol.
- **Options**: Black-Scholes + Greeks, IV surface, hedging with options.
- **Portfolio optimization**: mean-variance, risk parity, Black-Litterman, CVaR/
  min-drawdown, Kelly-portfolio; covariance with Ledoit-Wolf (basic shrink exists).
- **Monte Carlo**: fat tails/jumps (Student-t, Merton), scenario trees, path-dependent.
- **Backtesting engine**: vectorbt, walk-forward, purged/embargoed CV, realistic
  costs/slippage, regime splits. *Gate every new method through this before trust.*
- Anomaly/divergence detection (sentiment vs price, breadth, correlation breaks).

## 5. Reasoning / agent architecture
- **Multi-round debate** (not one rebuttal): bull vs bear vs risk, several rounds,
  converge or escalate uncertainty.
- **Self-consistency:** sample N decisions, compare, act only on agreement.
- **Multi-model ensemble:** run the decision on 2-3 models (local + cloud), compare;
  disagreement: lower confidence / NO_ACTION.
- **Tree-of-thought / deliberation budget:** spend more compute on high-stakes calls.
- **Reflection + red-team agent:** a dedicated adversary that tries to break each thesis.
- **Thesis lifecycle:** open theses with explicit falsification criteria; track them
  across days; Bayesian-update belief as evidence arrives; close when proven/refuted.
  This is the "take its time, don't force it" backbone.
- Roles split: Analyst (research) → PM (allocation) → Trader (execution) → Auditor.

## 6. Memory / learning
- **Better embeddings** (local nomic / sentence-transformers) for sharper recall.
- **Knowledge graph** of entities (companies, people, sectors, events) + relations
  (supplier-of, competitor, exposed-to) for cross-asset/causal reasoning.
- Hierarchical memory: episodic (events) / semantic (facts) / procedural (methods).
- Contradiction detection + consolidation; causal-chain store; pattern mining of
  "what worked / what failed"; per-strategy A/B with outcome stats.
- Meta-learning: learn which METHODS to trust per regime, not just sources/agents.

## 7. Execution / portfolio (toward live)
- **IBKR adapter** (real API, EUR) behind the existing ExecutionAdapter interface;
  human-approval gate before any live order; explicit confirmations.
- Options/hedging strategies; inverse-ETF/put tail hedges; rebalancing optimizer;
  DCA/laddering; limit orders + slippage; dividends/corporate actions; tax-aware.
- Multi-currency P&L; scenario-based hedges keyed to open risks.

## 8. Risk management (institutional)
- VaR/CVaR, factor-exposure limits, liquidity risk, correlation-breakdown alarms.
- Stress tests: 2008, COVID, rate-shock, war/energy-spike scenarios.
- Monte Carlo portfolio paths; regime-conditional risk budget; tail-hedge triggers.

## 9. Self-improvement / autonomy
- MetaAgent v2: tune/retire under-performing agents, A/B agent variants, evolve the
  roster by measured contribution to good calls.
- **Self-writing tools** (sandboxed, test-gated), not just agents.
- Prompt self-optimization; auto-discovery + integration of new data sources.
- Curriculum: start conservative, widen mandate as calibration earns trust.
- Code self-improvement loop with mandatory test pass + backtest gate before adopt.

## 10. Dashboard / UX
- Equity curve, drawdown chart, allocation-over-time, calibration reliability plot,
  source-trust leaderboard, agent debate transcripts, thesis board (open/closed).
- What-if simulator; backtest UI; alerts/notifications (push/email/Telegram).
- **Human-approval mode:** optional gate where you confirm trades before they fill.
- Reasoning-trace viewer (full chain for any decision); mobile view.

## 11. Reliability / ops (for true 24/7 over months)
- **Memory-aware operation:** cap concurrent model memory, prefer a smaller model
  for gather-agents and a strong model only for the decision, tune context per
  available RAM, avoid running a second model process.
- **launchd/pm2 supervisor:** auto-start on login, auto-restart on crash/reboot.
- Per-API rate-limit backoff + rotation (GDELT 429s seen); model fallback chain
  (local down → cloud); health checks + watchdog; alerting on repeated errors.
- Log rotation; cost tracking (if cloud used); telemetry dashboard.

## 12. Eval / validation (earn trust with evidence)
- Backtest harness + walk-forward; reconcile paper-trade vs backtest.
- Calibration metrics (Brier, reliability diagram), benchmark suite, replay mode.
- "Would this have worked historically?" gate before any method is trusted live.
- Decision explainability / audit export.

## 13. Innovative edge-seeking (the SOTA / creative core)
- **Cross-asset causal impact graph:** weather→crop→food→input-cost→sector; chip
  shortage→autos→rental pricing→travel: propagate shocks through a graph.
- Narrative-momentum tracking (story gaining/losing traction vs fundamentals).
- Event-driven: M&A arb, earnings drift, index rebalancing, IPO lockups.
- Smart-money following (13F/insider/Congress) with verification.
- Sentiment-vs-reality divergence; meme/social velocity; regime-switch detection.
- Geopolitical scenario trees; policy/regulation impact modeling; second-order effects.

## 14. Model / inference
- Multi-model routing (cheap gather / strong decide); structured-output grammars
  (JSON schema enforcement) so parsing never fails; reasoning-budget control;
  local+cloud hybrid; optional fine-tune on the fund's own validated decisions.

---

### Suggested order (highest leverage first)
1. Ops: memory-aware model routing + supervisor (stability for months).
2. Agentic browse loop + source discovery (more proactive research).
3. Backtest harness + method-gating (so self-invented methods earn trust safely).
4. Thesis lifecycle + multi-round debate (take-its-time deliberation).
5. EDGAR XBRL fundamentals + earnings transcripts + insider/13F (real edge data).
6. Knowledge graph + better embeddings (cross-asset reasoning).
7. Multi-model ensemble + self-consistency (decision robustness).
