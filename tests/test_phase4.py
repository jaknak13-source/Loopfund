"""Phase 4: evidence aggregation + DecisionAgent debate (accept / veto / floor)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents import evidence
from agents.decision import DecisionAgent
from agents.memory_agent import MemoryAgent
from agents.risk import RiskAgent
from core.blackboard import Blackboard
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from schemas import AgentReport, Confidence, TradeAction


def _report(agent, stance, score, assets, unverified=None) -> AgentReport:
    return AgentReport(
        id=f"{agent}-{stance}", agent=agent, cycle_id="c1", created_at=datetime.now(timezone.utc),
        topic="t", summary=f"{agent} says {stance}", stance=stance,
        confidence=Confidence(score=score, low=max(0, score - 0.1), high=min(1, score + 0.1)),
        assets=assets, unverified_claims=unverified or [],
    )


def test_aggregate_signs() -> None:
    reports = [
        _report("QuantAgent", "bullish", 0.7, ["NVDA"]),
        _report("FundamentalsAgent", "bullish", 0.6, ["NVDA"]),
        _report("RiskAgent", "bearish", 0.8, []),
        _report("SentimentAgent", "bearish", 0.5, ["XOM"]),
    ]
    agg = evidence.aggregate(reports)
    assert agg["per_asset"]["NVDA"] > 0
    assert agg["per_asset"]["XOM"] < 0
    assert agg["risk_signal"] < 0  # skeptic acts as a brake


def test_unverified_claims_lower_weight() -> None:
    clean = _report("MacroAgent", "bullish", 0.6, ["AAA"])
    noisy = _report("MacroAgent", "bullish", 0.6, ["AAA"], unverified=["x", "y", "z"])
    assert evidence.report_weight(noisy) < evidence.report_weight(clean)


def _make_decider(tmp_path, responder):
    bb = Blackboard(path=tmp_path / "t.db")
    rag = RagMemory(bb, vector_path=tmp_path / "v" / "i.npz")
    memory = MemoryAgent(rag)
    router = ModelRouter(backends={"qwen": MockBackend(responder)}, max_concurrent=1)
    risk = RiskAgent(bb, router, None, memory)
    decider = DecisionAgent(bb, router, None, memory, risk)
    # seed peer reports
    bb.write_report(_report("QuantAgent", "bullish", 0.7, ["NVDA"]))
    bb.write_report(_report("FundamentalsAgent", "bullish", 0.65, ["NVDA"]))
    return bb, decider


_BUY_JSON = (
    '{"action":"buy","asset":"NVDA","target_weight":0.5,'
    '"reasoning":"strong evidence","key_assumptions":["ai capex"],'
    '"known_risks":["valuation"],"confidence":{"score":0.7,"low":0.6,"high":0.8,"rationale":"r"}}'
)


@pytest.mark.asyncio
async def test_decision_buy_accepted_and_capped(tmp_path) -> None:
    def responder(messages):
        text = messages[-1].content
        return "Reasonable. ACCEPT" if "Attack this decision" in text else _BUY_JSON
    bb, decider = _make_decider(tmp_path, responder)
    d = await decider.run("c1")
    assert d.action == TradeAction.BUY
    assert d.asset == "NVDA"
    assert d.target_weight is not None and d.target_weight <= 0.20  # concentration cap enforced


@pytest.mark.asyncio
async def test_decision_risk_reject_on_corroborated_idea_haircuts_not_vetoes(tmp_path) -> None:
    # NVDA is corroborated here (QuantAgent + FundamentalsAgent both bullish), so a RiskAgent
    # REJECT downgrades to a SIZE HAIRCUT rather than a hard veto — the fund still acts on a
    # well-supported idea. (The uncorroborated-REJECT veto path is covered in test_unlock.)
    def responder(messages):
        text = messages[-1].content
        return "Too risky. VERDICT: REJECT" if "Attack this decision" in text else _BUY_JSON
    bb, decider = _make_decider(tmp_path, responder)
    d = await decider.run("c1")
    assert d.action == TradeAction.BUY
    assert d.target_weight is not None and 0.0 < d.target_weight <= 0.20  # 0.5 requested -> halved + capped


@pytest.mark.asyncio
async def test_decision_below_floor_is_no_action(tmp_path) -> None:
    low_buy = _BUY_JSON.replace('"score":0.7', '"score":0.3').replace('"low":0.6', '"low":0.2').replace('"high":0.8', '"high":0.4')
    def responder(messages):
        text = messages[-1].content
        return "ACCEPT" if "Attack this decision" in text else low_buy
    bb, decider = _make_decider(tmp_path, responder)
    d = await decider.run("c1")
    assert d.action == TradeAction.NO_ACTION
