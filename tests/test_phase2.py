"""Phase 2: RAG memory recall + ResearchAgent end-to-end (offline, mock LLM)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from agents.memory_agent import MemoryAgent
from agents.research import ResearchAgent
from core.blackboard import Blackboard
from memory.rag import RagMemory
from models_adapter.mock import MockBackend
from models_adapter.router import ModelRouter
from schemas import MemoryEntry
from tools.registry import ToolRegistry


@pytest.fixture
def rag(tmp_path) -> RagMemory:
    bb = Blackboard(path=tmp_path / "t.db")
    return RagMemory(bb, vector_path=tmp_path / "vec" / "idx.npz")


def _entry(eid: str, title: str, body: str, kind: str = "news") -> MemoryEntry:
    return MemoryEntry(id=eid, created_at=datetime.now(timezone.utc), kind=kind, title=title, body=body)


def test_vector_recall_ranks_relevant(rag: RagMemory) -> None:
    rag.add(_entry("a", "NVIDIA earnings beat", "Nvidia reported strong data center revenue growth"))
    rag.add(_entry("b", "Oil prices", "Crude oil fell on demand concerns in Europe"))
    rag.add(_entry("c", "Fed rate decision", "Federal Reserve held interest rates steady"))
    hits = rag.search("nvidia chip revenue", k=2)
    assert hits, "expected recall hits"
    assert hits[0].id == "a"


def test_memory_agent_ingest_and_recall(rag: RagMemory) -> None:
    ma = MemoryAgent(rag)
    ma.write_lesson("Avoid single-source rumors", "A rumor moved us once and was false.", outcome="incorrect")
    ctx = ma.lessons_context("rumor single source", k=3)
    assert "rumor" in ctx.lower()
    assert rag.size() >= 1


_CANNED = """```json
{"summary": "Markets mixed; AI names firm, energy soft.",
 "stance": "neutral",
 "assets": ["NVDA", "XOM"],
 "findings": ["AI capex narrative intact", "Energy demand concerns"],
 "confidence": {"score": 0.45, "low": 0.3, "high": 0.6, "rationale": "mixed signals"},
 "unverified_claims": ["Rumor of a big chip order (unconfirmed)"]}
```"""


@pytest.mark.asyncio
async def test_research_agent_end_to_end(tmp_path) -> None:
    bb = Blackboard(path=tmp_path / "t.db")
    rag = RagMemory(bb, vector_path=tmp_path / "vec" / "idx.npz")
    memory = MemoryAgent(rag)
    router = ModelRouter(backends={"qwen": MockBackend(_CANNED)}, max_concurrent=1)

    # hermetic tool registry: fake news adapters, no network
    reg = ToolRegistry(bb)
    async def _rss(**_):
        return {"articles": [{"title": "Nvidia jumps on AI demand", "link": "http://x/1"},
                             {"title": "Oil slips on demand worries", "link": "http://x/2"}], "stale": False}
    async def _gdelt(**_):
        return {"articles": [{"title": "Central bank signals caution"}], "stale": False}
    reg.register("rss_headlines", _rss)
    reg.register("gdelt_search", _gdelt)

    agent = ResearchAgent(bb, router, reg, memory)
    report = await agent.run("cycle-1")

    assert report.stance == "neutral"
    assert "NVDA" in report.assets
    assert report.confidence.score == 0.45
    assert report.unverified_claims  # flagged lead present
    assert report.citations and report.citations[0].verified is False
    # ingested into memory and recallable
    assert rag.search("nvidia ai demand", k=1)
