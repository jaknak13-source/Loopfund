"""Continuous-research engine: decision pacing + research tasks that never idle and
save findings to memory."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.helpers import build_offline_orchestrator


def test_decision_due_pacing(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    assert orch.decision_due() is True                      # never run -> due
    orch._state["last_decision_iso"] = datetime.now(timezone.utc).isoformat()
    assert orch.decision_due() is False                     # within the cadence -> research instead


@pytest.mark.asyncio
async def test_research_tasks_run_and_save(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    before = orch.rag.size()
    # deep-dive (0), undervalued scan (1), theme (2), smart-money (4) all run offline
    for idx in (0, 1, 2, 4):
        res = await orch.research_task(idx)
        assert res.get("task") and res["task"] != "error"
    assert orch.rag.size() > before                         # findings accumulated in memory


@pytest.mark.asyncio
async def test_research_task_never_crashes(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    # even the quant-method task (needs run_python, absent offline) degrades gracefully
    res = await orch.research_task(3)
    assert "task" in res
