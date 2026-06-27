"""CouncilAgent: multi-perspective bull/bear/synthesis deliberation on top candidates."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from schemas import AgentReport, Confidence


def _report(agent, stance, assets, signals=None, conf=0.6):
    return AgentReport(id=f"r-{agent}", agent=agent, cycle_id="c1",
                       created_at=datetime.now(timezone.utc), topic="t", stance=stance,
                       assets=assets, asset_signals=signals or {}, summary=f"{agent} view",
                       findings=[f"{agent} finding"],
                       confidence=Confidence(score=conf, low=conf - 0.1, high=conf + 0.1))


def _council(tmp_path):
    from agents.council import CouncilAgent
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    from agents.memory_agent import MemoryAgent
    from models_adapter.router import ModelRouter
    from models_adapter.mock import MockBackend
    from tools.registry import ToolRegistry

    bb = Blackboard(path=tmp_path / "c.db")
    rag = RagMemory(bb, vector_path=tmp_path / "v.npz")
    mem = MemoryAgent(rag)
    turns = {"n": 0}

    def responder(messages):
        turns["n"] += 1
        sysmsg = messages[0].content
        if "BULL advocate" in sysmsg:
            return "Strong secular demand, cheap vs peers, insiders buying."
        if "BEAR" in sysmsg:
            return "Margins peaking, valuation full, momentum fading."
        return "SYNTHESIS: corroborated but timing unclear. Verdict: DEVELOP. Confirm: next earnings."

    router = ModelRouter(backends={"qwen": MockBackend(responder)}, max_concurrent=1)
    return CouncilAgent(bb, router, ToolRegistry(bb), mem), bb, turns


def test_council_deliberates_top_candidate(tmp_path):
    council, bb, turns = _council(tmp_path)
    for r in [_report("QuantAgent", "bullish", ["NVDA"], {"NVDA": 0.6}),
              _report("FundamentalsAgent", "bullish", ["NVDA"]),
              _report("RiskAgent", "uncertain", [])]:
        bb.write_report(r)
    agg = {"ranked": [("NVDA", 0.6)], "corroboration": {"NVDA": 2}}
    dossier = asyncio.run(council.deliberate("c1", agg, "all cash"))
    assert "NVDA" in dossier
    assert "BULL" in dossier and "BEAR" in dossier and "SYNTHESIS" in dossier
    assert turns["n"] >= 3  # three deliberation turns


def test_council_no_candidate_is_graceful(tmp_path):
    council, bb, _ = _council(tmp_path)
    dossier = asyncio.run(council.deliberate("c1", {"ranked": [], "corroboration": {}}, "all cash"))
    assert "no" in dossier.lower()


def test_council_develop_saves_thesis(tmp_path):
    council, bb, _ = _council(tmp_path)
    bb.write_report(_report("QuantAgent", "bullish", ["AMD"], {"AMD": 0.5}))
    agg = {"ranked": [("AMD", 0.5)], "corroboration": {"AMD": 1}}
    asyncio.run(council.deliberate("c1", agg, "all cash"))
    # synthesis returns DEVELOP -> a developing thesis persisted as research memory
    research = bb.memory_by_kind("research", limit=10)
    assert any("AMD" in (m.title + " ".join(m.assets)) for m in research)
