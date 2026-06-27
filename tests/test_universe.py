"""Broad universe, rotating watchlist, dynamic expansion, and new tool registration."""

from __future__ import annotations

import pytest

from config import universe
from core.blackboard import Blackboard
from core.watchlist import ANCHORS, sample_watchlist
from tools.data_tools import build_data_registry


def test_universe_is_broad() -> None:
    uni = universe.full_universe()
    assert len(uni) > 300  # hundreds across classes + global markets
    # US + assets
    for sym in ["NVDA", "MU", "WDC", "SPY", "GLD", "USO", "BTC-USD", "EURUSD=X", "TLT", "URA", "PLTR"]:
        assert sym in uni, sym
    # global: Europe, Japan, HK/China, Korea (SK Hynix), Taiwan, India, Australia, S.Africa
    for sym in ["ASML.AS", "7203.T", "0700.HK", "000660.KS", "2330.TW", "RELIANCE.NS",
                "BHP.AX", "NPN.JO", "EWJ", "INDA"]:
        assert sym in uni, sym


def test_add_ticker_and_full_universe(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(universe, "data_dir", lambda: tmp_path)
    assert universe.add_ticker("ZZZZ") is True
    assert "ZZZZ" in universe.full_universe()
    assert universe.add_ticker("ZZZZ") is False     # dup
    assert universe.add_ticker("NVDA") is False      # already in base


def test_watchlist_rotates_and_includes_held() -> None:
    w0 = sample_watchlist(["NVDA"], cycle_index=0)
    w5 = sample_watchlist(["NVDA"], cycle_index=5)
    for w in (w0, w5):
        assert all(a in w for a in ANCHORS)   # anchors always present
        assert "NVDA" in w                      # held always present
    assert set(w0) != set(w5)                   # different slice of the universe


def test_new_tools_registered(tmp_path) -> None:
    reg = build_data_registry(Blackboard(path=tmp_path / "t.db"))
    for name in ["propose_ticker", "congress_trades", "polymarket_markets"]:
        assert name in reg.available(), name


@pytest.mark.asyncio
async def test_propose_ticker_adds(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(universe, "data_dir", lambda: tmp_path)
    from tools import universe_tools

    async def fake_price(t):
        return {"ticker": t, "price": 12.3, "ccy": "USD"}
    monkeypatch.setattr(universe_tools.market, "get_price", fake_price)

    res = await universe_tools.propose_ticker("ZZZZ", "found in research")
    assert res["ok"] is True and res["newly_added"] is True
    assert "ZZZZ" in universe.full_universe()
