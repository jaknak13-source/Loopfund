# Skill: Reading SEC Filings

How to find and mine 10-K/10-Q/8-K and Form-4 for the facts and red flags that
move a thesis. The filing is the primary source the RiskAgent will demand.

1. Locate filings: `recent_filings(ticker)` lists recent forms with dates and
   types. Pull structured financials with `sec_financials(ticker)`. Always
   date-check against the current authoritative time — last quarter's 10-Q is stale.
2. Know what each form is for:
   - 10-K (annual): full audited statements, full MD&A, the Risk Factors section,
     footnotes, segment data. The richest single source.
   - 10-Q (quarterly): unaudited update, lighter MD&A, fewer footnotes. Use for
     trend and the latest quarter's surprises.
   - 8-K (event): material events between reports — guidance, M&A, exec departures,
     auditor changes, debt covenants, restatements. The early-warning channel.
   - Form-4: insider buys/sells. Cross-check with `insider_transactions(ticker)`.
3. Where the truth hides: read MD&A for management's own framing of trends and the
   reasons behind them; read Risk Factors for what they're legally required to admit;
   read the FOOTNOTES for revenue recognition, off-balance-sheet items, stock-based
   comp, related-party deals, and segment splits the headline buries.
4. Red flags to hunt: revenue recognized aggressively, growing gap between net income
   and operating cash flow, rising days-sales-outstanding, "adjusted" metrics drifting
   from GAAP, going-concern language, auditor change, a new 8-K restatement, heavy
   insider selling on Form-4.
5. Compare the narrative to the numbers: if MD&A says "strong demand" but
   `sec_financials` shows inventory and receivables ballooning faster than sales,
   trust the numbers. Reaction and tone are not evidence.
6. Corroborate material claims against a second independent source (`web_research`,
   `rss_headlines`) before sizing — a filing is primary, but confirm you read it
   right and that nothing newer (an 8-K) overrides it.

PITFALLS
- Reading only the press-release headline or the summary table and skipping
  footnotes/MD&A — that's exactly where the dilution and the related-party deals sit.
- Treating insider selling as automatically bearish: Form-4 sales are often scheduled
  10b5-1 or tax-driven. Insider BUYING is the higher-signal event.
- Free-data limits: `sec_financials`/`recent_filings` cover US SEC issuers and can
  lag the actual EDGAR posting; foreign filers (20-F/6-K) and exhibits may be thin or
  absent. If a form you need isn't there, mark it UNVERIFIED rather than assuming.
- Don't over-trade an 8-K headline before confirming materiality and a second source;
  NO_ACTION beats a position built on a misread event.
