"""Full-cycle orchestrator test, fully offline (mock LLM + fake data tools)."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from core.blackboard import Blackboard
from core.orchestrator import Orchestrator
from execution.portfolio import Portfolio, PortfolioStore
from execution.sim_ledger import SimLedger
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from schemas import HumanInstruction
from tools.registry import ToolRegistry

_ANALYST_JSON = ('{"summary":"ok","stance":"neutral","assets":["NVDA"],"findings":["f"],'
                 '"confidence":{"score":0.4,"low":0.3,"high":0.5,"rationale":"r"},"unverified_claims":[]}')
_BUY_JSON = ('{"action":"buy","asset":"NVDA","target_weight":0.1,"reasoning":"ok",'
             '"key_assumptions":["a"],"known_risks":["r"],'
             '"confidence":{"score":0.7,"low":0.6,"high":0.8,"rationale":"r"}}')


def _responder(messages):
    text = messages[-1].content
    if "Attack this decision" in text:
        return "Acceptable. ACCEPT"
    if '"action":' in text:
        return _BUY_JSON
    return _ANALYST_JSON


def _bars():
    rng = np.random.default_rng(3)
    closes = [100.0]
    for _ in range(120):
        closes.append(closes[-1] * (1 + 0.0005 + rng.normal(0, 0.01)))
    return [{"date": str(i), "open": c, "high": c, "low": c, "close": c, "volume": 1000}
            for i, c in enumerate(closes)]


def _registry(bb: Blackboard) -> ToolRegistry:
    reg = ToolRegistry(bb)

    async def price(**kw):
        return {"ticker": kw.get("ticker"), "price": 100.0, "ccy": "EUR", "stale": False}
    async def fx_rate(**kw):
        return {"rate": 1.0, "base": kw.get("base"), "quote": "EUR", "stale": False}
    async def history(**kw):
        return {"ticker": kw.get("ticker"), "bars": _bars(), "stale": False}
    async def rss_headlines(**kw):
        return {"articles": [{"title": "Markets steady", "link": "http://x/1"}], "stale": False}
    async def gdelt_search(**kw):
        return {"articles": [{"title": "Policy update"}], "stale": False}
    async def macro_snapshot(**kw):
        return {"available": False, "series": {}}
    async def fundamentals(**kw):
        return {"ticker": kw.get("ticker"), "fundamentals": {"trailingPE": 30}, "stale": False}
    async def reddit_hot(**kw):
        return {"subreddit": kw.get("subreddit"), "posts": [], "available": False}
    async def stocktwits_symbol(**kw):
        return {"symbol": kw.get("symbol"), "messages": [], "stale": False}
    async def recent_filings(**kw):
        return {"ticker": kw.get("ticker"), "filings": [], "available": False}

    for name, fn in [("price", price), ("fx_rate", fx_rate), ("history", history),
                     ("rss_headlines", rss_headlines), ("gdelt_search", gdelt_search),
                     ("macro_snapshot", macro_snapshot), ("fundamentals", fundamentals),
                     ("reddit_hot", reddit_hot), ("stocktwits_symbol", stocktwits_symbol),
                     ("recent_filings", recent_filings)]:
        reg.register(name, fn)
    return reg


def _orch(tmp_path) -> Orchestrator:
    bb = Blackboard(path=tmp_path / "t.db")
    rag = RagMemory(bb, vector_path=tmp_path / "v" / "i.npz")
    ledger = SimLedger(Portfolio(cash_eur=1000.0),
                       store=PortfolioStore(path=tmp_path / "pf.json"), blackboard=bb)
    router = ModelRouter(backends={"qwen": MockBackend(_responder)}, max_concurrent=1)
    return Orchestrator(blackboard=bb, router=router, data_tools=_registry(bb), rag=rag,
                        ledger=ledger, watchlist=["NVDA"], state_path=tmp_path / "state.json",
                        learning_path=tmp_path / "learning.json")


@pytest.mark.asyncio
async def test_full_cycle_executes_buy(tmp_path) -> None:
    orch = _orch(tmp_path)
    result = await orch.run_cycle("c1")
    assert result["decision"]["action"] == "buy"
    assert result["executed_trade_id"] is not None
    assert "NVDA" in orch.ledger.p.positions
    assert result["portfolio"]["total_value_eur"] > 0
    assert result["memory_size"] > 0  # agents wrote to RAG


@pytest.mark.asyncio
async def test_human_no_trade_blocks_execution(tmp_path) -> None:
    orch = _orch(tmp_path)
    orch.bb.write_instruction(HumanInstruction(
        id="i1", received_at=datetime.now(timezone.utc), text="Don't trade this week."))
    result = await orch.run_cycle("c1")
    assert "no_trade" in result["intents"]
    assert result["executed_trade_id"] is None
    assert "NVDA" not in orch.ledger.p.positions
