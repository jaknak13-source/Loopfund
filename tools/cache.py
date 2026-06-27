"""Tiny disk cache with TTL. Reduces API hits and gives graceful degradation:
when the network is down, a stale cached value can still be served (flagged).
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from core.config import data_dir


class DiskCache:
    def __init__(self, namespace: str, ttl_s: int = 900) -> None:
        self.dir = data_dir() / "cache" / namespace
        self.dir.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_s

    def _path(self, key: str) -> Path:
        h = hashlib.sha256(key.encode()).hexdigest()[:24]
        return self.dir / f"{h}.json"

    def get(self, key: str, allow_stale: bool = False) -> tuple[Any, bool] | None:
        """Return (value, stale) or None if absent. stale=True if past TTL."""
        p = self._path(key)
        if not p.exists():
            return None
        try:
            blob = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        age = time.time() - blob["ts"]
        stale = age > self.ttl
        if stale and not allow_stale:
            return None
        return blob["val"], stale

    def set(self, key: str, value: Any) -> None:
        self._path(key).write_text(
            json.dumps({"ts": time.time(), "val": value}), encoding="utf-8"
        )
