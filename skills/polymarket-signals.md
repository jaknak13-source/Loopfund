# Skill: Polymarket Signals

How to use prediction-market implied probabilities as a macro/event signal. The crowd
is betting real money on outcomes (rate cuts, elections, CPI prints, geopolitics) — that
priced probability, and especially its movement, is a cheap forward-looking input.

1. Pull `polymarket_markets` for the events that matter to your thesis (Fed decision,
   recession odds, election, war/escalation, regulatory outcome). Read the implied
   probability = the market's odds, in money terms.
2. The DELTA is the signal. With `run_python`, compute each market's implied probability
   THIS cycle minus LAST cycle. A sharp move (e.g. rate-cut odds 30% -> 60%) is a regime
   shift the broader market may not have fully repriced — that gap is the opportunity.
3. TRANSLATE the event into asset impact via cross-market chains:
   - rate-cut odds rising -> duration/long bonds, rate-sensitive growth, gold tailwind.
   - recession odds rising -> defensives over cyclicals, credit-spread caution.
   - election/policy outcome shifting -> sector winners/losers of that policy.
   Cross-check the macro picture with `macro_snapshot` / `fred_series` so the bet and the
   hard data agree before you act.
4. SIZE / ACT: a probability delta is a directional LEAD and a TIMING input, not a position
   by itself. Use it to (a) tilt exposure of an existing thesis, (b) flag a regime change to
   the risk agent, or (c) size a small event-driven starter once corroborated. Big binary
   event ahead with uncertain outcome = reduce size / NO_ACTION, don't gamble the binary.
5. CORROBORATE: confirm the event read with >=2 independent credible sources
   (`web_research`, `rss_headlines`, `gdelt_search`) before EUR risk. Odds are a lead.
6. Record the signal deterministically on the report: market, implied probability now,
   the cycle-over-cycle delta, liquidity/volume, the asset impact chain, and your
   confidence. Hand the risk agent a number and a chain, not "the market looks worried".

PITFALLS:
- Thin/illiquid markets give noisy odds; a few EUR can move a small market. Check volume/
  liquidity before trusting a number, and weight low-volume markets down.
- Probability != certainty: a 70% market still loses 30% of the time. Never treat it as fact.
- Resolution/wording risk: read exactly what the market resolves on and by when; ambiguous
  or far-dated questions carry little signal.
- Base currency is EUR — translate any USD-denominated asset impact via `fx_rate`; an
  FX move can swallow the edge a US-event signal implies.
