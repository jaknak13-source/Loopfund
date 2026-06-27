# Skill: Comparables Analysis

How to value a company relative to its peers using multiples — and how to know when
the comps are lying to you. Fast sanity check, never the whole thesis.

1. Build a real peer set: same industry, similar size, similar growth and margin
   profile, similar capital structure. 4-8 names. A peer set chosen to flatter the
   thesis is worthless — pick honestly.
2. Pull the figures for the target and every peer with `fundamentals(ticker)`
   (multiples, margins, growth) and `sec_financials(ticker)` where you need to
   recompute a metric consistently. Use `price`/`history` for the current multiple.
3. Pick multiples that fit the business: P/E for stable earners, EV/EBITDA for
   capital-intensive or differing leverage, EV/Sales for unprofitable growth, P/B
   for financials. Apply the SAME multiple definition to every name — mixing trailing
   and forward, or GAAP and adjusted, across the set produces garbage.
4. Compute the peer median and range (not just the mean — one outlier skews a mean).
   Locate the target in that distribution. Cheap or expensive vs peers, and by how much.
5. Explain the gap before trading it. A discount is only opportunity if it's
   unjustified. If the target grows slower, earns lower returns on capital, or carries
   more risk, the discount is DESERVED — that's a value trap, not a buy.
6. Cross-check relative value against intrinsic value (`estimate_fair_value`, and the
   financial-modeling / valuation-playbook skills). When relative and absolute agree,
   conviction is higher; when they conflict, find out why before sizing.
7. Convert any peer prices/EV to EUR via `fx_rate` if the set spans currencies, so the
   dry-mode book compares like with like.

PITFALLS
- Garbage peer set: throwing dissimilar names together or cherry-picking high
  multiples to manufacture upside. The comp set is the analysis — get it right first.
- Multiples are relative, not absolute: if the WHOLE sector is in a bubble, "cheap vs
  peers" can still be expensive. Pair with an intrinsic check.
- Apples-to-oranges metrics: comparing a net-cash company's EV/EBITDA to a levered
  one's, or trailing vs forward P/E. Define each multiple once and apply it uniformly.
- One number isn't evidence: a single cheap multiple is a lead, not a position.
  Corroborate with >= 2 independent sources and an intrinsic cross-check, or NO_ACTION.
