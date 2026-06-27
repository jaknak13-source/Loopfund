"""Phase-1.8 honest benchmark: weekly cash top-ups must not be counted as returns.

The old code divided portfolio value by a FIXED inception base while top-ups were
added to cash, so 'beating_sp500' inflated ~10%/week regardless of skill. The
benchmark must be contribution-adjusted: each top-up raises the invested base AND
buys notional SPY, so a pure-cash topped-up portfolio reports no positive excess.
"""

from __future__ import annotations


def test_pure_cash_topup_is_not_beating_sp500(tmp_path):
    from memory.learning import LearningStore
    ls = LearningStore(path=tmp_path / "l.json")
    ls.ensure_inception(spy_entry_eur=600.0, start_value_eur=1000.0)
    ls.record_contribution(amount_eur=100.0, spy_price_eur=600.0)
    # pure cash: value = 1000 start + 100 top-up = 1100, zero investment gains. SPY flat.
    bench = ls.benchmark(spy_now_eur=600.0, portfolio_value_eur=1100.0)
    assert bench["available"] is True
    assert abs(bench["strategy_return"]) < 0.01     # cash didn't grow -> ~0, not +10%
    assert bench["excess_return"] <= 0.01           # NOT spuriously positive
    assert bench["beating_sp500"] is False


def test_pure_cash_lags_when_spy_rises(tmp_path):
    from memory.learning import LearningStore
    ls = LearningStore(path=tmp_path / "l.json")
    ls.ensure_inception(spy_entry_eur=600.0, start_value_eur=1000.0)
    ls.record_contribution(amount_eur=100.0, spy_price_eur=600.0)
    # SPY +10%; pure cash still 1100 -> cash must lag SPY.
    bench = ls.benchmark(spy_now_eur=660.0, portfolio_value_eur=1100.0)
    assert abs(bench["sp500_return"] - 0.10) < 0.01
    assert abs(bench["strategy_return"]) < 0.01
    assert bench["excess_return"] < 0.0
    assert bench["beating_sp500"] is False


def test_migration_backfills_pretledger_topup(tmp_path, monkeypatch):
    """Bug fix: an old state file (a top-up already applied, but no contributions ledger)
    must be migrated so the topup isn't counted as strategy return."""
    import json
    from datetime import datetime, timezone
    import memory.learning as learning

    monkeypatch.setattr(learning, "settings", lambda: {"portfolio": {"weekly_topup": 100.0}}, raising=False)
    # pre-ledger file: inception + a top-up fired (last_topup_iso) but NO contributions key
    old = {
        "inception": {"date": datetime(2026, 6, 18, tzinfo=timezone.utc).isoformat(),
                      "start_value_eur": 1000.0, "spy_entry_eur": 600.0},
        "weekly": {"last_topup_iso": datetime(2026, 6, 18, tzinfo=timezone.utc).isoformat()},
        "invested_capital_eur": 1000.0, "spy_units": 1000.0 / 600.0,
        "pending": [], "agent_tally": {}, "source_tally": {}, "metrics": {},
    }
    p = tmp_path / "learning.json"
    p.write_text(json.dumps(old), encoding="utf-8")
    ls = learning.LearningStore(path=p)
    # cash now 1100 (1000 start + 100 topup), pure cash, SPY flat -> must NOT be beating
    bench = ls.benchmark(spy_now_eur=600.0, portfolio_value_eur=1100.0)
    assert abs(bench["strategy_return"]) < 0.01   # not inflated ~10%
    assert bench["beating_sp500"] is False
    assert abs(bench["invested_capital_eur"] - 1100.0) < 1e-6


def test_real_outperformance_still_registers(tmp_path):
    from memory.learning import LearningStore
    ls = LearningStore(path=tmp_path / "l.json")
    ls.ensure_inception(spy_entry_eur=600.0, start_value_eur=1000.0)
    ls.record_contribution(amount_eur=100.0, spy_price_eur=600.0)
    # invested base 1100; portfolio grew to 1300 (+18%) while SPY flat -> genuinely beating.
    bench = ls.benchmark(spy_now_eur=600.0, portfolio_value_eur=1300.0)
    assert bench["strategy_return"] > 0.15
    assert bench["excess_return"] > 0.15
    assert bench["beating_sp500"] is True
