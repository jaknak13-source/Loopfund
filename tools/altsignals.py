"""Alternative public signals (free, no key): US Congress stock trades and
Polymarket prediction-market probabilities. Both are LEADS/sentiment — verify
against primary sources before acting; never trade on them alone.
"""

from __future__ import annotations

import httpx

from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("altsignals")
_cache = DiskCache("altsignals", ttl_s=6 * 3600)

_HOUSE = "https://house-stock-watcher-data.s3-us-west-2.amazonaws.com/data/all_transactions.json"


async def congress_trades(limit: int = 40, ticker: str | None = None) -> dict:
    """Recent US House stock disclosures (free public dataset). Optionally filter by ticker."""
    cached = _cache.get("house_tx")
    if cached is not None:
        rows = cached[0]
    else:
        try:
            async with httpx.AsyncClient(timeout=30, headers={"User-Agent": "loopfund/0.1"}) as c:
                r = await c.get(_HOUSE)
                r.raise_for_status()
                rows = r.json()
            _cache.set("house_tx", rows[-4000:])  # keep recent slice
        except Exception as exc:
            log.warning("congress_failed", error=str(exc))
            stale = _cache.get("house_tx", allow_stale=True)
            if stale is None:
                return {"trades": [], "available": False, "error": str(exc)}
            rows = stale[0]
    if ticker:
        t = ticker.upper()
        rows = [r for r in rows if str(r.get("ticker", "")).upper() == t]
    recent = rows[-limit:]
    trades = [
        {"rep": r.get("representative"), "ticker": r.get("ticker"),
         "type": r.get("type"), "amount": r.get("amount"),
         "date": r.get("transaction_date"), "disclosed": r.get("disclosure_date")}
        for r in recent
    ]
    return {"trades": list(reversed(trades)), "source": "house-stock-watcher",
            "stale": cached[1] if cached else False}


async def polymarket_markets(limit: int = 15, query: str | None = None) -> dict:
    """Top active Polymarket markets by volume + implied probabilities (sentiment)."""
    key = f"poly:{limit}:{query or ''}"
    cached = _cache.get(key)
    if cached is not None:
        return {"markets": cached[0], "stale": cached[1], "source": "polymarket"}
    params = {"closed": "false", "order": "volume", "ascending": "false", "limit": str(limit)}
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "loopfund/0.1"}) as c:
            r = await c.get("https://gamma-api.polymarket.com/markets", params=params)
            r.raise_for_status()
            data = r.json()
        out = []
        for m in (data if isinstance(data, list) else data.get("data", [])):
            q = str(m.get("question", ""))
            if query and query.lower() not in q.lower():
                continue
            out.append({"question": q, "volume": m.get("volume"),
                        "outcomes": m.get("outcomes"), "prices": m.get("outcomePrices"),
                        "end": m.get("endDate")})
        out = out[:limit]
        _cache.set(key, out)
        return {"markets": out, "stale": False, "source": "polymarket"}
    except Exception as exc:
        log.warning("polymarket_failed", error=str(exc))
        stale = _cache.get(key, allow_stale=True)
        if stale is not None:
            return {"markets": stale[0], "stale": True, "source": "polymarket"}
        return {"markets": [], "available": False, "error": str(exc)}
