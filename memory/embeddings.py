"""Text embeddings. Default is a dependency-free deterministic hashing embedder
(works fully offline). An optional LM Studio embedder can be swapped in when a
local embedding model is loaded. RAG quality improves with the latter, but the
system must never hard-depend on it.
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

_TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(ABC):
    dim: int
    sig: str = "base"  # identity tag; the vector index is keyed by this so changing the
    # embedder (algo or dim) starts a separate index and triggers a rebuild, never a mix.

    @abstractmethod
    def embed(self, text: str) -> np.ndarray:
        raise NotImplementedError


def _hash(token: str, dim: int) -> tuple[int, float]:
    h = int(hashlib.md5(token.encode()).hexdigest(), 16)
    return h % dim, (1.0 if (h >> 8) & 1 else -1.0)


class HashingEmbedder(Embedder):
    """Feature-hashing embedder over word unigrams + bigrams + character 4-grams ->
    L2-normalized vector. Offline, deterministic, no model. The bigrams add word-order
    and the char n-grams add subword overlap, so recall is far less brittle than pure
    bag-of-words (a paraphrase or morphological variant still shares char-grams)."""

    def __init__(self, dim: int = 512) -> None:
        self.dim = dim
        self.sig = f"hash{dim}v2"

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        tokens = _TOKEN.findall(text.lower())
        if not tokens:
            return vec

        def bump(token: str, weight: float) -> None:
            idx, sign = _hash(token, self.dim)
            vec[idx] += sign * weight

        for tok in tokens:                       # unigrams (primary signal)
            bump(tok, 1.0)
            for i in range(len(tok) - 3):        # char 4-grams (subword overlap)
                bump("#" + tok[i:i + 4], 0.5)
        for a, b in zip(tokens, tokens[1:]):     # word bigrams (order/context)
            bump(f"{a}_{b}", 0.7)

        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec


class LMStudioEmbedder(Embedder):
    """Uses LM Studio's /embeddings endpoint. Requires an embedding model loaded."""

    def __init__(self, base_url: str, model: str, api_key: str = "lm-studio", dim: int = 768) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.dim = dim
        self.sig = f"lmstudio-{model}-{dim}"

    def embed(self, text: str) -> np.ndarray:
        import httpx

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            json={"model": self.model, "input": text},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=60,
        )
        resp.raise_for_status()
        vec = np.array(resp.json()["data"][0]["embedding"], dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0 else vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return 0.0
    return float(np.dot(a, b))  # both pre-normalized
