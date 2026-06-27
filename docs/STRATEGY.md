# Fund House Rules

The DecisionAgent and RiskAgent MUST read and obey this file before every
decision. Human edits here override default agent behavior. This is the safety
floor that keeps a single hallucination, fake-news item, or model error from
breaking the portfolio.

## Hard limits (never violated without an explicit human flag)
- LONG ONLY. NEVER propose a short position. Shorting is not supported and not allowed.
  Do not waste reasoning discussing shorts; if a name looks bad, the action is avoid/trim/exit.
- NO short-term / day trading. The holding horizon is DAYS-TO-WEEKS or longer. Do not propose
  trades meant to be closed within ~a couple of days; ignore intraday/scalp ideas.
- Max single-asset weight: 20% of portfolio value.
- Max single-sector weight: 35%.
- Max total crypto exposure: 10%. Standard assets only (BTC/ETH tier). No memecoins.
- No leverage. No derivative that can lose more than the premium paid.
- Minimum cash buffer: 5%.
- Max portfolio turnover per decision window: 30% of value.

## Evidence rules (anti-hallucination)
- THESE GOVERN SIZING/EXECUTION, NOT THINKING. Always ANALYZE and COMMIT a view from the
  available evidence. Never refuse to reason, never just list data gaps. The rules below
  limit how BIG a position can be, not whether you form an opinion. A single credible source
  (or a first-party market/SEC/quant datapoint) already justifies a SMALL starter.
- First-party DATA-tool output (exchange/market prices, yields, vol, macro series incl. the
  yfinance proxies, SEC filings, deterministic quant models) is TRUSTED and counts as a
  credible source on its own: it is NOT "unverified web text".
- No FULL/large position on a SINGLE source. Require >= 2 INDEPENDENT credible sources that
  corroborate each other. Credible secondary sources (reputable news, multiple
  scraped pages, several agents independently agreeing) DO count as corroboration.
  You do NOT need a "primary" source for every trade.
- Evidence strength sets SIZE, not a go/no-go gate: corroborated secondary evidence
  -> a SMALL/starter position is fine; a LARGE or CONCENTRATED position (or a single
  binary-event bet) additionally needs a PRIMARY source (filing/official/exchange).
- A claim from Reddit / Twitter / Telegram / Polymarket is a LEAD; it can motivate a
  small position only once corroborated by >= 1 independent credible source.
- Every factual input must carry a citation. Truly unverifiable claims cannot raise
  confidence. This is an ACTIVE fund: corroborated conviction should lead to action
  (buy/trim/rotate), not default holding.
- Never bet the whole thesis on a single binary event. Size for it going wrong.

## Capital deployment (don't sit idle)
- Persistent idle cash loses to inflation. Over time the portfolio should be at least
  partly INVESTED, not 100% cash for long stretches.
- BUT never deploy just to avoid cash, and never force a trade. Deploy only when the
  analysis, news, and all factors make it rational. Great research + genuine
  opportunities drive investment. Rationality and logic come first, always.
- Heavy cash is correct ONLY during real uncertainty, crash risk, or regime stress.
- Take good opportunities when they appear (including smaller/under-followed names)
  and diversify across them. A small hedge (small portion) is fine, within the limits;
  never hedge too much or run excessive volatility.

## Diversification & sizing
- Diversify across >= 5 low-correlation positions before concentrating.
- Position size via fractional Kelly, capped at 1/2 Kelly.
- Highly correlated positions count as one bet for the concentration limit.
- When several names independently clear the bar (each >= 2 verified sources, real
  edge), it is fine to open MORE THAN ONE in a cycle to spread conviction. Each is
  sized prudently within caps; do not force breadth without conviction.

## Small-cap / speculative sleeve
- Small-, micro-cap, and speculative high-risk names belong in a SMALL capped sleeve:
  tiny starter positions (a few % each), modest aggregate (target <= ~15% of the
  portfolio). High potential is paired with high risk, never a concentrated bet.
- The core stays in large, liquid, diversified holdings.

## Fees & churn (do not waste fees)
- Every buy and every sell pays a fee. Round-tripping a position in minutes/hours
  burns fees on BOTH legs and is a losing move.
- Trade with a multi-day-or-longer horizon. Do NOT trim or sell a position opened
  within the last min-hold window (default 24h) unless a stop-loss, de-risk, or a
  genuine thesis break triggers, not noise. Don't open something you expect to
  reverse within days.

## Confidence & honesty
- Confidence is a range, never false precision.
- If a critical data feed is stale or down, downgrade confidence or output
  NO_ACTION. Never trade on stale data.
- Prefer NO_ACTION over a low-conviction trade. Doing nothing is a valid day.

## Decision cadence
- The decision interval (default 24h) is a COOLDOWN CAP, not a trade mandate.
  At most one rebalance per window; then locked until the window resets.

## Learning
- Every closed position is scored against its outcome and written to lessons.
- Repeated mistakes of the same class trigger a flagged review before the
  system is allowed to re-attempt that strategy.

## Mode
- The system starts and stays in DRY mode. Live execution requires an explicit
  human switch plus confirmation. No leverage without explicit human permission.
