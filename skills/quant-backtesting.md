# Skill: Quant Backtesting

How to backtest a strategy honestly with `run_python` over `history`, so the result
predicts the future instead of flattering the past. Most backtests lie; your job is
to make this one fail if the edge isn't real.

1. PULL data with `history` for the full fixed universe and date range. Inspect for
   gaps, splits, and missing names. Reconstruct point-in-time membership where you can —
   testing only today's survivors is survivorship bias and inflates every result.
2. In `run_python`, build the signal and trades with a strict TIME RULE: a signal
   computed from data up to close of day T may only trade at T+1's open/close. Never
   let a row see its own future. Lag every input explicitly; this kills look-ahead,
   the single most common bug.
3. Apply REALISTIC costs: commission + spread + slippage per trade (model slippage as a
   function of size vs typical volume, not a flat 0). For EUR base, convert via
   `fx_rate`. If the edge only survives at zero cost, it does not exist.
4. WALK-FORWARD / out-of-sample: split the timeline. Fit/choose any parameter on the
   in-sample window ONLY, then measure on the untouched out-of-sample window. Report the
   OOS numbers — in-sample Sharpe is marketing, not evidence.
5. Compute deterministic stats in `run_python`: CAGR, Sharpe, Sortino, max drawdown,
   hit rate, turnover, exposure. Plot/inspect the equity curve and the WORST drawdown
   period — a smooth curve with one cliff is a red flag, not a triumph.
6. REJECT implausible results: an OOS Sharpe > ~2 on daily free data, a curve with no
   losing months, or an edge that evaporates with one parameter nudge means look-ahead,
   overfit, or a data bug. Hunt the bug before you believe the number.
7. Stress it: vary the parameter ±20%, shift the start date, drop the best month, add
   one extra day of execution lag. A robust edge degrades gracefully; a fragile one
   collapses. Only a strategy that survives all four earns a (small, dry-mode) allocation.

PITFALLS
- Look-ahead via unlagged signals, restated fundamentals, or using close to trade at
  that same close — assume guilty until the lag is proven.
- Survivorship: delisted/merged names silently dropped from `history` make losers
  disappear. State this limitation explicitly when data can't be reconstructed.
- Overfitting: many parameters + one tested period = a story about noise. Fewer knobs,
  more out-of-sample, report the degradation curve.
- False precision from one path: report a range and the drawdown, not a single Sharpe.
  If you can't corroborate the data, mark the result UNVERIFIED and do not size on it.
