"""Self-extending agents: briefing parsing, dynamic agent execution, the loader,
and the MetaAgent authoring a new agent."""

from __future__ import annotations

import pytest

from agents import briefing_loader, meta as meta_mod
from agents.briefing_loader import briefings_dir, discover
from agents.dynamic import Briefing, DynamicAgent, load_briefing, parse_briefing
from agents.memory_agent import MemoryAgent
from agents.meta import MetaAgent
from core.blackboard import Blackboard
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry
from tests.helpers import build_offline_orchestrator

_ANALYST_JSON = ('{"summary":"chains tightening","stance":"bearish","assets":["XOM"],'
                 '"findings":["port congestion"],"confidence":{"score":0.5,"low":0.4,'
                 '"high":0.6,"rationale":"r"},"unverified_claims":[]}')

_SAMPLE = """---
name: TestAgent
schedule: cycle
tools:
  - name: gdelt_search
    params: {query: "x"}
---
You are TestAgent. Do a thing."""


def test_parse_briefing() -> None:
    meta, body = parse_briefing(_SAMPLE)
    assert meta["name"] == "TestAgent"
    assert body.startswith("You are TestAgent")


def test_load_seed_briefing() -> None:
    # the committed example briefing
    b = load_briefing(briefings_dir() / "SupplyChainAgent.md")
    assert b is not None and b.name == "SupplyChainAgent"
    assert any(t["name"] == "gdelt_search" for t in b.tools)


def test_loader_discovers_seed() -> None:
    assert any(b.name == "SupplyChainAgent" for b in discover())


@pytest.mark.asyncio
async def test_dynamic_agent_runs(tmp_path) -> None:
    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v" / "i.npz"))
    router = ModelRouter(backends={"qwen": MockBackend(_ANALYST_JSON)}, max_concurrent=1)
    reg = ToolRegistry(bb)

    async def gdelt_search(**kw):
        return {"articles": [{"title": "Port strike escalates", "link": "http://x/1"}]}
    reg.register("gdelt_search", gdelt_search)

    brief = Briefing(name="SupplyChainAgent", body="You are SupplyChainAgent.",
                     tools=[{"name": "gdelt_search", "params": {"query": "ports"}}])
    agent = DynamicAgent(brief, bb, router, reg, memory, watchlist=["XOM"])
    report = await agent.run("c1")
    assert report.agent == "SupplyChainAgent"
    assert report.stance == "bearish"
    assert report.citations  # gathered from the declared tool


def _patch_dynamic_dir(monkeypatch, tmp_path) -> None:
    cfg = {"agents": {"dynamic_dir": str(tmp_path / "briefs"), "allow_meta": True,
                      "max_dynamic_agents": 8}}
    monkeypatch.setattr(briefing_loader, "settings", lambda: cfg)
    monkeypatch.setattr(meta_mod, "settings", lambda: cfg)


_NEW_BRIEFING = """---
name: EnergyTransitionAgent
profile: default
schedule: cycle
enabled: true
tools:
  - name: gdelt_search
    params: {query: "energy transition policy"}
---
You are the EnergyTransitionAgent. Track energy policy and grid build-out."""


@pytest.mark.asyncio
async def test_meta_creates_new_agent(tmp_path, monkeypatch) -> None:
    _patch_dynamic_dir(monkeypatch, tmp_path)
    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v" / "i.npz"))
    router = ModelRouter(backends={"qwen": MockBackend(_NEW_BRIEFING)}, max_concurrent=1)
    reg = ToolRegistry(bb)
    reg.register("gdelt_search", lambda **kw: {"articles": []})

    agent = MetaAgent(bb, router, reg, memory)
    out = await agent.improve()
    assert out["ok"] is True
    assert out["name"] == "EnergyTransitionAgent"
    # the authored briefing is now discoverable
    assert any(b.name == "EnergyTransitionAgent" for b in discover())


@pytest.mark.asyncio
async def test_meta_rejects_reserved_name(tmp_path, monkeypatch) -> None:
    _patch_dynamic_dir(monkeypatch, tmp_path)
    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v" / "i.npz"))
    reserved = _NEW_BRIEFING.replace("EnergyTransitionAgent", "QuantAgent")
    router = ModelRouter(backends={"qwen": MockBackend(reserved)}, max_concurrent=1)
    reg = ToolRegistry(bb)
    reg.register("gdelt_search", lambda **kw: {"articles": []})
    out = await MetaAgent(bb, router, reg, memory).improve()
    assert out["ok"] is False


def test_creative_crew_loaded() -> None:
    by_name = {b.name: b for b in discover()}
    for n in ("InnovatorAgent", "ContrarianScout", "CrossMarketConnector"):
        assert n in by_name, n
        assert by_name[n].profile == "creative"            # high-temp profile
        assert any(t["name"] == "random_memory" for t in by_name[n].tools)  # random ideation fuel


def test_agent_striding(tmp_path) -> None:
    from agents.briefing_loader import build_dynamic_agents
    from agents.memory_agent import MemoryAgent
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    from models_adapter.mock import MockBackend
    from models_adapter.router import ModelRouter
    from tools.registry import ToolRegistry
    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v.npz"))
    router = ModelRouter(backends={"qwen": MockBackend("{}")}, max_concurrent=1)
    reg = ToolRegistry(bb)
    def names(i):
        return {a.name for a in build_dynamic_agents(bb, router, reg, memory, ["NVDA"], cycle_index=i)}
    n0, n1 = names(0), names(1)
    assert len(n0) >= 6                       # cycle 0: all dynamic agents run
    assert "InnovatorAgent" not in n1         # every:3 -> skipped on cycle 1
    assert "ValuationAgent" not in n1         # every:2 -> skipped on cycle 1
    assert len(n1) < len(n0)                  # fewer agents -> faster cycle


def test_creative_profile_is_high_temp() -> None:
    from core.config import models_config
    # elevated for creativity, but capped so the model still emits valid JSON
    assert 0.7 <= models_config()["creative"]["temperature"] <= 0.9


def test_random_memory_registered(tmp_path) -> None:
    from core.blackboard import Blackboard
    from tools.data_tools import build_data_registry
    reg = build_data_registry(Blackboard(path=tmp_path / "t.db"))
    assert "random_memory" in reg.available()


@pytest.mark.asyncio
async def test_random_memory_returns_entries(tmp_path, monkeypatch) -> None:
    from datetime import datetime, timezone
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    from schemas import MemoryEntry
    from tools import ideation
    monkeypatch.setattr(ideation, "data_dir", lambda: tmp_path)
    bb = Blackboard(path=tmp_path / "loopfund.db")
    rag = RagMemory(bb, vector_path=tmp_path / "v.npz")
    for i in range(5):
        rag.add(MemoryEntry(id=f"e{i}", created_at=datetime.now(timezone.utc), kind="news",
                            title=f"finding {i}", body=f"body {i}"))
    res = await ideation.random_memory(n=3)
    assert res["n"] == 3 and all("title" in e for e in res["entries"])


@pytest.mark.asyncio
async def test_orchestrator_runs_dynamic_agent(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    await orch.run_cycle("c1")
    # the seed SupplyChainAgent (real briefings dir) ran this cycle
    agents_seen = {r.agent for r in orch.bb.reports_for_cycle("c1")}
    assert "SupplyChainAgent" in agents_seen
