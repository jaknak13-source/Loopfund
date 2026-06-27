"""SQLite persistence layer. Single file, WAL mode, survives restarts.

Each record type gets its own table storing the full pydantic JSON plus a few
indexed columns for cheap filtering. Thread-safe via a per-call connection.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from core.config import data_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    cycle_id TEXT,
    agent TEXT,
    created_at TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_cycle ON reports(cycle_id);
CREATE INDEX IF NOT EXISTS idx_reports_agent ON reports(agent);

CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    decision_date TEXT,
    created_at TEXT,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    decision_id TEXT,
    asset TEXT,
    status TEXT,
    created_at TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trades_asset ON trades(asset);

CREATE TABLE IF NOT EXISTS tool_calls (
    id TEXT PRIMARY KEY,
    agent TEXT,
    tool TEXT,
    created_at TEXT,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory (
    id TEXT PRIMARY KEY,
    kind TEXT,
    created_at TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memory_kind ON memory(kind);

CREATE TABLE IF NOT EXISTS instructions (
    id TEXT PRIMARY KEY,
    active INTEGER,
    created_at TEXT,
    json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
    id TEXT PRIMARY KEY,
    agent TEXT,
    kind TEXT,
    cycle_id TEXT,
    created_at TEXT,
    search TEXT,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_agent ON activity(agent);
CREATE INDEX IF NOT EXISTS idx_activity_kind ON activity(kind);
CREATE INDEX IF NOT EXISTS idx_activity_cycle ON activity(cycle_id);
"""


class SqliteStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_dir() / "loopfund.db")
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _put(self, table: str, columns: dict[str, Any], payload: str) -> None:
        cols = ["id", *[c for c in columns if c != "id"], "json"]
        placeholders = ", ".join("?" for _ in cols)
        values = [columns["id"], *[columns[c] for c in cols if c not in ("id", "json")], payload]
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET json=excluded.json"
        )
        with self._conn() as conn:
            conn.execute(sql, values)

    def _get(self, table: str, id_: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(f"SELECT json FROM {table} WHERE id=?", (id_,)).fetchone()
        return json.loads(row["json"]) if row else None

    def _query(self, table: str, where: str = "", params: tuple = (), limit: int = 200) -> list[dict[str, Any]]:
        sql = f"SELECT json FROM {table}"
        if where:
            sql += f" WHERE {where}"
        sql += " ORDER BY created_at DESC LIMIT ?"
        with self._conn() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def query_activity(self, agent: str = "", kind: str = "", cycle_id: str = "",
                       q: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses, params = [], []
        if agent:
            clauses.append("agent=?")
            params.append(agent)
        if kind:
            clauses.append("kind=?")
            params.append(kind)
        if cycle_id:
            clauses.append("cycle_id=?")
            params.append(cycle_id)
        if q:
            clauses.append("search LIKE ?")
            params.append(f"%{q.lower()}%")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = f"SELECT json FROM activity{where} ORDER BY created_at DESC LIMIT ?"
        with self._conn() as conn:
            rows = conn.execute(sql, (*params, limit)).fetchall()
        return [json.loads(r["json"]) for r in rows]

    def memory_index(self) -> list[dict[str, Any]]:
        """Lightweight (id, kind, created_at) listing of all memory rows."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, kind, created_at FROM memory ORDER BY created_at ASC"
            ).fetchall()
        return [{"id": r["id"], "kind": r["kind"], "created_at": r["created_at"]} for r in rows]

    def delete(self, table: str, ids: list[str]) -> int:
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._conn() as conn:
            cur = conn.execute(f"DELETE FROM {table} WHERE id IN ({placeholders})", ids)
            return cur.rowcount

    def prune_table(self, table: str, keep: int = 2000) -> int:
        """Keep only the most recent `keep` rows of a high-volume table (e.g.
        tool_calls). Prevents unbounded DB growth over long runs."""
        with self._conn() as conn:
            cur = conn.execute(
                f"DELETE FROM {table} WHERE id NOT IN "
                f"(SELECT id FROM {table} ORDER BY created_at DESC LIMIT ?)", (keep,)
            )
            return cur.rowcount
