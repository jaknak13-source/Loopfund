# Skill: Sentiment & Social Playbook

How to quantify crowd sentiment from social feeds and use it as a LEAD, never as
evidence for a position. Social tells you what the crowd already thinks; it does not
tell you what is true.

1. Pull `reddit_hot` (subreddit-level chatter) and `stocktwits_symbol(ticker)` for the
   name. Read them as a sample of crowd positioning, not as fact.
2. Quantify deterministically — don't eyeball "vibes". With `run_python`, compute:
   - bull/bear ratio (StockTwits sentiment tags), post/mention COUNT, and the
     cycle-over-cycle DELTA in mention volume (this cycle vs last).
   - It is the delta and acceleration that carry signal, not the absolute level.
3. HYPE / MANIPULATION flags — discount or invert the signal when you see:
   - mention volume spiking with no corroborating filing or news (pump pattern),
   - uniform copy-paste bullishness, rocket/"to the moon" ramp, brand-new accounts,
   - a low-float / micro-cap being coordinated, or sentiment that flipped overnight.
   Flag these explicitly on the report; a coordinated ramp is a fade candidate, not a buy.
4. CONTRARIAN vs CONFIRMING use:
   - Extreme one-sided euphoria near a high = contrarian caution (crowd is the exit liquidity).
   - Capitulation/disgust on a fundamentally sound name = contrarian interest.
   - Rising-but-not-euphoric sentiment that CONFIRMS an independent fundamental thesis =
     mild tailwind on timing only. Sentiment can confirm a thesis you already have; it
     cannot originate one.
5. ACT: a social signal alone is NO_ACTION on size. It can (a) surface a name to research,
   (b) adjust TIMING/entry of a thesis already supported by >=2 independent credible
   sources, or (c) justify a fade of an obvious pump. Real position size still comes from
   fundamentals + valuation, not upvotes.
6. Always route any social-sourced name through evidence-verification before sizing:
   demand a primary or independent source (`recent_filings`, `web_research`) before EUR risk.

PITFALLS:
- Treating mention count as a price prediction. Volume of talk != direction of price.
- Survivorship/sampling bias: these feeds over-represent retail longs and momentum names.
- Stale snapshots — date-check the feed; yesterday's euphoria may already be unwinding.
- Free-data limits: coverage is thin/absent for small or non-US tickers; absence of
  chatter is not a bearish signal, just missing data. Say so rather than inventing a read.
