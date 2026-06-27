# Skill: Geopolitics Analysis

How to map a geopolitical event into its commodity, sector, and FX impact chains and
the second-order effects the crowd hasn't priced. The first-order move is usually
already in; the edge is downstream.

1. Pin down the EVENT and its facts first: conflict, sanctions, embargo, blockade,
   coup, election shock, supply-route disruption. Use `gdelt_search` (volume/tone),
   `rss_headlines`, and `web_research` to establish what actually happened and WHEN.
   Date-check against current authoritative time — geopolitical feeds recirculate
   old crises constantly.
2. Identify the CHOKEPOINT or exposure: what physical or financial flow does this
   threaten? (Strait of Hormuz -> oil; Black Sea -> grain/fertilizer; Taiwan -> advanced
   chips; Russia -> gas/palladium/uranium; Red Sea -> shipping/freight rates.)
3. Walk the impact chain link by link (ties to cross-market-chains):
   event -> commodity that re-prices -> sector that uses or produces it -> the FX of the
   exposed economy. Example: Middle East escalation -> oil spike -> energy producers up,
   airlines/transports down -> oil-importer currencies weaken. Convert any USD-commodity
   view to our EUR base with `fx_rate`.
4. Map the SECOND-ORDER effects explicitly — that's where the un-priced edge is:
   - Substitution: blocked supply -> alternative supplier/region benefits (LNG when
     pipeline gas is cut; non-Russian uranium; reshored chip capacity).
   - Defense/security: sustained conflict -> defense procurement, cyber, border tech.
   - Inflation feed-through: energy/food spike -> CPI -> central-bank reaction -> rates/FX
     (hand the rate/regime read to macro-regime-playbook).
5. For EACH link state confidence + what confirms or breaks it. A long chain is low
   confidence; the first link (commodity) is usually already priced within hours, so
   target the durable downstream beneficiary, not the obvious headline trade.
6. Corroborate before sizing: >=2 independent credible sources for the event, primary
   where possible (official statements, sanctions lists). Size SMALL — geopolitics is
   noisy, headline-driven, and mean-reverts on de-escalation. Define the invalidation
   (ceasefire, route reopens) up front.

PITFALLS:
- The obvious first-order trade (oil up on Mideast news) is priced in minutes; chasing it
  buys the spike. Find the lagging downstream/substitution beneficiary instead.
- Geopolitical events whipsaw on de-escalation rumors. A position can be right on thesis
  and wrong on timing — keep size small and don't average into noise.
- No live event/intel feed beyond free GDELT/RSS/web; coverage is lagged and incomplete.
  Treat early reports as untrusted leads until corroborated.
- Don't overfit a 4-link causal story. The more hops, the lower the confidence; NO_ACTION
  on a speculative chain beats a confident fiction. Deterministic linkage over narrative.
