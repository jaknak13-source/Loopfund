"""Bounded memory: pruning keeps the RAG from growing unbounded over long runs,
while always protecting lessons/decisions/summaries."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


from core.blackboard import Blackboard
from memory.rag import RagMemory
from schemas import MemoryEntry


def _entry(eid: str, kind: str, age_min: int) -> MemoryEntry:
    return MemoryEntry(
        id=eid, kind=kind, title=f"{kind}-{eid}", body="x " + eid,
        created_at=datetime.now(timezone.utc) - timedelta(minutes=age_min),
    )


def test_prune_drops_oldest_unprotected_keeps_durable(tmp_path) -> None:
    rag = RagMemory(Blackboard(path=tmp_path / "t.db"), vector_path=tmp_path / "v" / "i.npz")
    # oldest -> newest news, plus durable lessons/decision
    rag.add(_entry("n1", "news", 50))
    rag.add(_entry("n2", "news", 40))
    rag.add(_entry("n3", "news", 30))
    rag.add(_entry("l1", "lesson", 45))
    rag.add(_entry("d1", "decision", 35))
    assert rag.size() == 5

    removed = rag.prune(max_entries=3)
    assert removed == 2  # 5 total, cap 3 -> drop 2 oldest news (n1, n2)

    ids_left = set(rag.vectors.ids)
    assert "l1" in ids_left and "d1" in ids_left   # durable kept
    assert "n3" in ids_left                          # newest news kept
    assert "n1" not in ids_left and "n2" not in ids_left
    assert rag.size() == 3


def test_prune_noop_under_cap(tmp_path) -> None:
    rag = RagMemory(Blackboard(path=tmp_path / "t.db"), vector_path=tmp_path / "v" / "i.npz")
    rag.add(_entry("n1", "news", 10))
    assert rag.prune(max_entries=100) == 0
    assert rag.size() == 1


def test_prune_table_keeps_recent(tmp_path) -> None:
    from core.store import SqliteStore

    s = SqliteStore(path=tmp_path / "t.db")
    for i in range(10):
        s._put("tool_calls",
               {"id": f"t{i}", "agent": "A", "tool": "x", "created_at": f"2026-01-01T00:00:{i:02d}"},
               "{}")
    removed = s.prune_table("tool_calls", keep=3)
    assert removed == 7
    assert len(s._query("tool_calls", limit=100)) == 3
