"""Phase 8: idle deep-research (backtests) + live-mode safety gate."""

from __future__ import annotations

import pytest

from tests.helpers import build_offline_orchestrator


@pytest.mark.asyncio
async def test_deep_research_writes_memory(tmp_path) -> None:
    orch = build_offline_orchestrator(tmp_path)
    before = orch.rag.size()
    res = await orch.deep_research()
    assert "NVDA" in res["backtests"]
    assert "sharpe" in res["backtests"]["NVDA"]
    assert orch.rag.size() > before  # summary stored


def test_live_gate_blocks_without_env(monkeypatch) -> None:
    import core.app as app
    from core.config import reload

    monkeypatch.setattr(app, "settings", lambda: {"mode": "live", "watchlist": ["NVDA"]})
    monkeypatch.delenv("LOOPFUND_ALLOW_LIVE", raising=False)
    with pytest.raises(RuntimeError, match="Refusing to start"):
        app._select_execution(tools=None, ledger=None)
    reload()
