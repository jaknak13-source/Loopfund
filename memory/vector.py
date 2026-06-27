"""Persistent vector index. numpy matrix on disk, cosine top-k search. Small-scale
(thousands of entries) — fine for a single-machine research fund. No server.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from core.config import data_dir
from core.logging import get_logger
from memory.embeddings import Embedder, HashingEmbedder

log = get_logger("vector")


class VectorStore:
    def __init__(self, embedder: Embedder | None = None, path: Path | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        base = (data_dir() / "vector")
        base.mkdir(parents=True, exist_ok=True)
        # index file is keyed by embedding dim, so switching embedders starts a SEPARATE
        # index instead of silently zeroing the existing one (that was a recall-data-loss bug).
        sig = getattr(self.embedder, "sig", None) or f"dim{self.embedder.dim}"
        self.path = path or (base / f"index-{sig}.npz")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # only adopt a pre-keying legacy index for the DEFAULT (production) path —
        # never for an explicit custom path (tests), or we'd read the live index.
        self._legacy = (base / "index.npz") if path is None else None
        self.ids: list[str] = []
        self.matrix: np.ndarray = np.zeros((0, self.embedder.dim), dtype=np.float32)
        self._load()

    def _load(self) -> None:
        src = self.path if self.path.exists() else (
            self._legacy if (self._legacy and self._legacy.exists()) else None)
        if src is None:
            return
        data = np.load(src, allow_pickle=True)
        file_sig = str(data["sig"][0]) if "sig" in data else None
        matrix = data["matrix"].astype(np.float32)
        sig = getattr(self.embedder, "sig", None) or f"dim{self.embedder.dim}"
        if file_sig != sig or (matrix.size and matrix.shape[1] != self.embedder.dim):
            # embedder changed (algo or dim): do NOT adopt stale/mismatched vectors and do NOT
            # wipe the other file — start empty for THIS embedder; RagMemory re-embeds from the DB.
            log.warning("vector_index_embedder_changed_rebuilding",
                        file_sig=file_sig, embedder_sig=sig)
            return
        self.ids, self.matrix = list(data["ids"]), matrix
        if src is self._legacy:  # migrate a matching legacy index to the keyed name once
            self._save()

    def _save(self) -> None:
        sig = getattr(self.embedder, "sig", None) or f"dim{self.embedder.dim}"
        np.savez(self.path, ids=np.array(self.ids, dtype=object), matrix=self.matrix,
                 sig=np.array([sig]))

    def add(self, entry_id: str, text: str) -> None:
        vec = self.embedder.embed(text).reshape(1, -1)
        if entry_id in self.ids:
            i = self.ids.index(entry_id)
            self.matrix[i] = vec
        else:
            self.ids.append(entry_id)
            self.matrix = np.vstack([self.matrix, vec]) if self.matrix.size else vec
        self._save()

    def remove(self, ids: list[str]) -> int:
        """Drop entries by id and rebuild the matrix. Returns count removed."""
        drop = set(ids)
        if not drop or not self.ids:
            return 0
        keep_idx = [i for i, eid in enumerate(self.ids) if eid not in drop]
        removed = len(self.ids) - len(keep_idx)
        if removed == 0:
            return 0
        self.ids = [self.ids[i] for i in keep_idx]
        self.matrix = self.matrix[keep_idx] if keep_idx else np.zeros((0, self.embedder.dim), dtype=np.float32)
        self._save()
        return removed

    def search(self, query: str, k: int = 5) -> list[tuple[str, float]]:
        if not self.ids:
            return []
        q = self.embedder.embed(query)
        scores = self.matrix @ q  # cosine (all normalized)
        order = np.argsort(-scores)[:k]
        return [(self.ids[i], float(scores[i])) for i in order]

    def __len__(self) -> int:
        return len(self.ids)
