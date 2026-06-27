# Skill: News Analysis

How to turn a stream of news into a tradeable signal while filtering out the noise.
Most headlines are already priced or irrelevant; the job is to find the few that aren't.

1. Establish the BASELINE first. Pull `gdelt_search(query)` for tone and volume on the
   entity/theme. A spike in article volume + a tone shift is the signal; flat coverage
   with one loud headline is usually noise.
2. Broaden the read with `rss_headlines` for current flow and `web_research` /
   `web_search` to find the underlying primary event behind the coverage. You want the
   FACT, not the Nth reprint of the same wire story.
3. Separate signal from noise:
   - Is it NEW information, or a restatement of something already known and priced?
   - Is it material to fundamentals/regime, or color? (CEO quote vs guidance cut.)
   - Is the volume organic or a single source amplified across aggregators?
4. DATE-CHECK everything against the current authoritative time. GDELT and RSS surface
   old articles, recirculated anniversaries, and undated evergreen pages constantly.
   A stale headline traded as fresh is the most common news mistake — verify the
   publication date on the primary source before acting.
5. Corroborate before it counts: per house rules, a real position needs >=2 INDEPENDENT
   credible sources (different outlets/origins, not the same wire). For company-specific
   news demand a PRIMARY source — `recent_filings` / `sec_financials` for anything an
   8-K would cover. Cross-reference `reddit_hot` / `stocktwits_symbol` only to gauge
   crowd positioning, never as evidence.
6. Judge the REACTION, not just the news: price already moving against a "good" headline
   means it was priced (see earnings-analysis). Pair the news read with `price` / `history`.
7. Act: a corroborated, dated, material, not-yet-priced item sizes as a starter; size up
   only as confirmation accumulates. Record citations (source, claim, date, primary?) on
   the report. Uncited or undated -> mark UNVERIFIED, cannot raise conviction.

PITFALLS:
- Recency illusion: GDELT/RSS regularly return stale or recirculated items. Undated == untrusted.
- Volume != truth. Coordinated amplification (PR pushes, social pumps) inflates GDELT volume
  without new facts; trace back to the single origin.
- Sentiment tone from `gdelt_search` is a coarse proxy, not a verified read — directional only.
- "Buy the rumor, sell the news": by the time a story is everywhere it is usually priced.
  NO_ACTION on a loud-but-priced headline is the correct, disciplined call.
