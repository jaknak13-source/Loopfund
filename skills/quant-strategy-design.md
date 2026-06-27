# Skill: Quant Strategy Design

How to turn a vague hypothesis ("momentum works in semis") into a systematic,
testable strategy with explicit, falsifiable rules — before any capital, even
dry-mode EUR.

1. STATE the hypothesis as one sentence with a WHY: an economic/behavioral reason
   the edge should exist (risk premium, structural flow, behavioral bias). No story,
   no strategy — random patterns fit noise.
2. Define the UNIVERSE precisely: which tickers, what liquidity/size floor, listed
   where. Use `propose_ticker` to register candidates so they have `price`/`history`
   coverage. Fix the universe BEFORE looking at returns (avoid cherry-picking winners).
3. Specify the SIGNAL deterministically: an exact formula computable from
   `history`/`price`/`fundamentals`/`sec_financials`/`fred_series`. It must be a
   number, not a vibe — e.g. "12-1 month total return", "EV/EBIT rank", "5-day RSI".
   Write it so `run_python` can reproduce it bit-for-bit.
4. Define ENTRY/EXIT rules with thresholds: enter when signal crosses X, exit on
   stop / target / time / signal-reversal. State holding period and rebalance cadence.
   Every rule needs a default and a do-nothing branch — NO_ACTION is a valid output.
5. Define RISK upfront: per-position size (vol-targeted or fixed-fraction), max gross,
   max per-name, correlation/sector caps, and a hard invalidation that kills the trade.
   Express sizing in EUR base; use `fx_rate` to convert non-EUR instruments.
6. Pre-register the SUCCESS metric and the kill criteria: what out-of-sample Sharpe /
   hit-rate / max-drawdown makes this live-worthy, and what result retires it. Decide
   this before backtesting so results can't move the goalposts.
7. Hand to `quant-backtesting` to validate. A strategy that can't be backtested
   deterministically isn't a strategy — it's a hunch. Corroborate any fundamental
   inputs to the house bar (>= 2 independent credible sources) before sizing real.

PITFALLS
- Story-first design: building rules to fit a chart you already saw is curve-fitting.
  Demand the economic reason first.
- Vague rules ("buy when it looks strong") can't be tested or audited — forbid them.
- Free-data limits: `history` depth and breadth are finite and there's no live
  options/IV or intraday feed — design daily-or-slower strategies, not HFT.
- Ignoring costs at design time leads to "edges" that vanish after fees/slippage; bake
  realistic costs into the success metric from the start.
