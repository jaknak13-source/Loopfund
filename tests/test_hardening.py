"""Hardening: authoritative time + preamble in prompts, backups/restore,
crash error logging, daily memory audit."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agents.base import BaseAgent
from agents.memory_agent import MemoryAgent
from agents.memory_auditor import MemoryAuditorAgent
from core import backup as backup_mod
from core import resilience as resil_mod
from core.blackboard import Blackboard
from core.clock import time_context
from core.preamble import system_preamble
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from schemas import MemoryEntry
from tools.registry import ToolRegistry


def test_time_context_has_now() -> None:
    tc = time_context()
    assert "CURRENT TIME" in tc and "UTC" in tc
    assert str(datetime.now(timezone.utc).year) in tc


def test_preamble_has_cutoff_and_verify() -> None:
    p = system_preamble()
    assert "training data ends" in p.lower()
    assert "verify" in p.lower()
    assert "CURRENT TIME" in p  # time embedded


class _FA(BaseAgent):
    name = "FA"
    async def run(self, cycle_id):  # pragma: no cover - not used
        ...


@pytest.mark.asyncio
async def test_think_injects_preamble(tmp_path) -> None:
    bb = Blackboard(path=tmp_path / "t.db")
    mb = MockBackend("ok")
    agent = _FA(bb, ModelRouter(backends={"qwen": mb}, max_concurrent=1), ToolRegistry(bb))
    await agent.think("ROLE-SPECIFIC SYSTEM", "user msg")
    system_sent = mb.calls[-1][0].content
    assert "OPERATING TRUTH" in system_sent
    assert "CURRENT TIME" in system_sent
    assert "ROLE-SPECIFIC SYSTEM" in system_sent  # original prompt preserved


def test_backup_and_restore(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backup_mod, "data_dir", lambda: tmp_path)
    (tmp_path / "portfolio.json").write_text('{"cash_eur": 123.0}', encoding="utf-8")
    name = backup_mod.backup_now().name
    assert name in backup_mod.list_backups()
    # mutate, then restore
    (tmp_path / "portfolio.json").write_text('{"cash_eur": 999.0}', encoding="utf-8")
    assert backup_mod.restore(name) is True
    assert '"cash_eur": 123.0' in (tmp_path / "portfolio.json").read_text()


def test_maybe_daily_backup_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backup_mod, "data_dir", lambda: tmp_path)
    (tmp_path / "state.json").write_text("{}", encoding="utf-8")
    state: dict = {}
    assert backup_mod.maybe_daily_backup(state) is not None
    assert backup_mod.maybe_daily_backup(state) is None  # same day -> skip


def test_record_error_writes_log(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(resil_mod, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(resil_mod, "backup_now", lambda tag=None: tmp_path)  # avoid real copy
    resil_mod.record_error("unit", ValueError("boom"))
    log = (tmp_path / "errors.jsonl").read_text()
    assert "boom" in log and "unit" in log


_AUDIT_JSON = ('{"flagged":[{"title":"Old NVDA price","reason":"price is weeks stale"}],'
               '"summary":"1 stale entry"}')


@pytest.mark.asyncio
async def test_memory_audit_flags_and_writes_lesson(tmp_path) -> None:
    bb = Blackboard(path=tmp_path / "t.db")
    rag = RagMemory(bb, vector_path=tmp_path / "v" / "i.npz")
    memory = MemoryAgent(rag)
    rag.add(MemoryEntry(id="m1", created_at=datetime.now(timezone.utc) - timedelta(days=2), kind="news",
                        title="Old NVDA price", body="NVDA at 100 (from a while ago)"))
    auditor = MemoryAuditorAgent(bb, ModelRouter(backends={"qwen": MockBackend(_AUDIT_JSON)},
                                                 max_concurrent=1), ToolRegistry(bb), memory)
    out = await auditor.audit()
    assert out["ok"] and out["flagged"] == 1
    assert rag.search("flagged stale NVDA", k=1, kind="lesson")  # correction recorded
