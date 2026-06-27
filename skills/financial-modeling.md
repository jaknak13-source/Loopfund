# Skill: Financial Modeling

How to build a defensible 3-statement + DCF model from filings, then test what
breaks it. The point is a number you can defend, not a spreadsheet that looks busy.

1. Pull the raw data: `sec_financials(ticker)` for income statement, balance sheet,
   and cash flow history; `fundamentals(ticker)` for margins, shares, and ratios.
   Get >= 3 years so trends, not one-offs, drive the assumptions.
2. Build the income statement first: revenue, then margins as % of revenue
   (gross, EBIT, net). Anchor every assumption to history — if the 3yr gross
   margin is 38-41%, do not model 50% without a named, sourced reason.
3. Link the three statements so they reconcile: net income flows to retained
   earnings and to cash-flow-statement top line; capex and D&A tie to PP&E;
   working-capital deltas hit cash. If cash doesn't foot, the model is wrong.
4. Drive the DCF off unlevered free cash flow: EBIT*(1-tax) + D&A - capex - ΔNWC.
   Project 5yr explicit, then a terminal value (Gordon growth g <= long-run GDP,
   or an exit EBITDA multiple cross-checked against peers).
5. Discount at WACC. Use `fred_series` for the risk-free rate (e.g. DGS10) and
   build cost of equity from a sane beta and equity-risk premium; do not invent a
   discount rate. State it explicitly.
6. Cross-check the output against `estimate_fair_value(ticker)` — if your DCF and
   the tool's blended value disagree by a lot, find out why before trusting either.
7. SENSITIVITY is the deliverable, not the base case. Use `run_python` to flex the
   2-3 variables that move the answer most (revenue growth, terminal g/exit
   multiple, margin) and produce a value RANGE. A model with one number is a lie.
8. Reverse it: solve for the growth/margin the CURRENT price implies. If the market
   already requires heroics, there's no margin of safety regardless of your base case.
9. Convert to EUR with `fx_rate` for the dry-mode base currency before comparing to
   the book. Report the range, the key assumptions, and the source for each.

PITFALLS
- Terminal value is usually 60-80% of a DCF — a sloppy terminal g/exit multiple
  dwarfs years of careful explicit-period work. Stress it hardest.
- Tying value to a single hero assumption (one growth rate) is false precision;
  conviction comes from a range that still clears price, not a pretty point estimate.
- Free-data limits: `sec_financials` may lag or miss segment/footnote detail and
  non-US issuers. If an input is missing or stale, mark it UNVERIFIED, don't fill
  the gap with vibes. There is no live cost-of-capital feed — you build WACC by hand.
- A model is necessary, not sufficient: corroborate the thesis with >= 2 independent
  sources before it backs a real position. If you can't, NO_ACTION is a valid output.
