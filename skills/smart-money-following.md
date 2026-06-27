# Skill: Smart-Money Following

How to turn congressional and insider trade disclosures into a signed, sized LEAD.
These people often know the business or the policy better than the crowd — but the
data is delayed and noisy, so it is a tilt, not a trigger.

1. Pull `congress_trades` and `insider_transactions(ticker)`. Read every row with the
   filer, direction, size, and DISCLOSURE DATE (not just the trade date).
2. Signal vs noise — open-market BUYS are the signal; selling is mostly noise:
   - INSIDER OPEN-MARKET BUYS (officers/directors spending own cash, esp. CEO/CFO,
     esp. clustered across multiple insiders) = the strongest tell. Conviction buy.
   - Routine SELLING is usually noise: 10b5-1 scheduled plans, option-exercise-and-sell,
     tax/diversification. Do NOT read ordinary selling as bearish. Only an unusual,
     large, unscheduled cluster of sells near bad news deserves a second look.
   - CONGRESS: weight large, well-timed buys near relevant legislation/committee work;
     small or broad-index trades are noise. Treat as a curiosity tilt, not gospel.
3. Build a signed score with `run_python`: net = (cluster of insider buys) positive,
   (isolated/scheduled sells) ~zero. Weight by (a) filer seniority, (b) dollar size vs
   their net worth/salary, (c) clustering (3+ insiders > 1), (d) freshness of disclosure.
4. SIZE: a strong clustered insider-buy signal supports a small-to-medium STARTER once
   corroborated. It raises conviction on a thesis; it does not by itself clear the bar.
   A single congressional buy alone = NO_ACTION on size, watchlist only.
5. CORROBORATE before EUR risk: pair the signal with fundamentals (`fundamentals`,
   `sec_financials`) and >=2 independent credible sources (evidence-verification).
   Smart-money flow is a reason to LOOK, then verify, then size.
6. Sign and record the lead on the report: ticker, direction (BUY tilt / no tilt),
   the filers and dollar size that drove it, the disclosure dates, and your confidence.
   Hand a deterministic number to the risk agent, not "insiders seem bullish".

PITFALLS:
- Disclosure lag: filings can be days to weeks late — the edge may be priced in. Date-check.
- Reading every sale as bearish — the single most common error here. Sells are mostly noise.
- Survivorship/selection: you see disclosed trades, not the full book or the hedges/options
  around them. No live options/IV feed exists here to see the offsetting leg.
- Over-weighting one famous name. One filer is an anecdote; a cluster is a signal.
