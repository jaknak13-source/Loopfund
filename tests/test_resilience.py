"""Phase-1.6 resilience: timeouts must not 3x-stall the serialized loop or drop
the whole agent report; dead/keyless feeds must degrade gracefully."""

from __future__ import annotations

import httpx
import pytest


def test_lmstudio_does_not_retry_on_timeout():
    """A ReadTimeout already consumed the full budget; retrying it 3x stalls the
    single-slot loop for ~9 min. It must fail once, not three times."""
    from models_adapter.lmstudio import LMStudioBackend

    calls = {"n": 0}
    backend = LMStudioBackend("http://localhost:9", "k")

    async def boom(*a, **k):
        calls["n"] += 1
        raise httpx.ReadTimeout("model busy")

    import asyncio

    # monkeypatch the inner client call via the public method's httpx use:
    # easiest is to patch httpx.AsyncClient.post
    orig = httpx.AsyncClient.post
    httpx.AsyncClient.post = boom  # type: ignore[assignment]
    try:
        with pytest.raises(httpx.TimeoutException):
            asyncio.run(backend.complete([], model="m", timeout=0.01))
    finally:
        httpx.AsyncClient.post = orig  # type: ignore[assignment]
    assert calls["n"] == 1  # NOT 3


def test_lmstudio_still_retries_transient_connection_error():
    """Genuine transient errors (connection refused) should still be retried."""
    from models_adapter.lmstudio import LMStudioBackend

    calls = {"n": 0}
    backend = LMStudioBackend("http://localhost:9", "k")

    async def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("refused")

        class _R:
            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return _R()

    import asyncio

    orig = httpx.AsyncClient.post
    httpx.AsyncClient.post = flaky  # type: ignore[assignment]
    try:
        out = asyncio.run(backend.complete([], model="m", timeout=1))
    finally:
        httpx.AsyncClient.post = orig  # type: ignore[assignment]
    assert out == "ok"
    assert calls["n"] == 2  # retried once then succeeded


def test_macro_snapshot_keyless_fallback(monkeypatch):
    """With no FRED key, macro_snapshot must still return real data via yfinance proxies."""
    import asyncio

    import tools.macro as macro
    import tools.market as market

    monkeypatch.setattr(macro, "env", lambda *a, **k: None)  # no FRED key

    async def fake_history(ticker, period="1y", interval="1d"):
        base = 100.0
        bars = [{"close": base * (1 + 0.001 * i)} for i in range(60)]  # gentle uptrend
        return {"ticker": ticker, "bars": bars}

    monkeypatch.setattr(market, "get_history", fake_history)
    snap = asyncio.run(macro.macro_snapshot())
    assert snap["available"] is True
    assert "proxies" in snap.get("source", "")
    assert snap["series"]["10y_yield"]["value"] > 0
    assert "chg_21d_pct" in snap["series"]["10y_yield"]
