# Skill: Quant Model Invention

How to invent a NOVEL quantitative signal and validate it end-to-end with `run_python`
before trusting one euro to it. The default outcome of inventing a signal is that it's
noise; this playbook exists to prove otherwise or kill it fast.

1. HYPOTHESIZE from a mechanism, not a backtest: what real behavior or flow would create
   a mispricing? Examples of raw material — `congress_trades`/`insider_transactions`
   (informed flow), `reddit_hot`/`stocktwits_symbol` (retail attention), `gdelt_search`/
   `rss_headlines` (news intensity), `fred_series` (macro regime), `polymarket_markets`
   (crowd odds), `weather_forecast` (commodity demand). Write the causal story first.
2. SPECIFY the signal as an exact transform: which inputs, what window, how aggregated
   into one number per name per date. It must be deterministic and reproducible in
   `run_python` — if you can't write the formula, you don't have a signal.
3. PROVE the data is point-in-time: alt-data timestamps are treacherous (filings lag,
   social scrapes backfill). Confirm each input was knowable on the date you use it.
   Unverifiable timing = mark UNVERIFIED and do not trade it.
4. TEST predictiveness in `run_python`: rank names by the signal, sort into quantiles,
   measure FORWARD returns (next day/week/month) per quantile. Demand a monotonic
   spread top-vs-bottom, not just a good top bucket. Check information coefficient
   (rank correlation of signal vs forward return) for stability over time.
5. CONTROL for the obvious: is this just repackaged momentum, size, or sector beta?
   Regress out / neutralize known factors (see `factor-investing`) and re-test. A "novel"
   edge that's 90% momentum is not novel — it's leverage on a known premium.
6. FULL backtest via `quant-backtesting`: realistic costs+slippage, walk-forward,
   out-of-sample, stress tests. Novel signals overfit easily because there's no prior —
   be MORE skeptical, not less. Reject implausible Sharpe outright.
7. CORROBORATE and size tiny: even a validated novel signal needs the house bar
   (>= 2 independent credible sources for any real-name position) and a small, basketed,
   EUR-base dry-mode allocation with a pre-set invalidation. If it passes and is genuinely
   reusable, `propose_skill` to capture it; otherwise document the negative result and move on.

PITFALLS
- Data mining: testing 50 signals and keeping the one that worked is guaranteed false
  positives. Pre-register the hypothesis; count how many you tried and discount accordingly.
- Alt-data look-ahead and backfill: the most exciting "edges" are usually timing bugs.
  Lag everything and verify availability dates.
- Tiny / illiquid samples: social and congress signals cover few names sparsely — a great
  IC on 8 stocks is noise. Require a minimum name count and forward-period count.
- Falling in love with a novel idea: novelty is not evidence. Deterministic OOS numbers
  decide; NO_ACTION beats trading an unproven model.
