# Skill: Valuation Playbook

How to judge whether a stock is cheap or expensive. Use the `estimate_fair_value`
tool for the numbers, then apply judgment.

1. Pull `estimate_fair_value(ticker)` — gives DCF, multiples, blended fair value,
   upside %, and the price-implied growth rate.
2. Sanity-check the inputs (the tool returns them): is the growth assumption
   reasonable vs the company's history and industry? Is the discount rate right for
   the risk? Garbage in -> garbage fair value.
3. Reverse-DCF check: is the market's `price_implied_growth` plausible? If the price
   requires heroic growth, it's expensive; if it implies decline for a healthy
   grower, it may be cheap.
4. Cross-check with multiples vs peers and the company's own history.
5. Demand a MARGIN OF SAFETY: only treat as a buy if blended fair value is
   meaningfully (e.g. >20%) above price, and the thesis is corroborated.
6. State the bull and bear value scenarios (growth +/-) — never a single false-
   precision number. Size the position by conviction AND margin of safety.
7. Valuation is necessary, not sufficient: pair with catalyst/timing (see
   earnings-analysis) — cheap can stay cheap without a catalyst.
