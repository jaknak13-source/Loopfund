"""SmartMoneyAgent: turn insider/politician/institution disclosures into signed
per-ticker signals (the 'follow the smart money' edge)."""

from __future__ import annotations


def _tx(rep, ticker, type_, amount, date):
    return {"rep": rep, "ticker": ticker, "type": type_, "amount": amount, "date": date}


def test_score_flows_buys_positive_sells_negative():
    from agents.smartmoney import score_flows
    trades = [
        _tx("A", "NVDA", "purchase", "$50,001 - $100,000", "2026-06-15"),
        _tx("B", "NVDA", "purchase", "$15,001 - $50,000", "2026-06-14"),
        _tx("C", "XOM", "sale_full", "$100,001 - $250,000", "2026-06-13"),
    ]
    scores = score_flows(trades, now_iso="2026-06-18T00:00:00")
    assert scores["NVDA"]["score"] > 0
    assert scores["XOM"]["score"] < 0
    assert all(-1.0 <= v["score"] <= 1.0 for v in scores.values())
    assert scores["NVDA"]["buys"] == 2 and scores["NVDA"]["sells"] == 0


def test_score_flows_recency_weighted():
    from agents.smartmoney import score_flows
    recent = [_tx("A", "AAA", "purchase", "$15,001 - $50,000", "2026-06-17")]
    old = [_tx("A", "BBB", "purchase", "$15,001 - $50,000", "2025-01-01")]
    s = score_flows(recent + old, now_iso="2026-06-18T00:00:00")
    assert s["AAA"]["score"] > s["BBB"]["score"]  # fresher disclosure weighs more


def test_score_flows_robust_to_garbage():
    from agents.smartmoney import score_flows
    trades = [
        _tx(None, "ZZZ", "purchase", None, None),
        {"ticker": "", "type": "weird"},
        _tx("X", "ZZZ", "sale", "n/a", "not-a-date"),
    ]
    scores = score_flows(trades, now_iso="2026-06-18T00:00:00")  # must not raise
    assert "" not in scores  # empty tickers dropped


def test_parse_and_score_insider_form4():
    from tools.filings import _parse_form4_events, score_insider_events
    xml = """
    <nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>5000</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>1000</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
    <nonDerivativeTransaction><transactionCoding><transactionCode>M</transactionCode></transactionCoding>
      <transactionAmounts><transactionShares><value>9999</value></transactionShares></transactionAmounts>
    </nonDerivativeTransaction>
    """
    evs = _parse_form4_events(xml)
    assert len(evs) == 3
    sc = score_insider_events(evs)
    assert sc["n_buys"] == 1 and sc["n_sells"] == 1  # M (option exercise) ignored
    assert sc["score"] > 0  # an open-market BUY outweighs a smaller sale


def test_score_insider_all_routine_is_neutral():
    from tools.filings import score_insider_events
    sc = score_insider_events([{"code": "M", "shares": 1000}, {"code": "F", "shares": 500}])
    assert sc["score"] == 0.0 and sc["n_buys"] == 0 and sc["n_sells"] == 0


def test_score_insider_pure_selling_is_only_mildly_bearish():
    """Routine insider selling (no buys) must NOT produce a strong bearish signal —
    insiders sell for many reasons. Capped at a mild lean."""
    from tools.filings import score_insider_events
    many_sells = [{"code": "S", "shares": 50000} for _ in range(16)]
    sc = score_insider_events(many_sells)
    assert sc["n_buys"] == 0 and sc["n_sells"] == 16
    assert -0.31 <= sc["score"] <= -0.0  # mild, capped — not -1.0


def test_score_insider_buying_beats_selling():
    from tools.filings import score_insider_events
    mixed = [{"code": "P", "shares": 20000}, {"code": "S", "shares": 5000}]
    assert score_insider_events(mixed)["score"] > 0.2  # open-market buy dominates


def test_amount_weight_monotonic_across_bands():
    """Bug fix: thousands-separator commas must not invert the weighting — larger
    disclosure bands must weigh >= smaller ones."""
    from agents.smartmoney import _amount_weight
    small = _amount_weight("$1,001 - $15,000")
    mid = _amount_weight("$50,001 - $100,000")
    big = _amount_weight("$1,000,001 - $5,000,000")
    assert small < mid < big
    assert big <= 2.0 and small >= 0.4


def test_smartmoney_uses_insider_signal(monkeypatch):
    """With insider Form-4 data available, the agent emits a signed signal even when
    the congressional feed is down (the real-world resilience case)."""
    import asyncio

    from agents.smartmoney import SmartMoneyAgent

    sm = SmartMoneyAgent.__new__(SmartMoneyAgent)
    sm.name = "SmartMoneyAgent"
    sm.watchlist = ["NVDA", "XOM"]
    sm.router = type("R", (), {"resolve": lambda self, n: {"model": "t"}})()
    written = {}
    sm.bb = type("BB", (), {"write_report": lambda self, r: written.update(report=r)})()
    import structlog
    sm.log = structlog.get_logger("t")

    class _Rec:
        id = "tc"

    async def fake_call(agent, tool, **kw):
        if tool == "insider_transactions":
            if kw.get("ticker") == "NVDA":
                return ({"available": True, "score": 0.5, "n_buys": 3, "n_sells": 0,
                         "buyers": ["CEO Jensen"]}, _Rec())
            return ({"available": True, "score": 0.0, "n_buys": 0, "n_sells": 0, "buyers": []}, _Rec())
        if tool == "congress_trades":
            return ({"trades": [], "available": False}, _Rec())  # feed DOWN (real-world 403)
        return ({}, _Rec())

    sm.tools = type("T", (), {"call": staticmethod(fake_call)})()
    rep = asyncio.run(sm.run("c1"))
    assert rep.asset_signals.get("NVDA", 0) > 0  # insider buy registered
    assert "NVDA" in rep.assets
    assert rep.stance == "bullish"
    # congress down -> agent notes it honestly rather than pretending
    assert any("congressional" in f.lower() for f in rep.findings)


def test_smartmoney_report_emits_asset_signals(monkeypatch):
    """The agent must emit numeric asset_signals (the deterministic edge channel)."""
    import asyncio

    from agents.smartmoney import SmartMoneyAgent

    sm = SmartMoneyAgent.__new__(SmartMoneyAgent)
    sm.name = "SmartMoneyAgent"
    sm.watchlist = ["NVDA", "XOM"]

    class _R:
        def resolve(self, _n):
            return {"model": "test"}
    sm.router = _R()

    written = {}

    class _BB:
        def write_report(self, r):
            written["report"] = r
    sm.bb = _BB()

    class _Rec:
        id = "tc1"

    async def fake_call(agent, tool, **kw):
        if tool == "congress_trades":
            return ({"trades": [
                _tx("A", "NVDA", "purchase", "$50,001 - $100,000", "2026-06-15"),
                _tx("B", "NVDA", "purchase", "$15,001 - $50,000", "2026-06-14"),
                _tx("C", "XOM", "sale_full", "$100,001 - $250,000", "2026-06-13"),
            ], "source": "house"}, _Rec())
        return ({"filings": []}, _Rec())

    sm.tools = type("T", (), {"call": staticmethod(fake_call)})()
    import structlog
    sm.log = structlog.get_logger("test")

    rep = asyncio.run(sm.run("c1"))
    assert rep.asset_signals
    assert rep.asset_signals.get("NVDA", 0) > 0
    assert rep.asset_signals.get("XOM", 0) < 0
    assert "NVDA" in rep.assets
    assert rep.stance in ("bullish", "bearish", "neutral")
