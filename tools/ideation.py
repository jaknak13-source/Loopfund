"""Ideation fuel: pull RANDOM past memory entries so creative agents can collide
unrelated findings into novel research directions and cross-market connections.
Reads the live memory table directly (read-only)."""

from __future__ import annotations

import json

from core.config import data_dir
from core.logging import get_logger

log = get_logger("ideation")


async def random_memory(n: int = 6, kind: str | None = None) -> dict:
    """Return n RANDOM stored memory entries (title + snippet) as raw material for
    lateral thinking. Optionally filter by kind (news/report/lesson/...)."""
    import sqlite3

    db = data_dir() / "loopfund.db"
    if not db.exists():
        return {"entries": [], "available": False, "reason": "no memory yet"}
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        if kind:
            rows = con.execute("SELECT json FROM memory WHERE kind=? ORDER BY RANDOM() LIMIT ?",
                               (kind, n)).fetchall()
        else:
            rows = con.execute("SELECT json FROM memory ORDER BY RANDOM() LIMIT ?", (n,)).fetchall()
        con.close()
    except Exception as exc:
        log.warning("random_memory_failed", error=str(exc))
        return {"entries": [], "available": False, "error": str(exc)}
    out = []
    for r in rows:
        try:
            o = json.loads(r[0])
            out.append({"kind": o.get("kind"), "title": o.get("title", ""),
                        "snippet": (o.get("body", "") or "")[:240], "assets": o.get("assets", [])})
        except json.JSONDecodeError:
            continue
    return {"entries": out, "n": len(out), "source": "random_memory"}
