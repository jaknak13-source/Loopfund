"""Phase-1.9 observability: the activity feed + structured why-no-trade that back
the dashboard 'Mind' tab."""

from __future__ import annotations

from datetime import datetime, timezone

from schemas import ActivityEvent


def _ev(agent, kind, title, cycle="c1"):
    return ActivityEvent(id=f"{agent}-{kind}-{title}", ts=datetime.now(timezone.utc),
                         cycle_id=cycle, agent=agent, kind=kind, title=title, summary="s")


def test_blackboard_write_and_filter_activity(tmp_path):
    from core.blackboard import Blackboard
    bb = Blackboard(path=tmp_path / "t.db")
    bb.write_activity(_ev("MacroAgent", "thinking", "macro read"))
    bb.write_activity(_ev("QuantAgent", "thinking", "quant read"))
    bb.write_activity(_ev("QuantAgent", "status", "running"))

    assert len(bb.latest_activity(limit=10)) == 3
    assert len(bb.latest_activity(agent="QuantAgent")) == 2
    assert len(bb.latest_activity(kind="thinking")) == 2
    assert len(bb.latest_activity(agent="QuantAgent", kind="status")) == 1


def test_activity_search(tmp_path):
    from core.blackboard import Blackboard
    bb = Blackboard(path=tmp_path / "t.db")
    bb.write_activity(ActivityEvent(id="1", ts=datetime.now(timezone.utc), agent="A",
                                    kind="research", title="NVDA datacenter demand", summary="GPU capex"))
    bb.write_activity(ActivityEvent(id="2", ts=datetime.now(timezone.utc), agent="B",
                                    kind="research", title="gold safe haven", summary="rates"))
    hits = bb.latest_activity(q="nvda")
    assert len(hits) == 1 and hits[0].title.startswith("NVDA")
    hits2 = bb.latest_activity(q="capex")  # search matches summary too
    assert len(hits2) == 1


def test_activity_prune(tmp_path):
    from core.blackboard import Blackboard
    bb = Blackboard(path=tmp_path / "t.db")
    for i in range(20):
        bb.write_activity(ActivityEvent(id=f"e{i:03d}", ts=datetime.now(timezone.utc),
                                        agent="A", kind="status", title=f"t{i}"))
    bb.store.prune_table("activity", keep=5)
    assert len(bb.latest_activity(limit=100)) == 5


# --- structured why-no-trade ---

def _agg():
    return {"per_asset": {}, "corroboration": {}, "top_long": None, "market_signal": 0.0}


def _da():
    from agents.decision import DecisionAgent

    class _BB:
        def reports_for_cycle(self, _c):
            return []

    da = DecisionAgent.__new__(DecisionAgent)
    da.bb = _BB()
    da.priors = None
    return da


def test_block_reason_risk_veto():
    da = _da()
    parsed = {"action": "buy", "asset": "TSLA", "target_weight": 0.1,
              "confidence": {"score": 0.6, "low": 0.5, "high": 0.7, "rationale": "r"}}
    dec = da._finalize("c1", parsed, _agg(), "bad. VERDICT: REJECT", "dry")
    assert dec.action.value == "no_action"
    assert dec.block_reason == "risk_veto"


def test_block_reason_below_floor():
    da = _da()
    parsed = {"action": "buy", "asset": "TSLA", "target_weight": 0.1,
              "confidence": {"score": 0.2, "low": 0.1, "high": 0.3, "rationale": "r"}}
    dec = da._finalize("c1", parsed, _agg(), "ok. VERDICT: ACCEPT", "dry")
    assert dec.action.value == "no_action"
    assert dec.block_reason == "below_floor"


def test_block_reason_no_structured_output():
    da = _da()
    dec = da._finalize("c1", None, _agg(), "VERDICT: ACCEPT", "dry")
    assert dec.block_reason == "no_structured_output"


def test_decisions_have_distinct_precise_timestamps(tmp_path):
    """Regression: decision_date is date-only, so the log showed the SAME time for every
    same-day decision. created_at must be a precise datetime and drive ordering."""
    from datetime import date, datetime, timedelta, timezone

    from core.blackboard import Blackboard
    from schemas import Confidence, PortfolioDecision, TradeAction

    bb = Blackboard(path=tmp_path / "d.db")
    today = date(2026, 6, 18)
    base = datetime(2026, 6, 18, 10, 0, 0, tzinfo=timezone.utc)
    for i in range(3):
        bb.write_decision(PortfolioDecision(
            id=f"d{i}", decision_date=today, created_at=base + timedelta(minutes=17 * i),
            action=TradeAction.NO_ACTION, reasoning="r",
            confidence=Confidence(score=0.3, low=0.2, high=0.4)))

    got = bb.latest_decisions(10)
    times = [d.created_at for d in got]
    assert len(set(times)) == 3              # distinct timestamps, not all-identical
    assert times == sorted(times, reverse=True)  # newest first, precise ordering
    assert times[0].hour == 10 and times[0].minute == 34  # real time-of-day preserved


def test_decision_created_at_falls_back_to_date_when_missing():
    """A record without created_at (older rows) falls back to its decision_date —
    NOT the read-time — so it renders its original day and never shifts."""
    from schemas import Confidence, PortfolioDecision, TradeAction
    from datetime import date
    d = PortfolioDecision(id="x", decision_date=date(2026, 6, 18), action=TradeAction.NO_ACTION,
                          reasoning="r", confidence=Confidence(score=0.3, low=0.2, high=0.4))
    assert d.created_at is not None
    assert d.created_at.date() == date(2026, 6, 18)


def test_block_reason_traded():
    da = _da()
    parsed = {"action": "buy", "asset": "MSFT", "target_weight": 0.1,
              "confidence": {"score": 0.6, "low": 0.5, "high": 0.7, "rationale": "r"}}
    dec = da._finalize("c1", parsed, _agg(), "ok. VERDICT: ACCEPT", "dry")
    assert dec.action.value == "buy"
    assert dec.block_reason == "traded"
