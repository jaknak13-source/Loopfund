"""Let agents grow the tradable universe themselves. When research surfaces a name
not yet tracked, an agent calls `propose_ticker` — it's added to the dynamic
universe and priced, so future cycles will research it. This is how the fund
expands beyond its seed list to any public name it discovers."""

from __future__ import annotations

from config.universe import add_ticker
from core.logging import get_logger
from tools import market

log = get_logger("universe")


async def propose_ticker(ticker: str, reason: str = "") -> dict:
    t = (ticker or "").strip().upper()
    if not t:
        return {"ok": False, "reason": "empty ticker"}
    added = add_ticker(t, reason)
    # verify it's real / priceable
    px = await market.get_price(t)
    priceable = px.get("price") is not None
    log.info("ticker_proposed", ticker=t, added=added, priceable=priceable)
    return {"ok": priceable, "ticker": t, "newly_added": added,
            "price": px.get("price"), "ccy": px.get("ccy"), "reason": reason[:200],
            "note": None if priceable else "could not price — may be invalid/delisted"}
