# Skill: Risk Management Playbook

How to protect capital BEFORE chasing return. Sizing, stops, drawdown tiers,
concentration and tail risk. Capital preservation is the first job; a position
you can't survive being wrong on is too big.

1. Size by RISK, not conviction alone: decide max loss per position (e.g. 0.5-1%
   of NAV) and back out share count from the entry-to-stop distance. Wider stop ->
   smaller size. Use `price` + `history` to set a stop at a level the thesis breaks,
   not a round number.
2. Volatility-adjust: pull `history` and compute realized vol with `run_python`
   (deterministic number, not a vibe). High-vol names get a smaller notional so each
   position contributes similar risk.
3. Define the FALSIFIER and stop together: the price/fact that proves you wrong is
   the stop. If hit, exit — no averaging down on a broken thesis.
4. Concentration caps: single name <= a fixed % of NAV; cap exposure per sector and
   per shared driver. Two "different" names that both depend on AI capex are one bet.
5. Correlation: use `run_python` on `history` to check pairwise correlation before
   adding. Stacking correlated longs is hidden leverage; size the cluster as one.
6. Drawdown tiers (RiskGovernor automates the hard ones, reason ahead of it):
   - mild DD -> stop adding, tighten stops;
   - moderate DD -> cut gross, trim high-beta/illiquid, raise cash;
   - severe DD -> de-risk to defensive, protect capital, opportunities come later.
   Cross-reference crash-warning-signs for regime context.
7. Tail risk: ask what a 3-sigma move does to the book. Watch `fred_series`
   (spreads, rates), `macro_snapshot` and `gdelt_search` for shocks. Avoid clustering
   binary events (earnings dates, FDA, elections, `polymarket_markets` odds).
8. Liquidity: thin/small-cap names need smaller size and wider mental stops — you
   can't exit at the screen price under stress.
9. NO_ACTION is a valid risk decision. When risk is unclear or evidence is thin,
   holding cash IS managing risk. Dry-mode, EUR base — `fx_rate` for non-EUR names so
   sizing and stops are in true base currency.

PITFALLS:
- No live options/IV feed and free-data limits: treat any implied-vol or hedge
  pricing as estimate, label it, don't size off false precision.
- Stops in a non-EUR currency: an FX move can blow your loss budget even if the
  stock didn't move — always risk-budget in EUR.
- Correlation looks low until a crisis, when everything goes to 1. Stress the book
  assuming correlations spike, not the calm-market number.
- Moving a stop to avoid taking a loss is not risk management — it's the loss
  getting bigger. The stop is set when you enter, for a reason.
