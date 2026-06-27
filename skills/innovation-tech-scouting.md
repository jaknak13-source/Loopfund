# Skill: Innovation & Tech Scouting

How to spot emerging tech early from filings, news, and niche sources — and separate
real adoption from hype before the crowd or the price moves.

1. Start from a SIGNAL, not a buzzword: a new product shipping, a design win, a capex
   commitment, a regulatory approval, a standards change. "X is the future" is not a signal.
2. Mine primary sources for early evidence:
   - `recent_filings` / `sec_financials`: new segment disclosures, R&D ramp, capex lines,
     risk-factor language shifts, named customers/partners in 10-K/10-Q/8-K.
   - `gdelt_search` + `rss_headlines`: announcements, conference launches, partnerships.
   - `web_research` / `web_fetch`: niche trade press, engineering blogs, standards bodies,
     patent and grant databases — where adoption shows up before mainstream coverage.
3. Demand ADOPTION evidence, not intent: real customers, shipping revenue, repeat orders,
   capacity being built. Pilots and LOIs are weaker than booked revenue in `sec_financials`.
4. Build the value chain: who actually monetizes the innovation vs who just talks about it?
   Often the picks-and-shovels supplier captures value before the headline name. Use
   `propose_ticker` to log non-obvious beneficiaries for analyst follow-up.
5. Cross-check the money: `insider_transactions` / `congress_trades` for accumulation;
   `estimate_fair_value` to see whether the innovation is already fully priced.
6. Read sentiment as a CONTRA gauge: `reddit_hot`, `stocktwits_symbol`. Peak retail froth
   with thin revenue = late; quiet forums with accelerating filings = early.
7. Require >= 2 independent credible sources, primary where possible (evidence-verification).
   Size SMALL and basket — most emerging-tech bets fail; survivors must carry the losers.

PITFALLS
- Hype vs adoption: press releases and TAM slides are marketing. Anchor on shipped revenue
  and capex you can find in filings.
- Right trend, wrong vehicle: the innovation is real but a commodity; no pricing power means
  no durable margin. Check moat before sizing.
- Timing risk: early can mean dead money for years, or dilution before payoff. Define the
  catalyst and invalidation; if neither is near, NO_ACTION is valid.
- Free-data limits: no proprietary patent/clinical feeds here; coverage is uneven on
  private and pre-revenue names. Flag what you couldn't verify rather than guessing.
- Deterministic check beats vibes: ground every claim in a number from `sec_financials` or
  `estimate_fair_value`. Dry-mode, EUR base — convert with `fx_rate` before comparing names.
