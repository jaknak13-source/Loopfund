"""Backups + recovery. Snapshots the runtime state (DB, portfolio, learning,
state, vector index) so memory and P&L survive crashes and can be restored or
reset. A daily backup runs automatically; crash backups run on unhandled errors.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from core.config import data_dir
from core.logging import get_logger

log = get_logger("backup")

_FILES = ["loopfund.db", "portfolio.json", "state.json", "learning.json"]
_DIRS = ["vector"]


def _backups_dir() -> Path:
    d = data_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def backup_now(tag: str | None = None) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    name = ts if not tag else f"{ts}_{tag}_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    dest = _backups_dir() / name
    dest.mkdir(parents=True, exist_ok=True)
    d = data_dir()
    for f in _FILES:
        p = d / f
        if p.exists():
            shutil.copy2(p, dest / f)
    for sub in _DIRS:
        p = d / sub
        if p.exists():
            shutil.copytree(p, dest / sub, dirs_exist_ok=True)
    log.info("backup_created", path=str(dest))
    return dest


def list_backups() -> list[str]:
    return sorted(p.name for p in _backups_dir().iterdir() if p.is_dir())


def prune(keep: int = 14) -> None:
    backups = list_backups()
    for name in backups[:-keep] if len(backups) > keep else []:
        shutil.rmtree(_backups_dir() / name, ignore_errors=True)


def maybe_daily_backup(state: dict, keep: int = 14) -> str | None:
    """Run one backup per real day. `state` tracks the last backup date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if state.get("last_backup_date") == today:
        return None
    path = backup_now()
    prune(keep)
    state["last_backup_date"] = today
    return str(path)


def restore(name: str) -> bool:
    """Restore a named backup into the live data dir. Returns True on success."""
    root = _backups_dir().resolve()
    src = (root / name).resolve()
    # Containment check: reject path traversal (e.g. name="../../etc") so restore
    # can only ever read from a named backup INSIDE the backups directory.
    if src == root or not src.is_relative_to(root):
        return False
    if not src.is_dir():
        return False
    backup_now(tag="pre_restore")  # safety snapshot of current state first
    d = data_dir()
    for f in _FILES:
        p = src / f
        if p.exists():
            shutil.copy2(p, d / f)
    for sub in _DIRS:
        p = src / sub
        if p.exists():
            shutil.rmtree(d / sub, ignore_errors=True)
            shutil.copytree(p, d / sub)
    log.info("backup_restored", name=name)
    return True


def reset(make_backup: bool = True) -> None:
    """Wipe runtime state for a fresh start (after a safety backup)."""
    if make_backup:
        backup_now(tag="pre_reset")
    d = data_dir()
    for f in _FILES + ["loopfund.db-wal", "loopfund.db-shm"]:
        (d / f).unlink(missing_ok=True)
    for sub in _DIRS + ["cache"]:
        shutil.rmtree(d / sub, ignore_errors=True)
    log.info("state_reset")
