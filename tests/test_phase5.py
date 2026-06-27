"""Phase 5: ledger accounting, P&L reconciliation, risk caps, dry execution."""

from __future__ import annotations

import math
from datetime import date

import pytest

from core.blackboard import Blackboard
from execution.dry import DryExecution
from execution.portfolio import Portfolio, Position, PortfolioStore
from execution.risk_guard import validate_buy
from execution.sim_ledger import SimLedger
from schemas import Confidence, PortfolioDecision, TradeAction
from tools.registry import ToolRegistry


def _ledger(tmp_path, cash=1000.0) -> SimLedger:
    store = PortfolioStore(path=tmp_path / "pf.json")
    return SimLedger(Portfolio(cash_eur=cash), store=store)


def test_buy_sell_accounting_eur(tmp_path) -> None:
    # Your NVDA example in EUR: start 100, buy 1 @50 (fee 1), sell @60 (fee 1).
    led = _ledger(tmp_path, cash=100.0)
    led.buy("d1", "NVDA", qty=1, price_native=50.0, ccy="EUR", fx_rate=1.0)
    assert math.isclose(led.p.cash_eur, 49.0)  # 100 - 50 - 1
    led.sell("d1", "NVDA", qty=1, price_native=60.0, ccy="EUR", fx_rate=1.0)
    assert math.isclose(led.p.cash_eur, 108.0)  # 49 + 60 - 1
    assert math.isclose(led.p.realized_pnl_eur, 8.0)  # 10 gain - 2 fees
    assert "NVDA" not in led.p.positions


def test_pnl_reconciles(tmp_path) -> None:
    led = _ledger(tmp_path, cash=1000.0)
    led.buy("d1", "AAA", qty=10, price_native=20.0, ccy="EUR", fx_rate=1.0)
    snap = led.mark_to_market({"AAA": 25.0})
    # total == starting + realized + unrealized
    assert math.isclose(
        snap["total_value_eur"], 1000.0 + snap["realized_pnl_eur"] + snap["unrealized_pnl_eur"], abs_tol=0.01
    )


def test_buy_rejected_insufficient_cash(tmp_path) -> None:
    led = _ledger(tmp_path, cash=10.0)
    t = led.buy("d1", "AAA", qty=10, price_native=20.0, ccy="EUR", fx_rate=1.0)
    assert t.status == "rejected"
    assert led.p.cash_eur == 10.0


def test_risk_guard_blocks_concentration() -> None:
    p = Portfolio(cash_eur=850.0, positions={"AAA": Position("AAA", qty=1, avg_cost_eur=150.0, ccy="EUR")})
    prices = {"AAA": 150.0}  # total = 850 + 150 = 1000
    ok, reason = validate_buy(p, "AAA", eur_amount=100.0, fee_eur=1.0, prices_eur=prices)
    assert not ok and "single-asset" in reason


@pytest.mark.asyncio
async def test_dry_execution_buys_to_target_weight(tmp_path) -> None:
    bb = Blackboard(path=tmp_path / "t.db")
    led = SimLedger(Portfolio(cash_eur=1000.0), store=PortfolioStore(path=tmp_path / "pf.json"), blackboard=bb)
    reg = ToolRegistry(bb)

    async def _price(**kw):
        return {"ticker": kw["ticker"], "price": 100.0, "ccy": "EUR", "stale": False}

    async def _fx(**kw):
        return {"rate": 1.0, "base": kw.get("base"), "quote": "EUR", "stale": False}

    reg.register("price", _price)
    reg.register("fx_rate", _fx)

    dx = DryExecution(reg, led)
    decision = PortfolioDecision(
        id="dec1", decision_date=date.today(), action=TradeAction.BUY, asset="AAA",
        target_weight=0.15, reasoning="test",
        confidence=Confidence(score=0.7, low=0.6, high=0.8),
    )
    trade = await dx.execute(decision)
    assert trade is not None and trade.status in ("filled", "closed")
    # target 0.15 * 1000 = 150 EUR / 100 = 1.5 shares
    assert math.isclose(led.p.positions["AAA"].qty, 1.5, abs_tol=1e-3)
    # realized weight stays within the hard cap
    w = led.p.weights({"AAA": 100.0})
    assert w["AAA"] <= 0.20 + 1e-9
