"""Macro data. FRED (optional free key) for US series; frankfurter.app for FX
history (ECB, no key). Degrades to 'unavailable' when a key is missing or offline.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from core.config import env
from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("macro")
_cache = DiskCache("macro", ttl_s=6 * 3600)

# A few useful FRED series ids.
FRED_SERIES = {
    "fed_funds": "DFF",
    "cpi": "CPIAUCSL",
    "unemployment": "UNRATE",
    "10y_yield": "DGS10",
    "2y_yield": "DGS2",
    "dollar_index": "DTWEXBGS",
}


async def fred_series(series_id: str, limit: int = 60) -> dict:
    """Fetch a FRED series. Requires FRED_API_KEY; degrades gracefully if absent."""
    api_key = env("FRED_API_KEY")
    if not api_key:
        return {"series_id": series_id, "observations": [], "available": False, "reason": "no FRED_API_KEY"}

    key = f"fred:{series_id}:{limit}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"series_id": series_id, "observations": val, "stale": stale, "source": "fred"}

    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": str(limit),
    }
    try:
        async with httpx.AsyncClient(timeout=20) as c:
            resp = await c.get("https://api.stlouisfed.org/fred/series/observations", params=params)
            resp.raise_for_status()
            data = resp.json()
        obs = [{"date": o["date"], "value": o["value"]} for o in data.get("observations", [])]
        _cache.set(key, obs)
        return {"series_id": series_id, "observations": obs, "stale": False, "source": "fred"}
    except Exception as exc:
        log.warning("fred_failed", series=series_id, error=str(exc))
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return {"series_id": series_id, "observations": stale_hit[0], "stale": True, "source": "fred"}
        return {"series_id": series_id, "observations": [], "available": False, "stale": True}


# Keyless market proxies for the headline macro series (no FRED key needed).
# Each maps to a yfinance ticker whose latest close approximates the series.
_PROXY_TICKERS = {
    "10y_yield": "^TNX",     # CBOE 10y yield index (value = yield*10? no: ^TNX ~ yield)
    "2y_yield": "^FVX",      # 5y as a short-rate proxy (2y not on yfinance)
    "volatility_vix": "^VIX",
    "dollar_index": "DX-Y.NYB",
    "oil_wti": "CL=F",
    "gold": "GC=F",
}


async def _proxy_snapshot() -> dict:
    """Keyless macro proxies via yfinance: levels + 21d change so the MacroAgent has a
    signed read on rates/vol/dollar/commodities even without a FRED key."""
    from tools.market import get_history

    series: dict = {}
    tilt_bits: list[str] = []
    for name, tkr in _PROXY_TICKERS.items():
        try:
            res = await get_history(tkr, period="3mo", interval="1d")
            bars = res.get("bars") or []
            closes = [b["close"] for b in bars if b.get("close") is not None]
            if len(closes) < 5:
                series[name] = None
                continue
            latest = closes[-1]
            ago = closes[-22] if len(closes) >= 22 else closes[0]
            chg = (latest / ago - 1.0) if ago else 0.0
            series[name] = {"value": round(latest, 4), "chg_21d_pct": round(chg * 100, 2),
                            "proxy": tkr}
            if name in ("10y_yield", "volatility_vix") and abs(chg) > 0.05:
                tilt_bits.append(f"{name} {'up' if chg > 0 else 'down'} {abs(chg)*100:.0f}% (21d)")
        except Exception:
            series[name] = None
    available = any(v is not None for v in series.values())
    # compute the yield-curve label DETERMINISTICALLY so the LLM can't invert it (2y<10y is
    # NORMAL upward-sloping, not 'inverted'). ^FVX(5y) stands in for the short leg.
    out = {"series": series, "available": available,
           "tilt": "; ".join(tilt_bits) or "no strong 21d macro move",
           "source": "yfinance proxies (keyless)"}
    ten = (series.get("10y_yield") or {}).get("value")
    short = (series.get("2y_yield") or {}).get("value")
    if ten is not None and short is not None:
        spread = round(ten - short, 2)
        label = ("INVERTED (short>long — classic recession signal)" if spread < -0.05
                 else "flat" if spread < 0.15 else "NORMAL upward-sloping (long>short)")
        out["yield_curve"] = {"long_10y": ten, "short_5y": short, "spread_pp": spread,
                              "label": label}
    return out


async def macro_snapshot() -> dict:
    """Headline macro series. Prefers FRED (if key present); otherwise falls back to
    keyless yfinance market proxies so MacroAgent is never starved of data."""
    out: dict = {"fetched_at": datetime.now(timezone.utc).isoformat(), "series": {}}
    have_fred = bool(env("FRED_API_KEY"))
    if have_fred:
        for name, sid in FRED_SERIES.items():
            res = await fred_series(sid, limit=1)
            obs = res.get("observations") or []
            out["series"][name] = obs[0] if obs else None
        out["available"] = True
        out["source"] = "fred"
        return out
    # keyless fallback
    proxy = await _proxy_snapshot()
    out["series"] = proxy["series"]
    out["available"] = proxy["available"]
    out["tilt"] = proxy["tilt"]
    out["source"] = proxy["source"]
    if proxy.get("yield_curve"):
        out["yield_curve"] = proxy["yield_curve"]
    return out
