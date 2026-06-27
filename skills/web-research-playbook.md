# Skill: Web Research Playbook

How to run `web_search` / `web_fetch` / `web_research` so they produce credible,
corroborated evidence instead of SEO junk. The web is the widest source and the
easiest to be fooled by — discipline here is what separates a lead from evidence.

1. DESIGN the query. Be specific: ticker/company + the exact fact + a date qualifier
   (e.g. "ACME Q2 2026 revenue guidance"). Add `site:` or source terms to bias toward
   primary/credible domains (sec.gov, company IR, reputable wires). Vague queries return
   vague junk; run 2-3 query variants rather than one.
2. TOOL choice:
   - `web_search` to map the landscape and find candidate sources fast.
   - `web_fetch` to pull the full text of a SPECIFIC promising URL and read it directly.
   - `web_research` for a deeper multi-source sweep on a harder question.
   Pair with `rss_headlines` / `gdelt_search` for breaking-news breadth, and ALWAYS try
   the primary source (`recent_filings`, `sec_financials`) over a paraphrasing blog.
3. JUDGE source quality. Rank: primary (filings/regulator/official release) > established
   financial press > reputable secondary > anonymous blogs/forums > content farms. Check
   author, date, and whether the page actually cites its own source or just reprints a wire.
4. DODGE junk and blocks:
   - Skip SEO/content-farm and AI-spun pages; they reword each other and are not independent.
   - On a 403 / paywall / empty fetch, don't fabricate the content — try the original
     source, a different reputable outlet, or the primary filing instead. A failed fetch is
     a failed fetch; report it as missing, never invent the text.
   - Watch dates: re-running an old article as "news" is a classic trap. Date-check vs the
     current authoritative time.
5. DEMAND >=2 INDEPENDENT DOMAINS that agree before a fact backs a real EUR position.
   Independent = different origins, not the same wire syndicated across five sites — collapse
   syndicated copies to ONE source. Record each as a citation (source, claim, primary?).
6. If you cannot reach two independent credible sources, mark the claim UNVERIFIED and lower
   confidence. NO_ACTION is valid; a forced thesis on thin sourcing is worse than no trade.

PITFALLS:
- Syndication mistaken for corroboration — five reprints of one wire is ONE source.
- Trusting a headline without fetching the body; headlines overstate and mislead.
- Recency blindness: undated or old pages presented as current. Always date-check.
- Confirmation bias: searching only for what supports the thesis. Run a query designed to
  DISPROVE it too, and weigh what comes back honestly.
