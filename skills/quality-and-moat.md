# Skill: Quality and Moat

How to judge whether a business is actually good and whether its advantage lasts —
read from the figures, not the story. Quality is what lets you hold through noise.

1. Pull `fundamentals(ticker)` for margins, returns, and leverage, and
   `sec_financials(ticker)` for multi-year history. One year tells you nothing;
   you want the TREND and the consistency across a cycle (>= 3-5 years).
2. Returns on capital are the headline test: ROIC, ROE, ROA. A business that
   sustainably earns returns well above its cost of capital (see WACC in
   financial-modeling) is creating value. Below it, growth destroys value.
3. Margins reveal pricing power: stable or rising gross margins through inflation and
   competition signal a moat; margins that crumble when the cycle turns signal a
   commodity. Compare to peers via the comparables-analysis skill.
4. Capital intensity and cash conversion: does reported profit turn into free cash
   flow, or get eaten by capex and working capital? High, durable FCF conversion is a
   quality marker; a persistent net-income vs operating-cash-flow gap is a red flag.
5. Balance-sheet durability: modest leverage, comfortable interest coverage, and no
   refinancing cliff. A great franchise with a fragile balance sheet can still go to
   zero. Check debt maturities in the filings (reading-sec-filings).
6. Name the moat and find it in the numbers: brand/pricing power -> margins; network
   effects/switching costs -> stable share and high retention; scale -> cost
   advantage; regulatory/IP -> durability. If you can't point to the figure that
   proves it, you don't have a moat, you have a hope.
7. Test DURABILITY: is the advantage widening or eroding? Use `web_research` /
   `rss_headlines` for competitive and disruption signals, but anchor the verdict to
   whether returns on capital are holding up over time.
8. Tie quality to action: high quality justifies paying up a bit and holding longer;
   low quality demands a bigger margin of safety and a tighter leash.

PITFALLS
- High ROE driven by leverage, not operating excellence — decompose it (DuPont) before
  calling it quality. Buybacks can flatter per-share metrics while the business stalls.
- One good year is not a moat. Mean-reverting margins and returns fool the impatient;
  insist on consistency across a downturn.
- Narrative moats with no numerical footprint ("great brand", "loved product") that
  never show up in margins, retention, or returns. If the figures don't confirm it,
  discount the story.
- Free-data limits: no live churn/retention or unit-economics feed and segment detail
  can be thin — infer carefully and mark soft conclusions UNVERIFIED. Corroborate with
  >= 2 independent sources before a real position; NO_ACTION is valid when quality is
  ambiguous.
