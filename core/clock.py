"""Authoritative time. Every agent is told the real current time (to the second,
with timezone) so date/time reasoning is never guessed from stale training data.
"""

from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def time_context() -> str:
    n = now_utc()
    local = n.astimezone()  # machine local tz, for human reference
    return (
        f"CURRENT TIME (authoritative, do not guess): "
        f"{n.isoformat(timespec='seconds')} "
        f"({n.strftime('%A %d %B %Y %H:%M:%S')} UTC; "
        f"local {local.strftime('%H:%M:%S %Z%z')}). "
        f"unix={int(n.timestamp())}."
    )
