"""SentimentAgent turns StockTwits bull/bear into a signed (small, lead-weighted)
per-ticker signal so social actually moves the aggregate instead of being prose."""

from __future__ import annotations

import asyncio


def _sentiment_agent():
    from agents.analysts import SentimentAgent

    class _Rec:
        id = "tc"

    async def fake_call(agent, tool, **kw):
        if tool == "reddit_hot":
            return ({"available": True, "posts": [{"title": "stuff"}]}, _Rec())
        if tool == "stocktwits_symbol":
            sym = kw.get("symbol")
            if sym == "NVDA":  # strongly bullish crowd
                msgs = [{"sentiment": "Bullish"}] * 9 + [{"sentiment": "Bearish"}] * 1
            elif sym == "XOM":  # bearish crowd
                msgs = [{"sentiment": "Bearish"}] * 7 + [{"sentiment": "Bullish"}] * 1
            else:
                msgs = []
            return ({"messages": msgs}, _Rec())
        return ({}, _Rec())

    sa = SentimentAgent.__new__(SentimentAgent)
    sa.name = "SentimentAgent"
    sa.watchlist = ["NVDA", "XOM", "AAPL"]
    sa.tools = type("T", (), {"call": staticmethod(fake_call)})()
    return sa


def test_sentiment_emits_signed_capped_signal():
    sa = _sentiment_agent()
    asyncio.run(sa.gather("c1"))
    sig = sa._asset_signals
    assert sig["NVDA"] > 0 and sig["XOM"] < 0       # crowd direction captured
    assert all(abs(v) <= 0.3 + 1e-9 for v in sig.values())  # capped — sentiment is a LEAD
    assert "AAPL" not in sig                          # no messages -> no signal
