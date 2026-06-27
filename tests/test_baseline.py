"""Passive core allocation + ETF-aware concentration cap."""

from __future__ import annotations

import pytest

from execution.risk_guard import cap_for
from tests.helpers import build_offline_orchestrator


def test_cap_for_etf_vs_stock() -> None:
    assert cap_for("SPY") == 0.50    # broad ETF -> higher cap
    assert cap_for("AAPL") == 0.20   # single stock -> tight cap


@pytest.mark.asyncio
async def test_baseline_deploys_idle_cash(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)  # 1000 EUR cash, fake price=100 for any ticker
    # first deploy step toward the core (SPY is the biggest gap)
    trade = await orch._maybe_baseline()
    assert trade is not None and trade.status in ("filled", "closed")
    assert trade.asset == "SPY"
    assert "SPY" in orch.ledger.p.positions
    w1 = orch.ledger.p.weights({"SPY": 100.0}).get("SPY", 0.0)
    assert 0.05 < w1 <= 0.20  # ~one 10% step in toward the (light) SPY anchor

    # second step deploys further toward the SPY target, capped by the ETF cap
    await orch._maybe_baseline()
    w2 = orch.ledger.p.weights({"SPY": 100.0}).get("SPY", 0.0)
    assert w2 >= w1
    assert w2 <= 0.50 + 1e-9  # never exceeds the broad-ETF cap
