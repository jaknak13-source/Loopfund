"""Risk governor: drawdown tiers, buy gating, stop-loss, and de-risk in a cycle."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from execution import risk_governor as rg
from execution.portfolio import Portfolio, Position
from tests.helpers import build_offline_orchestrator


def test_drawdown_tiers() -> None:
    marks = {"hwm": 1000.0, "day_date": "x", "day_start_equity": 1000.0}
    assert rg.assess(990.0, marks)["state"] == rg.NORMAL      # -1%
    assert rg.assess(910.0, marks)["state"] == rg.REDUCE      # -9% (> soft 8%)
    assert rg.assess(800.0, marks)["state"] == rg.DERISK      # -20% (> hard 15%)


def test_daily_loss_triggers_reduce() -> None:
    marks = {"hwm": 1000.0, "day_date": "x", "day_start_equity": 1000.0}
    # only 3% off peak but down 7% on the day -> reduce
    assert rg.assess(930.0, marks)["state"] == rg.REDUCE


def test_allow_buy_by_state() -> None:
    assert rg.allow_buy("AAPL", rg.NORMAL) is True
    assert rg.allow_buy("AAPL", rg.REDUCE) is False   # single stock blocked
    assert rg.allow_buy("SPY", rg.REDUCE) is True     # ETF core still allowed
    assert rg.allow_buy("SPY", rg.DERISK) is False    # nothing in de-risk


def test_stop_loss_hits() -> None:
    p = Portfolio(cash_eur=0.0, positions={
        "AAA": Position("AAA", qty=1, avg_cost_eur=100.0, ccy="EUR"),
        "BBB": Position("BBB", qty=1, avg_cost_eur=100.0, ccy="EUR"),
    })
    hits = rg.stop_loss_hits(p, {"AAA": 78.0, "BBB": 95.0})  # AAA -22% past 20% stop
    assert hits == ["AAA"]


def test_non_core_positions() -> None:
    p = Portfolio(cash_eur=0.0, positions={
        "SPY": Position("SPY", 1, 100.0), "NVDA": Position("NVDA", 1, 100.0)})
    assert rg.non_core_positions(p) == ["NVDA"]  # SPY is core ETF


@pytest.mark.asyncio
async def test_cycle_derisk_blocks_buys(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    today = datetime.now(timezone.utc).date().isoformat()
    # inject a high-water mark far above current equity -> deep drawdown -> de-risk
    orch._state["marks"] = {"hwm": 2000.0, "day_date": today, "day_start_equity": 2000.0}
    orch._save_state()

    result = await orch.run_cycle("c1")
    assert result["risk"]["state"] == rg.DERISK
    # buy decision must be blocked, baseline skipped -> stayed in cash
    assert result["executed_trade_id"] is None
    assert "NVDA" not in orch.ledger.p.positions
