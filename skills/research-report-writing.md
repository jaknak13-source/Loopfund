# Skill: Research Report Writing

How to structure an investment thesis so the RiskAgent and PM can act on it. A report
is a falsifiable argument with citations, not a story. If it can't be proven wrong, it
can't be trusted.

Write the report in this order:

1. SUMMARY (3-4 lines): the call (long/short/NO_ACTION), the name, the one-line reason,
   proposed size, and confidence. A reader should grasp the bet before the details.
2. THESIS: the core argument — what the market is missing and why it re-prices. State
   the structural driver (see cross-market-chains / niche-discovery) explicitly.
3. EVIDENCE & CITATIONS: every load-bearing claim needs >= 2 independent credible
   sources (evidence-verification), with a PRIMARY source for any large/concentrated
   position. Pull primaries with `sec_financials`, `recent_filings`, `fundamentals`;
   corroborate with `web_search` / `web_research` / `rss_headlines`; gauge sentiment
   (not truth) with `reddit_hot`, `stocktwits_symbol`, `gdelt_search`. Mark uncorroborated
   items UNVERIFIED — they lower confidence, never raise it.
4. VALUATION: deterministic numbers via `estimate_fair_value` (see valuation-playbook).
   Give bull / base / bear value, the margin of safety vs `price`, and the
   price-implied growth. No single false-precision number.
5. CATALYSTS: what makes it re-price and WHEN — earnings (`recent_filings`), macro
   (`macro_snapshot`, `fred_series`), insider/political flow (`insider_transactions`,
   `congress_trades`), event odds (`polymarket_markets`). Cheap stays cheap without one.
6. RISKS: the real ways to lose, including the bear case stated fairly. Name liquidity,
   FX (`fx_rate`, EUR base), crowding, and any binary-event timing.
7. SIZING: proposed weight and the entry/stop, justified by conviction and volatility
   (risk-management-playbook, portfolio-construction). State max loss in EUR.
8. FALSIFIERS: the specific facts/prices that would PROVE THE THESIS WRONG and trigger
   exit. Be concrete — "if Q3 gross margin drops below X" beats "if fundamentals worsen".

PITFALLS:
- Narrative dressed as analysis: a compelling story with one source is a lead, not a
  thesis. Cite or cut.
- No falsifier = unfalsifiable = unactionable. Always write the exit condition first,
  not last.
- Burying the call: lead with the recommendation and size; don't make the reader mine
  for it.
- Recommending action when evidence is thin. NO_ACTION is a legitimate, well-supported
  conclusion — write it confidently when it's the honest answer.
