"""FX conversion to the EUR base currency. Source: frankfurter.app (free, ECB
reference rates, no key). Falls back to cached/stale rates when offline.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("fx")
_cache = DiskCache("fx", ttl_s=6 * 3600)
_FRANKFURTER = "https://api.frankfurter.dev/v1/latest"   # ECB, ~30 majors
_ERAPI = "https://open.er-api.com/v6/latest"              # ~160 currencies incl SAR/AED


async def _fetch_frankfurter(base: str, quote: str) -> float | None:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        resp = await c.get(_FRANKFURTER, params={"base": base, "symbols": quote})
        resp.raise_for_status()
        return float(resp.json()["rates"][quote])


async def _fetch_erapi(base: str, quote: str) -> float | None:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        resp = await c.get(f"{_ERAPI}/{base}")
        resp.raise_for_status()
        data = resp.json()
        rate = (data.get("rates") or {}).get(quote)
        return float(rate) if rate is not None else None


async def fx_rate(base: str, quote: str = "EUR") -> dict:
    """Return {rate, base, quote, source, stale}. rate: 1 base = rate quote.
    Tries ECB (frankfurter) first, then a broad provider (er-api) so exotic
    currencies (SAR, AED, ...) also convert. Degrades to stale cache when offline."""
    base = base.upper()
    quote = quote.upper()
    if base == quote:
        return {"rate": 1.0, "base": base, "quote": quote, "source": "identity", "stale": False}

    key = f"{base}->{quote}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {**val, "stale": stale}

    for fetch, src in ((_fetch_frankfurter, "frankfurter"), (_fetch_erapi, "er-api")):
        try:
            rate = await fetch(base, quote)
        except Exception:
            rate = None
        if rate is not None:
            out = {"rate": rate, "base": base, "quote": quote, "source": src,
                   "fetched_at": datetime.now(timezone.utc).isoformat()}
            _cache.set(key, out)
            return {**out, "stale": False}

    # both providers failed/lacked the pair -> stale cache if any, else unavailable
    stale_hit = _cache.get(key, allow_stale=True)
    if stale_hit is not None:
        log.warning("fx_stale_fallback", pair=key)
        return {**stale_hit[0], "stale": True}
    log.warning("fx_unavailable", pair=key)
    return {"rate": None, "base": base, "quote": quote, "source": None, "stale": True, "available": False}


async def to_eur(amount: float, ccy: str) -> float | None:
    info = await fx_rate(ccy, "EUR")
    if info.get("rate") is None:
        return None
    return amount * info["rate"]


# sync convenience for non-async call sites (ledger)
def to_eur_sync(amount: float, ccy: str) -> float | None:
    return asyncio.run(to_eur(amount, ccy))
