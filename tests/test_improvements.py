"""Phase-5 improvements: anti-churn guard, multi-buy validation, NO_ACTION back-off."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from schemas import SimulatedTrade
from tests.helpers import build_offline_orchestrator


def _buy_trade(asset: str, when: datetime) -> SimulatedTrade:
    return SimulatedTrade(
        id=str(uuid.uuid4()), decision_id="d", placed_at=when, asset=asset, side="buy",
        qty=1.0, ccy="USD", price_native=100.0, fees_eur=1.0, status="filled",
    )


def test_churn_blocked_within_min_hold(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    orch.bb.write_trade(_buy_trade("NVDA", datetime.now(timezone.utc) - timedelta(hours=2)))
    assert orch._churn_blocked("NVDA") is True            # bought 2h ago, min_hold 24h
    assert orch._hours_since_last_buy("NVDA") < 24


def test_churn_allowed_after_min_hold(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    orch.bb.write_trade(_buy_trade("NVDA", datetime.now(timezone.utc) - timedelta(hours=48)))
    assert orch._churn_blocked("NVDA") is False           # held 48h > 24h window


def test_churn_not_blocked_when_never_bought(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    assert orch._churn_blocked("TSLA") is False
    assert orch._hours_since_last_buy("TSLA") is None


def test_no_action_backoff_stretches_decision_gap(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    # last decision 0.6h ago; reminder_hours=1 -> base gap 0.5h
    orch._state["last_decision_iso"] = (datetime.now(timezone.utc) - timedelta(hours=0.6)).isoformat()
    orch._state["consecutive_no_action"] = 0
    assert orch.decision_due() is True                    # 0.6h >= 0.5h base
    orch._state["consecutive_no_action"] = 4              # backoff -> 0.5h * 5 = 2.5h
    assert orch.decision_due() is False                   # 0.6h < 2.5h -> research more


def test_validate_additional_buys_filters_uncorroborated(tmp_path):
    orch = build_offline_orchestrator(tmp_path)
    agg = {"corroboration": {"AAPL": 3, "MSFT": 2, "PENNY": 1}}
    parsed = {"additional_buys": [
        {"asset": "AAPL", "target_weight": 0.1, "reasoning": "strong"},   # ok (3 sources)
        {"asset": "MSFT", "target_weight": 0.08, "reasoning": "ok"},      # ok (2 sources)
        {"asset": "PENNY", "target_weight": 0.1, "reasoning": "hype"},    # dropped (<2)
        {"asset": "NVDA", "target_weight": 0.1, "reasoning": "primary"},  # dropped (== primary)
    ]}
    out = orch.decision._validate_additional_buys(parsed, agg, primary_asset="NVDA", holdings={})
    names = {b["asset"] for b in out}
    assert names == {"AAPL", "MSFT"}
    assert all(b["target_weight"] <= 0.20 for b in out)   # capped at single-asset cap


def test_memory_dedup_skips_identical_thesis(tmp_path):
    import uuid
    from datetime import datetime, timezone

    from schemas import MemoryEntry
    orch = build_offline_orchestrator(tmp_path)
    before = orch.rag.size()

    def entry():
        return MemoryEntry(
            id=str(uuid.uuid4()), created_at=datetime.now(timezone.utc), kind="research",
            title="Developing thesis: QQQ", body="QQQ looks strong on momentum.", assets=["QQQ"], tags=["t"])

    orch.rag.add(entry())
    orch.rag.add(entry())            # identical title+body -> deduped
    orch.rag.add(entry())
    assert orch.rag.size() == before + 1


def test_fee_guard_skips_tiny_trade_executes_normal(tmp_path):
    import asyncio
    import uuid
    from datetime import date, datetime, timezone

    from schemas import Confidence, PortfolioDecision, TradeAction
    orch = build_offline_orchestrator(tmp_path, cash=1000.0)

    def buy(weight):
        return PortfolioDecision(
            id=str(uuid.uuid4()), decision_date=date.today(), created_at=datetime.now(timezone.utc),
            action=TradeAction.BUY, asset="NVDA", target_weight=weight, reasoning="t",
            confidence=Confidence(score=0.7, low=0.6, high=0.8, rationale="r"), mode="dry")

    # ~0.2% notional (~2 EUR) -> flat ~1 EUR fee is >>1.5% -> skipped
    tiny = asyncio.run(orch.execution.execute(buy(0.002)))
    assert tiny is None
    # ~18% notional (~180 EUR) -> fee well under 1.5% -> executes
    normal = asyncio.run(orch.execution.execute(buy(0.18)))
    assert normal is not None and normal.asset == "NVDA"
