"""Crash resilience. On any unhandled error the system records the failure and
snapshots state so nothing is lost and the loop can keep running.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone

from core.backup import backup_now
from core.config import data_dir
from core.logging import get_logger

log = get_logger("resilience")


def record_error(where: str, exc: BaseException, snapshot: bool = True) -> dict:
    """Log an error to data/errors.jsonl and (optionally) snapshot state."""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "where": where,
        "type": type(exc).__name__,
        "error": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-4000:],
    }
    try:
        with (data_dir() / "errors.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError:
        pass
    log.error("recorded_error", where=where, type=rec["type"], error=rec["error"])
    if snapshot:
        try:
            backup_now(tag="crash")
        except Exception as bexc:  # never let backup failure mask the original error
            log.error("crash_backup_failed", error=str(bexc))
    return rec
