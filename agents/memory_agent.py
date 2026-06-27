"""MemoryAgent: owns the persistent RAG. Ingests every agent report, records
lessons and outcomes, and produces periodic summaries. Not an analysis agent —
a service the others read from and write to.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from core.logging import get_logger
from memory.rag import RagMemory
from schemas import AgentReport, MemoryEntry, PortfolioDecision


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class MemoryAgent:
    name = "MemoryAgent"

    def __init__(self, rag: RagMemory) -> None:
        self.rag = rag
        self.log = get_logger(self.name)

    def ingest_report(self, report: AgentReport) -> MemoryEntry:
        entry = MemoryEntry(
            id=_id(),
            created_at=_now(),
            kind="report",
            title=f"[{report.agent}] {report.topic}",
            body=report.summary + "\n" + "\n".join(report.findings),
            assets=report.assets,
            tags=[report.agent, report.stance],
            confidence=report.confidence.score,
            refs=[report.id],
        )
        self.rag.add(entry)
        return entry

    def ingest_decision(self, decision: PortfolioDecision) -> MemoryEntry:
        entry = MemoryEntry(
            id=_id(),
            created_at=_now(),
            kind="decision",
            title=f"Decision {decision.decision_date}: {decision.action.value} {decision.asset or ''}".strip(),
            body=decision.reasoning,
            assets=[decision.asset] if decision.asset else [],
            tags=[decision.action.value],
            confidence=decision.confidence.score,
            refs=[decision.id],
        )
        self.rag.add(entry)
        return entry

    def write_lesson(self, title: str, body: str, assets: list[str] | None = None,
                     outcome: str = "unknown", refs: list[str] | None = None) -> MemoryEntry:
        entry = MemoryEntry(
            id=_id(),
            created_at=_now(),
            kind="lesson",
            title=title,
            body=body,
            assets=assets or [],
            tags=["lesson"],
            outcome=outcome,  # type: ignore[arg-type]
            refs=refs or [],
        )
        self.rag.add(entry)
        self.log.info("lesson_written", title=title, outcome=outcome)
        return entry

    def recall(self, query: str, k: int = 5, kind: str | None = None) -> list[MemoryEntry]:
        return self.rag.search(query, k=k, kind=kind)

    def lessons_context(self, query: str, k: int = 5) -> str:
        """Compact lessons text to inject into an agent prompt before it works."""
        hits = self.rag.search(query, k=k, kind="lesson")
        if not hits:
            return "No prior lessons on record."
        return "\n".join(f"- {h.title}: {h.body[:200]} (outcome={h.outcome})" for h in hits)
