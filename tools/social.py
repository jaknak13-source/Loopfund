"""Social sentiment sources. Reddit (PRAW, optional free creds) and StockTwits
(public). Social claims are LEADS to be verified, never evidence on their own.
"""

from __future__ import annotations

import asyncio

import httpx

from core.config import env
from core.logging import get_logger
from tools.cache import DiskCache

log = get_logger("social")
_cache = DiskCache("social", ttl_s=1800)


def _reddit_hot_sync(subreddit: str, limit: int) -> list[dict]:
    import praw  # lazy: optional dependency

    reddit = praw.Reddit(
        client_id=env("REDDIT_CLIENT_ID"),
        client_secret=env("REDDIT_CLIENT_SECRET"),
        user_agent=env("REDDIT_USER_AGENT", "loopfund/0.1"),
        check_for_async=False,
    )
    out = []
    for post in reddit.subreddit(subreddit).hot(limit=limit):
        out.append(
            {
                "title": post.title,
                "score": post.score,
                "num_comments": post.num_comments,
                "url": f"https://reddit.com{post.permalink}",
                "created_utc": post.created_utc,
                "subreddit": subreddit,
            }
        )
    return out


async def reddit_hot(subreddit: str = "investing", limit: int = 15) -> dict:
    if not (env("REDDIT_CLIENT_ID") and env("REDDIT_CLIENT_SECRET")):
        return {"subreddit": subreddit, "posts": [], "available": False, "reason": "no reddit creds"}
    key = f"reddit:{subreddit}:{limit}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"subreddit": subreddit, "posts": val, "stale": stale, "source": "reddit"}
    try:
        posts = await asyncio.to_thread(_reddit_hot_sync, subreddit, limit)
        _cache.set(key, posts)
        return {"subreddit": subreddit, "posts": posts, "stale": False, "source": "reddit"}
    except ImportError:
        return {"subreddit": subreddit, "posts": [], "available": False, "reason": "praw not installed"}
    except Exception as exc:
        log.warning("reddit_failed", subreddit=subreddit, error=str(exc))
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return {"subreddit": subreddit, "posts": stale_hit[0], "stale": True, "source": "reddit"}
        return {"subreddit": subreddit, "posts": [], "available": False, "stale": True}


async def stocktwits_symbol(symbol: str, limit: int = 20) -> dict:
    symbol = symbol.upper()
    key = f"st:{symbol}:{limit}"
    cached = _cache.get(key)
    if cached is not None:
        val, stale = cached
        return {"symbol": symbol, "messages": val, "stale": stale, "source": "stocktwits"}
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
    try:
        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": "loopfund/0.1"}) as c:
            resp = await c.get(url)
            resp.raise_for_status()
            data = resp.json()
        msgs = []
        for m in data.get("messages", [])[:limit]:
            sentiment = (m.get("entities") or {}).get("sentiment") or {}
            msgs.append(
                {
                    "body": m.get("body", ""),
                    "created_at": m.get("created_at", ""),
                    "sentiment": sentiment.get("basic"),
                    "user": (m.get("user") or {}).get("username"),
                }
            )
        _cache.set(key, msgs)
        return {"symbol": symbol, "messages": msgs, "stale": False, "source": "stocktwits"}
    except Exception as exc:
        log.warning("stocktwits_failed", symbol=symbol, error=str(exc))
        stale_hit = _cache.get(key, allow_stale=True)
        if stale_hit is not None:
            return {"symbol": symbol, "messages": stale_hit[0], "stale": True, "source": "stocktwits"}
        return {"symbol": symbol, "messages": [], "available": False, "stale": True}
