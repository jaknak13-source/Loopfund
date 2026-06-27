# Skill: Portfolio Construction

How to assemble individual ideas into a coherent book: diversify, size by conviction
AND volatility, cap concentration and correlation, rebalance with discipline, and
treat cash as a real position.

1. Start from the whole book, not the single name. Every add changes the
   portfolio's risk, not just adds a line. Ask: what does this do to total exposure?
2. Size by conviction x inverse volatility. High-conviction, lower-vol names earn a
   bigger weight; speculative or high-vol names get starter-sized. Pull `history` and
   compute realized vol with `run_python` so weights rest on deterministic numbers.
3. Diversify across INDEPENDENT drivers, not just tickers. Map each holding to its
   real driver (AI capex, rates, oil, consumer). Names sharing a driver are one bet —
   see cross-market-chains for tracing shared exposure.
4. Hard caps: max single-name % of NAV, max sector %, max per-driver %. Use
   `fundamentals` for sector/industry tags. Breaching a cap forces a trim, regardless
   of how good the story feels.
5. Correlation budget: before adding, check pairwise correlation of candidate vs
   existing book (`run_python` on `history`). Prefer adds that lower or hold book
   correlation; a low-correlation diversifier can warrant more size than its
   standalone conviction.
6. Cash IS a position. Holding cash when nothing clears the bar is a decision, not a
   failure — NO_ACTION at the portfolio level. Dry/EUR base; use `fx_rate` to express
   all weights and the cash buffer in EUR before comparing.
7. Rebalance on RULES, not impulse: trim winners back toward target weight when they
   breach a cap, top up underweight high-conviction names, harvest names whose thesis
   broke. Trade the gap to target, not the noise.
8. Barbell the risk: a core of higher-conviction, corroborated positions plus a small
   basket of asymmetric niche bets (see niche-discovery) — never one concentrated gamble.
9. Re-run construction when the macro regime shifts (`macro_snapshot`, `fred_series`):
   a risk-off regime means lower gross and more cash, not the same weights.

PITFALLS:
- Diworsification: 30 names that all ride the same driver is concentration wearing a
  diversification costume. Count drivers, not tickers.
- Letting a winner run past its cap turns a good position into an un-sized risk. A cap
  is a cap even when it hurts to trim.
- Ignoring FX: a book that looks balanced in local prices can be lopsided in EUR. Weigh
  in base currency.
- Over-rebalancing churns the book on noise. Rebalance to bands, not to a moving target.
