"""RAG memory: structured storage (blackboard/SQLite) + vector index for
semantic recall. Every agent writes findings here and queries it before working,
so the system avoids repeating facts and past mistakes.
"""

from __future__ import annotations

from pathlib import Path

from core.blackboard import Blackboard
from memory.embeddings import Embedder
from memory.vector import VectorStore
from schemas import MemoryEntry


class RagMemory:
    def __init__(
        self,
        blackboard: Blackboard,
        embedder: Embedder | None = None,
        vector_path: Path | None = None,
    ) -> None:
        self.bb = blackboard
        self.vectors = VectorStore(embedder=embedder, path=vector_path)
        self._cache: dict[str, MemoryEntry] = {}
        self._rebuild_if_stale()

    def _rebuild_if_stale(self) -> None:
        """If the vector index is empty but the DB holds memory (e.g. the embedder changed,
        so a fresh dim/sig-keyed index was started), re-embed every stored entry. Keeps recall
        working after an embedder upgrade instead of silently losing it. Hashing re-embed is
        fast and offline."""
        try:
            idx = self.bb.store.memory_index()
            if not idx or len(self.vectors) >= len(idx):
                return
            for row in idx:
                entry = self._get(row["id"])
                if entry is not None and row["id"] not in self.vectors.ids:
                    self.vectors.add(entry.id, f"{entry.title}\n{entry.body}\n{' '.join(entry.tags)}")
        except Exception:
            pass  # rebuild is best-effort; never block startup

    def add(self, entry: MemoryEntry) -> None:
        # Dedup: the research loop re-saves near-identical theses ("Developing thesis: QQQ")
        # every cycle, bloating memory and diluting recall. Skip a new entry whose (kind,
        # title) matches a recent same-kind entry with a near-identical body.
        if self._is_duplicate(entry):
            return
        self.bb.write_memory(entry)
        self.vectors.add(entry.id, f"{entry.title}\n{entry.body}\n{' '.join(entry.tags)}")
        self._cache[entry.id] = entry

    def _is_duplicate(self, entry: MemoryEntry) -> bool:
        try:
            recent = self.bb.memory_by_kind(entry.kind, limit=60)
        except Exception:
            return False
        title = (entry.title or "").strip().lower()
        body = (entry.body or "").strip()
        for prior in recent:
            if (prior.title or "").strip().lower() != title:
                continue
            pb = (prior.body or "").strip()
            # same title + near-identical body length -> duplicate refresh, skip.
            if pb == body or (len(pb) and abs(len(pb) - len(body)) / max(len(pb), 1) < 0.05):
                return True
        return False

    def _get(self, entry_id: str) -> MemoryEntry | None:
        if entry_id in self._cache:
            return self._cache[entry_id]
        raw = self.bb.store._get("memory", entry_id)
        if raw is None:
            return None
        entry = MemoryEntry.model_validate(raw)
        self._cache[entry_id] = entry
        return entry

    def search(self, query: str, k: int = 5, kind: str | None = None) -> list[MemoryEntry]:
        hits = self.vectors.search(query, k=k * 3 if kind else k)
        out: list[MemoryEntry] = []
        for entry_id, _score in hits:
            entry = self._get(entry_id)
            if entry is None:
                continue
            if kind and entry.kind != kind:
                continue
            out.append(entry)
            if len(out) >= k:
                break
        return out

    def lessons(self, limit: int = 50) -> list[MemoryEntry]:
        return self.bb.memory_by_kind("lesson", limit=limit)

    def size(self) -> int:
        return len(self.vectors)

    # Kinds that carry durable knowledge and are never auto-pruned.
    PROTECTED_KINDS = ("lesson", "decision", "summary", "research")

    def prune(self, max_entries: int = 5000) -> int:
        """Keep memory bounded for long (weeks/months) runs. Drops the OLDEST
        non-protected entries (news/report/model_output/hypothesis) once the total
        exceeds max_entries. Lessons, decisions, and summaries are always kept.
        Returns the number removed."""
        index = self.bb.store.memory_index()  # oldest first
        if len(index) <= max_entries:
            return 0
        prunable = [r for r in index if r["kind"] not in self.PROTECTED_KINDS]
        to_remove = len(index) - max_entries
        drop_ids = [r["id"] for r in prunable[:to_remove]]
        if not drop_ids:
            return 0
        self.bb.store.delete("memory", drop_ids)
        self.vectors.remove(drop_ids)
        for did in drop_ids:
            self._cache.pop(did, None)
        return len(drop_ids)
