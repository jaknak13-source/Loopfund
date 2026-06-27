"""Closing the learning loop: research compounds (distinct kind, protected, recalled),
the embedder recalls subword/morphological variants, and credibility needs a real URL."""

from __future__ import annotations

from datetime import datetime, timezone


def _entry(kind, title, i):
    from schemas import MemoryEntry
    return MemoryEntry(id=f"{kind}-{i}", created_at=datetime.now(timezone.utc), kind=kind,
                       title=title, body="b", tags=[kind])


def test_research_kind_protected_from_prune(tmp_path):
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    rag = RagMemory(Blackboard(path=tmp_path / "m.db"), vector_path=tmp_path / "v.npz")
    for i in range(8):
        rag.add(_entry("report", f"routine report {i}", i))
    for i in range(4):
        rag.add(_entry("research", f"deep dive {i}", i))
    removed = rag.prune(max_entries=6)
    kinds = [e["kind"] for e in rag.bb.store.memory_index()]
    assert removed > 0
    assert kinds.count("research") == 4   # all research survived
    assert "research" in RagMemory.PROTECTED_KINDS


def test_research_is_recallable(tmp_path):
    from core.blackboard import Blackboard
    from memory.rag import RagMemory
    rag = RagMemory(Blackboard(path=tmp_path / "m.db"), vector_path=tmp_path / "v.npz")
    rag.add(_entry("research", "NVDA datacenter GPU demand deep dive", 1))
    hits = rag.search("NVDA datacenter GPU", k=3, kind="research")
    assert hits and hits[0].kind == "research"


def test_embedder_recalls_subword_variants():
    """The improved hashing embedder shares char-n-grams, so a morphological variant
    ('valuation' vs 'undervalued') is no longer cosine 0.0 like an unrelated string."""
    from memory.embeddings import HashingEmbedder, cosine
    e = HashingEmbedder()
    q = e.embed("quarterly valuation review")
    related = cosine(q, e.embed("the stock looks undervalued"))
    unrelated = cosine(q, e.embed("gold dollar weather forecast"))
    assert related > 0.0
    assert related > unrelated


def test_is_credible_requires_real_url():
    from core.sources import is_credible
    assert is_credible("https://www.reuters.com/markets/x") is True
    assert is_credible("reuters.com") is False          # bare self-reported string blocked
    assert is_credible("Reuters (per the article)") is False
    assert is_credible("ftp://reuters.com/x") is False  # non-http scheme blocked


def test_reputable_research_domains_are_credible():
    """Bank/asset-manager/research outlooks (Morgan Stanley etc.) must count as credible."""
    from core.sources import is_credible
    for d in ("morganstanley.com", "goldmansachs.com", "jpmorgan.com", "blackrock.com",
              "fidelity.com", "axios.com"):
        assert is_credible(f"https://www.{d}/research/outlook") is True, d
    assert is_credible("https://www.totally-made-up-blog.xyz/x") is False
