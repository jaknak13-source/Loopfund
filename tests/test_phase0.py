"""Phase 0 smoke tests: schemas, blackboard, tool registry, serialized inference,
and a fake agent writing a report end-to-end.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from agents.base import BaseAgent
from core.blackboard import Blackboard
from models_adapter.base import LLMBackend, Message
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from schemas import AgentReport, Confidence
from tools.registry import default_registry


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def bb(tmp_path) -> Blackboard:
    return Blackboard(path=tmp_path / "test.db")


# --- schemas ---

def test_confidence_band_valid() -> None:
    c = Confidence(score=0.6, low=0.4, high=0.8, rationale="ok")
    assert c.score == 0.6


def test_confidence_band_invalid() -> None:
    with pytest.raises(ValueError):
        Confidence(score=0.9, low=0.4, high=0.8)


# --- blackboard ---

def test_report_roundtrip(bb: Blackboard) -> None:
    report = AgentReport(
        id="r1",
        agent="TestAgent",
        cycle_id="c1",
        created_at=_now(),
        topic="NVDA",
        summary="test summary",
        stance="bullish",
        confidence=Confidence(score=0.5, low=0.3, high=0.7),
    )
    bb.write_report(report)
    back = bb.get_report("r1")
    assert back is not None
    assert back.topic == "NVDA"
    assert back.stance == "bullish"
    assert [r.id for r in bb.reports_for_cycle("c1")] == ["r1"]


# --- tool registry ---

@pytest.mark.asyncio
async def test_tool_registry_echo_logs_call(bb: Blackboard) -> None:
    reg = default_registry(bb)
    assert "echo" in reg.available()
    result, rec = await reg.call("TestAgent", "echo", x=1, y="two")
    assert result == {"x": 1, "y": "two"}
    assert rec.ok is True
    assert rec.agent == "TestAgent"


@pytest.mark.asyncio
async def test_tool_registry_unknown_raises(bb: Blackboard) -> None:
    reg = default_registry(bb)
    with pytest.raises(KeyError):
        await reg.call("TestAgent", "does_not_exist")


# --- serialized inference (M4 Air crash guard) ---

class _ConcurrencyProbe(LLMBackend):
    name = "lmstudio"

    def __init__(self) -> None:
        self.active = 0
        self.max_active = 0

    async def complete(self, messages, *, model, temperature=0.3, max_tokens=2048, timeout=180.0) -> str:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.02)
        self.active -= 1
        return "done"


def test_merge_system_into_user() -> None:
    from models_adapter.router import _merge_system_into_user
    out = _merge_system_into_user([Message("system", "SYS"), Message("user", "USR")])
    assert len(out) == 1 and out[0].role == "user"
    assert "SYS" in out[0].content and "USR" in out[0].content


@pytest.mark.asyncio
async def test_router_folds_system_when_unsupported() -> None:
    captured: list[Message] = []

    class _Rec(LLMBackend):
        name = "lmstudio"
        async def complete(self, messages, *, model, temperature=0.3, max_tokens=2048, timeout=180.0):
            captured.extend(messages)
            return "ok"

    router = ModelRouter(backends={"lmstudio": _Rec()}, max_concurrent=1)
    router.models_cfg = {"default": {"backend": "lmstudio", "model": "gemma",
                                     "supports_system_role": False}, "agents": {}}
    await router.complete("X", [Message("system", "S"), Message("user", "U")])
    assert all(m.role != "system" for m in captured)  # system folded away
    assert any("S" in m.content and "U" in m.content for m in captured)


@pytest.mark.asyncio
async def test_inference_is_serialized() -> None:
    probe = _ConcurrencyProbe()
    router = ModelRouter(backends={"qwen": probe}, max_concurrent=1)
    await asyncio.gather(
        *(router.complete("TestAgent", [Message("user", "hi")]) for _ in range(8))
    )
    assert probe.max_active == 1  # never more than one concurrent model call


# --- fake agent end-to-end ---

class FakeAgent(BaseAgent):
    name = "FakeAgent"

    async def run(self, cycle_id: str) -> AgentReport:
        text = await self.think("You are a test.", "Say something.")
        report = self.make_report(
            cycle_id=cycle_id,
            topic="smoke",
            summary=text,
            confidence=Confidence(score=0.5, low=0.3, high=0.7),
            stance="neutral",
        )
        self.bb.write_report(report)
        return report


@pytest.mark.asyncio
async def test_fake_agent_writes_report(bb: Blackboard) -> None:
    router = ModelRouter(backends={"qwen": MockBackend("hello from mock")}, max_concurrent=1)
    reg = default_registry(bb)
    agent = FakeAgent(bb, router, reg)

    report = await agent.run("cycle-1")
    back = bb.get_report(report.id)
    assert back is not None
    assert back.summary == "hello from mock"
    assert back.agent == "FakeAgent"
    assert [r.id for r in bb.reports_for_cycle("cycle-1")] == [report.id]
