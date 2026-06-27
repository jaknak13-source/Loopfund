"""Fair-value (DCF/multiples), skills playbooks, $WATCHLIST fan-out, new agents."""

from __future__ import annotations

import pytest

from quant import valuation


def test_dcf_and_helpers() -> None:
    d = valuation.dcf(100.0, 0.10, discount=0.10, years=5, shares=10.0, net_debt=0.0)
    assert d["equity_value"] > 0 and d["fair_value_per_share"] > 0
    assert valuation.multiples_value(5.0, 18.0) == 90.0
    assert valuation.blend(100.0, 90.0) == 95.0
    g = valuation.reverse_dcf(50.0, 100.0, 10.0)
    assert g is None or -0.30 <= g <= 0.40


@pytest.mark.asyncio
async def test_estimate_fair_value(monkeypatch) -> None:
    from tools import filings, market, valuation as vtool

    async def fake_sec(ticker):
        return {"ticker": ticker, "cik": "1", "financials": {
            "net_income": 1000.0, "eps_diluted": 5.0, "revenue_yoy": 0.10,
            "long_term_debt": 200.0, "cash": 100.0}}

    async def fake_price(ticker):
        return {"ticker": ticker, "price": 80.0, "ccy": "USD"}

    monkeypatch.setattr(filings, "sec_financials", fake_sec)
    monkeypatch.setattr(market, "get_price", fake_price)
    r = await vtool.estimate_fair_value("XYZ")
    assert r["fair_value_blend"] is not None
    assert r["upside_pct"] is not None
    assert r["inputs"]["shares_est"] == 200.0   # net_income/eps = 1000/5


@pytest.mark.asyncio
async def test_skills_tool() -> None:
    from tools import skills
    listing = await skills.list_skills()
    assert "valuation-playbook" in listing["skills"]
    got = await skills.get_skill("valuation-playbook")
    assert "Margin" in got["procedure"] or "margin" in got["procedure"].lower()
    miss = await skills.get_skill("does-not-exist")
    assert miss["available"] is False and "skills" in miss


@pytest.mark.asyncio
async def test_watchlist_fanout(tmp_path) -> None:
    from agents.dynamic import Briefing, DynamicAgent
    from agents.memory_agent import MemoryAgent
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    from models_adapter.mock import MockBackend
    from models_adapter.router import ModelRouter
    from tools.registry import ToolRegistry

    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v.npz"))
    calls = []

    async def fv(**kw):
        calls.append(kw.get("ticker"))
        return {"ticker": kw.get("ticker"), "fair_value_blend": 1.0}

    reg = ToolRegistry(bb)
    reg.register("estimate_fair_value", fv)
    router = ModelRouter(backends={"qwen": MockBackend('{"stance":"neutral","summary":"x","confidence":{"score":0.4,"low":0.3,"high":0.5}}')}, max_concurrent=1)
    brief = Briefing(name="ValuationAgent", body="value things",
                     tools=[{"name": "estimate_fair_value", "params": {"ticker": "$WATCHLIST"}}])
    agent = DynamicAgent(brief, bb, router, reg, memory, watchlist=["AAA", "BBB", "CCC"])
    await agent.run("c1")
    assert calls == ["AAA", "BBB", "CCC"]  # fanned out over watchlist


def test_new_agent_briefings_loaded() -> None:
    from agents.briefing_loader import discover
    names = {b.name for b in discover()}
    assert {"ValuationAgent", "EarningsAgent", "InnovatorAgent",
            "ContrarianScout", "CrossMarketConnector"} <= names
