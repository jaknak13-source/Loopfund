"""Phase 1: data registry assembly + offline-deterministic graceful degradation.

Network-dependent calls are NOT exercised here (kept hermetic). We assert that
adapters degrade cleanly when a key is missing or a source is identity.
"""

from __future__ import annotations

import pytest

from core.blackboard import Blackboard
from tools import fx, macro, social
from tools.data_tools import build_data_registry


@pytest.fixture
def bb(tmp_path) -> Blackboard:
    return Blackboard(path=tmp_path / "t.db")


def test_registry_has_all_tools(bb: Blackboard) -> None:
    reg = build_data_registry(bb)
    for name in [
        "echo", "price", "history", "fundamentals", "fx_rate", "fred_series",
        "macro_snapshot", "rss_headlines", "gdelt_search", "reddit_hot",
        "stocktwits_symbol", "recent_filings",
    ]:
        assert name in reg.available(), name


@pytest.mark.asyncio
async def test_fx_identity_no_network() -> None:
    res = await fx.fx_rate("EUR", "EUR")
    assert res["rate"] == 1.0
    assert res["stale"] is False


@pytest.mark.asyncio
async def test_fred_degrades_without_key(monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    res = await macro.fred_series("DFF")
    assert res["available"] is False


@pytest.mark.asyncio
async def test_reddit_degrades_without_creds(monkeypatch) -> None:
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    res = await social.reddit_hot("investing")
    assert res["available"] is False


@pytest.mark.asyncio
async def test_tool_call_logged_through_registry(bb: Blackboard) -> None:
    reg = build_data_registry(bb)
    res, rec = await reg.call("ResearchAgent", "fx_rate", base="EUR", quote="EUR")
    assert res["rate"] == 1.0
    assert rec.ok is True and rec.tool == "fx_rate"
