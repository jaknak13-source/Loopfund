# Skill: Factor Investing

How to build and combine the classic equity factors — momentum, value, quality,
low-vol — into a cross-sectional ranking that tilts the book toward paid-for risk
premia rather than single-name bets.

1. Pick factors with a known premium and a reason:
   - Momentum: 12-1 month total return (skip the most recent month). From `history`.
   - Value: cheap multiples (EV/EBIT, P/B, FCF yield). From `fundamentals`/`sec_financials`.
   - Quality: high ROE/ROIC, stable margins, low leverage. From `fundamentals`.
   - Low-vol: low trailing realized volatility. From `history`.
2. Compute each raw factor per name in `run_python` over the FIXED universe (from
   `quant-strategy-design`). Keep it point-in-time: fundamentals as known then, not
   restated — restated data is silent look-ahead.
3. CROSS-SECTIONAL Z-SCORE: within each rebalance date, standardize each raw factor
   to mean 0 / std 1 across names. Winsorize extremes (e.g. clip at ±3σ) so one outlier
   doesn't dominate. Flip the sign so "good" is always positive (cheap value = high z,
   low vol = high z).
4. COMBINE: average the standardized factor z-scores into a composite (equal-weight by
   default — don't optimize weights on the same data you'll claim the result from).
   Rank names by composite; go long the top quantile, optionally short the bottom.
5. NEUTRALIZE where it matters: subtract sector means before ranking so you're not just
   long one sector. Vol-target the sleeve and size in EUR base (`fx_rate` for non-EUR).
6. Account for DECAY: factor signals fade. Momentum needs frequent rebalancing (monthly);
   value/quality are slower (quarterly). Rebalancing too often burns the edge in costs;
   too rarely lets stale signals rot. Tune cadence in `quant-backtesting`, out-of-sample.
7. Validate the composite and EACH factor standalone via `quant-backtesting` with real
   costs. A factor only enters the book if it survives OOS; corroborate the underlying
   fundamentals to the house bar before any real (dry-mode) sizing.

PITFALLS
- Factors crowd and cycle: value can underperform for years, momentum crashes hard at
  reversals. Diversify across factors and never bet the book on one.
- Look-ahead via restated fundamentals or using the latest filing for a past date — use
  point-in-time only, or flag it UNVERIFIED.
- Z-scores blow up with missing data or tiny universes; require a minimum name count and
  handle NaNs explicitly before standardizing.
- Combining correlated factors (e.g. value + low-vol) double-counts one bet — check the
  cross-factor correlation before trusting the composite.
