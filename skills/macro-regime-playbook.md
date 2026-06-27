# Skill: Macro Regime Playbook

How to read the prevailing macro regime from cheap proxies and map it to portfolio
positioning. The regime is the tide; it sets the odds before any single-name thesis.

1. Pull `macro_snapshot` for the proxy panel: ^TNX (10y yield), ^VIX (equity vol),
   DXY (dollar), and commodities (oil, gold, copper). Cross-check rates/inflation
   with `fred_series` (e.g. DGS10, DGS2, CPIAUCSL, UNRATE) for the official series.
2. Read each axis as a LEVEL and a TREND (rising/falling), not a single tick:
   - Rates: ^TNX / 2s10s curve. Rising long yields = tightening, pressures duration
     and long-duration growth/tech; steepening vs flattening signals growth vs recession bias.
   - Inflation: CPI trend via `fred_series` + commodities/gold as the fast proxy.
   - Growth: copper ("Dr. Copper"), oil demand, employment series; copper up + curve
     steepening = reflation; both rolling over = slowdown.
   - FX: DXY. Strong dollar tightens global liquidity, hurts EM and USD commodities,
     and matters for our EUR base — convert any USD view with `fx_rate(USD,EUR)`.
   - Vol: ^VIX. Low/falling = risk-on carry regime; spiking = risk-off, de-risk fast.
3. Classify into one regime: Reflation (growth+inflation up), Goldilocks (growth up,
   inflation tame), Stagflation (inflation up, growth down), Deflation/Risk-off
   (both down, vol up). State which one and the 2-3 proxies that put you there.
4. Map regime -> positioning bias:
   - Reflation: cyclicals, energy, materials, financials; underweight long-duration bonds.
   - Goldilocks: quality growth, broad equity beta; vol-selling carry works.
   - Stagflation: energy, commodities, gold, pricing-power names; cut rate-sensitive growth.
   - Risk-off: raise cash, defensives, quality, hedges (ties to crash-warning-signs).
5. Demand >=2 independent confirmations of a regime SHIFT before repositioning — one
   hot CPI print or one VIX spike is noise. Corroborate the proxy move with `fred_series`
   or `web_research` on the actual data release; date-check the release.
6. Size by regime conviction: a clear, multi-proxy regime justifies a tilt across the
   book; a murky/transitioning regime means stay neutral. NO_ACTION on the macro
   overlay is fully valid — don't manufacture a regime call to feel busy.
7. Output: named regime, the proxy evidence, the directional tilt, and the invalidation
   (which proxy reversing would flip the call). Hand single-name selection to the
   sector/valuation playbooks within that tilt.

PITFALLS:
- These are PROXIES, not the data. ^TNX/DXY/^VIX move on positioning and intraday noise;
  confirm with the actual `fred_series` release before treating a wiggle as a regime change.
- No live options/IV surface or real-time rates feed on free data — ^VIX is delayed and
  daily-ish; do not infer precise vol regime timing, read direction only.
- Regimes transition gradually and whipsaw; chasing every flip churns the book. Require
  trend persistence, not a single bar.
- Correlation isn't the mechanism. State WHY a proxy maps to your tilt (the transmission
  channel), or you're curve-fitting. Deterministic readings over macro vibes.
