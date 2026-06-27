"""Market data via yfinance (free). Prices, history, light fundamentals.

yfinance is synchronous; calls are offloaded to a thread so they don't block the
event loop. Results are cached; on failure we serve stale data flagged as such.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import yfinance as yf

from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("market")
_price_cache = DiskCache("price", ttl_s=300)
_hist_cache = DiskCache("history", ttl_s=3600)
_fund_cache = DiskCache("fundamentals", ttl_s=12 * 3600)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _price_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    fi = t.fast_info
    price = getattr(fi, "last_price", None)
    ccy = getattr(fi, "currency", None)
    if price is None:  # fallback to last daily close
        hist = t.history(period="5d")
        if hist is None or hist.empty:
            raise ValueError(f"no price for {ticker}")
        price = float(hist["Close"].iloc[-1])
    if price is None:
        raise ValueError(f"no price for {ticker}")
    return {
        "ticker": ticker,
        "price": float(price),
        "ccy": (ccy or "USD"),
        "source": "yfinance",
        "fetched_at": _now(),
    }


async def get_price(ticker: str) -> dict:
    ticker = ticker.upper()
    cached = _price_cache.get(ticker)
    if cached is not None:
        val, stale = cached
        return {**val, "stale": stale}
    try:
        out = await asyncio.to_thread(_price_sync, ticker)
        _price_cache.set(ticker, out)
        return {**out, "stale": False}
    except Exception as exc:
        stale_hit = _price_cache.get(ticker, allow_stale=True)
        if stale_hit is not None:
            val, _ = stale_hit
            log.warning("price_stale_fallback", ticker=ticker, error=str(exc))
            return {**val, "stale": True}
        log.error("price_unavailable", ticker=ticker, error=str(exc))
        return {"ticker": ticker, "price": None, "stale": True, "available": False, "source": None}


def _history_sync(ticker: str, period: str, interval: str) -> list[dict]:
    df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError(f"no history for {ticker}")
    out = []
    for idx, row in df.iterrows():
        out.append(
            {
                "date": idx.isoformat(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"]),
            }
        )
    return out


async def get_history(ticker: str, period: str = "1y", interval: str = "1d") -> dict:
    ticker = ticker.upper()
    key = f"{ticker}:{period}:{interval}"
    cached = _hist_cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"ticker": ticker, "bars": val, "stale": stale, "source": "yfinance"}
    try:
        bars = await asyncio.to_thread(_history_sync, ticker, period, interval)
        _hist_cache.set(key, bars)
        return {"ticker": ticker, "bars": bars, "stale": False, "source": "yfinance"}
    except Exception as exc:
        stale_hit = _hist_cache.get(key, allow_stale=True)
        if stale_hit is not None:
            val, _ = stale_hit
            return {"ticker": ticker, "bars": val, "stale": True, "source": "yfinance"}
        log.error("history_unavailable", ticker=ticker, error=str(exc))
        return {"ticker": ticker, "bars": [], "stale": True, "available": False}


_FUND_KEYS = (
    "trailingPE", "forwardPE", "priceToBook", "marketCap", "profitMargins",
    "revenueGrowth", "debtToEquity", "dividendYield", "sector", "industry",
    "trailingEps", "freeCashflow", "totalRevenue",
)


def _fundamentals_sync(ticker: str) -> dict:
    info = yf.Ticker(ticker).get_info()
    return {k: info.get(k) for k in _FUND_KEYS}


async def get_fundamentals(ticker: str) -> dict:
    ticker = ticker.upper()
    cached = _fund_cache.get(ticker)
    if cached is not None:
        val, stale = cached
        return {"ticker": ticker, "fundamentals": val, "stale": stale, "source": "yfinance"}
    try:
        f = await asyncio.to_thread(_fundamentals_sync, ticker)
        _fund_cache.set(ticker, f)
        return {"ticker": ticker, "fundamentals": f, "stale": False, "source": "yfinance"}
    except Exception as exc:
        log.error("fundamentals_unavailable", ticker=ticker, error=str(exc))
        return {"ticker": ticker, "fundamentals": {}, "stale": True, "available": False}
