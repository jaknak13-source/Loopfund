# Skill: Trend & Thematic Research

How to research a secular/thematic trend, find the DURABLE winners, and avoid paying
the hype top.

1. Separate SECULAR from cyclical: a real theme has a multi-year structural driver
   (demographics, policy mandate, cost-curve collapse, re-shoring). Confirm the driver with
   data, not a narrative — `fred_series` / `macro_snapshot` for the macro backdrop,
   `web_research` for the demand thesis and timeline.
2. Size the runway: is adoption early (room to compound) or saturated (decelerating)? Look
   for accelerating revenue across the cohort in `sec_financials` / `fundamentals`, not a
   single quarter.
3. Map the value chain and rank by VALUE CAPTURE: enablers, platforms, commoditized parts.
   Favor names with pricing power and a moat over whoever has the loudest press. Use
   cross-market-chains logic; log candidates via `propose_ticker`.
4. Score each candidate on durability: revenue growth, margin trend, balance-sheet strength,
   reinvestment runway. The durable winner survives the shakeout; the hype name doesn't.
5. Check the entry price: `estimate_fair_value` + reverse-DCF. A great theme at a price that
   already implies the whole future is not a buy — demand a margin of safety (valuation-playbook).
6. Gauge crowding: `reddit_hot`, `stocktwits_symbol`, `gdelt_search` headline volume. Mass
   euphoria + parabolic price + thin earnings = late-cycle; size down or wait.
7. Corroborate with >= 2 independent credible sources, primary for large positions
   (evidence-verification). Express the theme as a small BASKET to diversify single-name
   risk, not one concentrated bet.

PITFALLS
- Theme right, timing wrong: buying after consensus has fully priced it. Crowding + stretched
  valuation is the warning; a real trend can still be a terrible trade at the top.
- Confusing the theme with the stock: the trend can be real while a specific name is
  overvalued, diluting, or losing share. Underwrite the company, not the slogan.
- Commodity trap: chasing the part of the chain with no pricing power. Volume growth without
  margin is not a winner.
- No live fund-flow/ETF-creation feed here; crowding read leans on sentiment and headline
  proxies, which lag. NO_ACTION is valid when entry is poor — themes don't expire next week.
- Base currency is EUR (dry-mode): convert multi-region candidates with `fx_rate` before
  ranking, so an FX swing isn't mistaken for relative performance.
