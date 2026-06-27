"""Self-taught research: sandboxed code execution + the research loop that writes,
runs, and saves its own method."""

from __future__ import annotations

from pathlib import Path

import pytest

from agents.memory_agent import MemoryAgent
from agents.quant_research import QuantResearchAgent
from core.blackboard import Blackboard
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from tools import code_runner
from tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_run_python_executes(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(code_runner, "SANDBOX", tmp_path / "sb")
    monkeypatch.setattr(code_runner, "code_execution_allowed", lambda: True)
    res = await code_runner.run_python("print('hello'); print(2 + 2)", "t", timeout_s=30)
    assert res["ok"] is True
    assert "hello" in res["stdout"] and "4" in res["stdout"]


@pytest.mark.asyncio
async def test_run_python_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(code_runner, "settings",
                        lambda: {"agents": {"allow_code_execution": False}})
    res = await code_runner.run_python("print(1)", "t")
    assert res["ok"] is False


@pytest.mark.asyncio
async def test_run_python_timeout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(code_runner, "SANDBOX", tmp_path / "sb")
    monkeypatch.setattr(code_runner, "code_execution_allowed", lambda: True)
    res = await code_runner.run_python("import time; time.sleep(5)", "slow", timeout_s=1)
    assert res["ok"] is False and res["timed_out"] is True


@pytest.mark.asyncio
async def test_quant_research_invents_and_saves_method(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(code_runner, "SANDBOX", tmp_path / "sb")
    monkeypatch.setattr(code_runner, "code_execution_allowed", lambda: True)
    import agents.quant_research as qr
    monkeypatch.setattr(qr, "SANDBOX", tmp_path / "sb")
    monkeypatch.setattr(qr, "LIBRARY", tmp_path / "lib")
    monkeypatch.setattr(qr, "code_execution_allowed", lambda: True)

    bb = Blackboard(path=tmp_path / "t.db")
    memory = MemoryAgent(RagMemory(bb, vector_path=tmp_path / "v" / "i.npz"))

    # the "LLM" writes this runnable script; it prints a valid RESULT line
    script = ('import json\n'
              'print("RESULT:", json.dumps({"method":"trivial_mr","sharpe":0.8,'
              '"total_return":0.12,"max_drawdown":-0.05,"notes":"toy"}))')
    router = ModelRouter(backends={"qwen": MockBackend(script)}, max_concurrent=1)

    reg = ToolRegistry(bb)
    async def history(**kw):
        return {"ticker": kw.get("ticker"), "bars": [{"close": 100.0 + i} for i in range(150)], "stale": False}
    reg.register("history", history)
    reg.register("run_python", code_runner.run_python)

    agent = QuantResearchAgent(bb, router, reg, memory, watchlist=["AAA"])
    out = await agent.research()

    assert out["ok"] is True
    assert out["result"]["method"] == "trivial_mr"
    assert out["result"]["sharpe"] == 0.8
    assert Path(out["saved"]).exists()           # method persisted to the library
    assert memory.rag.search("trivial_mr", k=1)   # lesson recorded in memory
