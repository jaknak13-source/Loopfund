"""News via free RSS feeds and the GDELT 2.0 doc API (no key). Returns deduped,
normalized articles. Niche/social claims are LEADS, not evidence — that
distinction is enforced by agents, not here.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time

import feedparser
import httpx

from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("news")
_cache = DiskCache("news", ttl_s=900)

# GDELT free tier rate-limits aggressively. Space calls out and, on a 429, back off
# for a cooldown window so we stop hammering it (serve cache/empty meanwhile).
_GDELT_MIN_INTERVAL = 6.0      # seconds between GDELT requests
_GDELT_COOLDOWN = 300.0        # seconds to skip GDELT after a 429
_gdelt = {"last": 0.0, "cooldown_until": 0.0}

DEFAULT_FEEDS = [
    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "https://www.ft.com/rss/home",
    "https://feeds.bloomberg.com/markets/news.rss",
    "https://www.reutersagency.com/feed/?best-topics=business-finance",
    "http://feeds.marketwatch.com/marketwatch/topstories/",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",
]


def _hash(title: str) -> str:
    return hashlib.sha256(title.strip().lower().encode()).hexdigest()[:16]


def _parse_feed_sync(url: str, limit: int) -> list[dict]:
    d = feedparser.parse(url)
    out = []
    for e in d.entries[:limit]:
        out.append(
            {
                "title": getattr(e, "title", ""),
                "link": getattr(e, "link", ""),
                "published": getattr(e, "published", ""),
                "summary": getattr(e, "summary", "")[:500],
                "source": d.feed.get("title", url) if hasattr(d, "feed") else url,
            }
        )
    return out


async def rss_headlines(feeds: list[str] | None = None, per_feed: int = 10) -> dict:
    feeds = feeds or DEFAULT_FEEDS
    key = f"rss:{','.join(feeds)}:{per_feed}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"articles": val, "stale": stale, "source": "rss"}

    articles: list[dict] = []
    seen: set[str] = set()
    for url in feeds:
        try:
            items = await asyncio.to_thread(_parse_feed_sync, url, per_feed)
        except Exception as exc:
            log.warning("feed_failed", url=url, error=str(exc))
            continue
        for it in items:
            h = _hash(it["title"])
            if h and h not in seen:
                seen.add(h)
                articles.append(it)

    if articles:
        _cache.set(key, articles)
        return {"articles": articles, "stale": False, "source": "rss"}
    stale_hit = _cache.get(key, allow_stale=True)
    if stale_hit is not None:
        return {"articles": stale_hit[0], "stale": True, "source": "rss"}
    return {"articles": [], "stale": True, "available": False, "source": "rss"}


def _gdelt_result(query: str, arts: list, stale: bool, available: bool = True, reason: str | None = None) -> dict:
    out = {"query": query, "articles": arts, "stale": stale, "source": "gdelt", "available": available}
    if reason:
        out["reason"] = reason
    return out


async def gdelt_search(query: str, max_records: int = 25) -> dict:
    """Search global news via GDELT. Free tier is heavily rate-limited, so we cache,
    throttle, and back off on 429 — degrading to cached/empty results, never erroring."""
    key = f"gdelt:{query}:{max_records}"
    cached = _cache.get(key)
    if cached is not None:
        return _gdelt_result(query, cached[0], cached[1])

    now = time.time()
    # in cooldown after a recent 429 -> don't hit the API at all
    if now < _gdelt["cooldown_until"]:
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return _gdelt_result(query, stale_hit[0], True)
        return _gdelt_result(query, [], True, available=False, reason="rate-limit cooldown")

    # space requests out to stay under the free-tier limit
    wait = _GDELT_MIN_INTERVAL - (now - _gdelt["last"])
    if wait > 0:
        await asyncio.sleep(wait)
    _gdelt["last"] = time.time()

    params = {"query": query, "mode": "ArtList", "maxrecords": str(max_records),
              "format": "json", "sort": "DateDesc"}
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "loopfund/0.1"}) as c:
            resp = await c.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params)

        if resp.status_code == 429:
            _gdelt["cooldown_until"] = time.time() + _GDELT_COOLDOWN
            log.info("gdelt_rate_limited", query=query, cooldown_s=_GDELT_COOLDOWN)
            stale_hit = _cache.get(key, allow_stale=True)
            return _gdelt_result(query, stale_hit[0] if stale_hit else [], True,
                                 available=bool(stale_hit), reason="rate-limited (429)")
        resp.raise_for_status()

        # GDELT sometimes returns an empty or non-JSON body on 200 -> treat as no results
        text = (resp.text or "").strip()
        if not text:
            _cache.set(key, [])
            return _gdelt_result(query, [], False)
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            log.info("gdelt_non_json", query=query)  # benign: empty/HTML body, not an error
            _cache.set(key, [])
            return _gdelt_result(query, [], False)

        arts = [
            {"title": a.get("title", ""), "link": a.get("url", ""),
             "published": a.get("seendate", ""), "source": a.get("domain", ""),
             "language": a.get("language", "")}
            for a in data.get("articles", [])
        ]
        _cache.set(key, arts)
        return _gdelt_result(query, arts, False)
    except Exception as exc:
        log.warning("gdelt_failed", query=query, error=str(exc))
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return _gdelt_result(query, stale_hit[0], True)
        return _gdelt_result(query, [], True, available=False)
