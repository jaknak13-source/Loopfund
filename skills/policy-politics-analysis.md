# Skill: Policy & Politics Analysis

How to turn policy, regulation, and elections into sector impact, using market-implied
odds and disclosed insider activity instead of pundit guesswork. The edge is pricing the
PROBABILITY and the affected sector before the policy is law.

1. Identify the policy event: pending legislation, regulatory ruling, central-bank/agency
   action, tariff, subsidy, or election. Establish facts and timeline with `web_research`,
   `rss_headlines`, and `gdelt_search`. Date-check — bills get reintroduced and old
   rulings recirculate; confirm the CURRENT status against authoritative time.
2. Get the market-implied PROBABILITY, not your opinion: `polymarket_markets` for the
   relevant contract (election outcome, "will X pass by date", confirmation, rate decision).
   Read the odds AND the trend — a contract moving from 30% to 60% is the signal. This is
   a deterministic number; prefer it over narrative confidence.
3. Cross-check disclosed smart money with `congress_trades`: legislators trading a sector
   ahead of relevant committee action is a corroborating tell (a lead, not proof). Pair
   with `insider_transactions` / `recent_filings` for corporate insiders in exposed names.
4. Map policy -> sector impact chain (winners AND losers):
   - Subsidy/industrial policy (IRA-style) -> clean energy, semis, domestic manufacturing up.
   - Tariffs -> protected domestics up, import-reliant retailers/autos down, FX feed-through.
   - Regulation/antitrust -> targeted incumbents down, compliant/alternative players up.
   - Rate/fiscal policy -> hand the rates/FX read to macro-regime-playbook.
   - Healthcare/drug-pricing -> pharma, PBMs, insurers re-rate.
5. Size on PROBABILITY x IMPACT x how-priced: a high-odds, high-impact, not-yet-priced
   policy justifies a real position; a coin-flip vote or already-priced outcome sizes tiny
   or NO_ACTION. Don't bet the binary outcome of a close vote — bet the asymmetric, durable
   sector effect with a defined invalidation (bill dies, ruling reversed).
6. Corroborate per house rules: >=2 independent credible sources for the policy facts,
   primary where it matters (official text, agency release, vote record). Record citations
   with dates. Uncited -> UNVERIFIED, cannot raise conviction.

PITFALLS:
- Polymarket odds can be thin/illiquid, US-centric, and slow to update on real news — treat
  a low-volume market's price as a weak signal, and don't trade the contract itself for us
  (dry-mode equity book, EUR base; use the odds only as an input).
- `congress_trades` and `insider_transactions` are DISCLOSURE-LAGGED (often weeks); they
  corroborate a thesis, they don't time an entry. Never treat them as front-running signal.
- Policy timelines slip and bills die in committee — "will pass eventually" is not a catalyst
  with a date. Require a near-term trigger or size for patience.
- Don't let political priors become the thesis. Read the implied odds and the disclosed flow;
  deterministic evidence over how you think the vote should go.
