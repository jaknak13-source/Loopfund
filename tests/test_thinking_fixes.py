"""Regressions for the thinking-quality fixes: confidence de-biasing, single-stock
insider targeting, deterministic yield-curve label."""

from __future__ import annotations

import asyncio


def test_score_recentered_off_band_floor():
    """LLM agents report score==low (pessimistic floor); _to_report must recenter it."""
    from agents.analysts import MacroAgent
    ma = MacroAgent.__new__(MacroAgent)
    ma.name = "MacroAgent"

    class _R:
        def resolve(self, _n):
            return {"model": "t"}
    ma.router = _R()
    parsed = {"summary": "s", "stance": "bullish", "assets": ["NVDA"], "findings": ["f"],
              "confidence": {"score": 0.15, "low": 0.15, "high": 0.55, "rationale": "r"},
              "unverified_claims": []}
    rep = ma._to_report("c1", parsed, [], [])
    assert rep.confidence.score > 0.15          # recentered off the floor
    assert abs(rep.confidence.score - 0.35) < 0.01  # midpoint of [0.15, 0.55]
    assert rep.confidence.low <= rep.confidence.score <= rep.confidence.high


def test_score_genuine_floor_preserved():
    """A genuine zero-width / floor read (no band) is left alone."""
    from agents.analysts import MacroAgent
    ma = MacroAgent.__new__(MacroAgent)
    ma.name = "MacroAgent"
    ma.router = type("R", (), {"resolve": lambda s, n: {"model": "t"}})()
    parsed = {"summary": "s", "stance": "uncertain", "assets": [], "findings": [],
              "confidence": {"score": 0.15, "low": 0.15, "high": 0.15, "rationale": "no data"},
              "unverified_claims": []}
    rep = ma._to_report("c1", parsed, [], [])
    assert abs(rep.confidence.score - 0.15) < 0.01  # zero-width band -> unchanged


def test_likely_single_stock_filters_non_stocks():
    from agents.smartmoney import _likely_single_stock
    assert _likely_single_stock("NVDA") is True
    assert _likely_single_stock("AAPL") is True
    assert _likely_single_stock("SPY") is False      # ETF
    assert _likely_single_stock("GLD") is False       # commodity ETF
    assert _likely_single_stock("BTC-USD") is False    # crypto
    assert _likely_single_stock("CL=F") is False        # future
    assert _likely_single_stock("^VIX") is False         # index


def test_macro_yield_curve_label_deterministic(monkeypatch):
    import tools.macro as macro
    import tools.market as market

    monkeypatch.setattr(macro, "env", lambda *a, **k: None)

    async def fake_history(ticker, period="1y", interval="1d"):
        # 10y (^TNX) higher than short (^FVX) -> NORMAL upward-sloping, NOT inverted
        val = 4.45 if ticker == "^TNX" else 4.20 if ticker == "^FVX" else 16.0
        return {"ticker": ticker, "bars": [{"close": val}] * 30}

    monkeypatch.setattr(market, "get_history", fake_history)
    snap = asyncio.run(macro.macro_snapshot())
    yc = snap["yield_curve"]
    assert "NORMAL" in yc["label"]          # 2y<10y is normal, not inverted
    assert yc["spread_pp"] > 0
