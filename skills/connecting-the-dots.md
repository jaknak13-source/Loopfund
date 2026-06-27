# Skill: Connecting the Dots

How to fuse news, financials, macro, sentiment, and flows into ONE coherent thesis,
then trace the second-order and cross-asset links the crowd hasn't priced.

1. Frame the QUESTION first: what would have to be true for this name (or theme) to
   re-rate? You are testing a hypothesis, not collecting facts to confirm a hunch.
2. Pull each layer and write down the ONE thing it says:
   - News/catalyst: `gdelt_search`, `rss_headlines`, `web_search` — what changed and when.
   - Financials: `sec_financials` / `fundamentals` — does the business back the story
     (revenue trend, margins, balance sheet)? `estimate_fair_value` for the price gap.
   - Macro: `macro_snapshot`, `fred_series` (rates, CPI, spreads) — tailwind or headwind?
   - Sentiment: `reddit_hot`, `stocktwits_symbol` — is the crowd already euphoric/asleep?
   - Flows: `insider_transactions`, `congress_trades` — is smart money buying or selling?
3. Look for CONFLUENCE: a real thesis has 3+ layers pointing the same way. One screaming
   layer with the rest silent is a coincidence, not an edge.
4. Trace the second-order link: if the news is true, who ELSE re-prices? Walk supplier ->
   customer -> substitute -> cross-asset (FX via `fx_rate`, rates, commodities). Hand
   long chains to cross-market-chains; keep the link you can defend.
5. Resolve CONTRADICTIONS explicitly — bullish news + insider selling + stretched
   valuation is a yellow flag, not noise to ignore. State which layer wins and why.
6. Demand >= 2 independent credible sources for any load-bearing fact (evidence-verification);
   a primary source (filing, release) for large positions.
7. Write the thesis as one paragraph: catalyst, why it's mispriced, what confirms it,
   what kills it. If you can't, you don't have one — return NO_ACTION.
8. Size by confluence AND margin of safety. Numbers from tools over narrative vibes.

PITFALLS
- Confirmation bias: collecting only the layers that agree. Actively pull the layer most
  likely to break your thesis (usually flows or valuation).
- Narrative without P&L: a great story on a deteriorating income statement is a trap.
- Stale dots: date-check every input against the current authoritative time; a 6-month-old
  headline glued to today's price is a false connection.
- No live options/IV or intraday order-flow feed here — "flows" means insider/Congress
  filings and sentiment proxies, which lag. Don't overstate flow conviction.
