"""MemoryAuditorAgent: once per day, scans recent memory and re-verifies it against
the current date and (optionally) the web, flagging anything stale, outdated, or
hallucinated so it cannot quietly corrupt future decisions.
"""

from __future__ import annotations

from agents.base import BaseAgent
from agents.memory_agent import MemoryAgent
from agents.util import parse_json_block
from core.blackboard import Blackboard
from models_adapter.router import ModelRouter
from tools.registry import ToolRegistry

_SYSTEM = (
    "You are the MemoryAuditorAgent. You audit the fund's stored memory for entries "
    "that are now STALE, OUTDATED, INTERNALLY INCONSISTENT, or likely HALLUCINATED, "
    "given the authoritative current date. Time-sensitive facts (prices, events, "
    "guidance) older than a few days are suspect unless re-verified. Be strict: when "
    "in doubt, flag it. Return ONLY JSON: "
    '{"flagged":[{"title":str,"reason":str}],"summary":str}'
)


class MemoryAuditorAgent(BaseAgent):
    name = "MemoryAuditorAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 memory: MemoryAgent) -> None:
        super().__init__(bb, router, tools)
        self.memory = memory

    async def run(self, cycle_id: str):
        from schemas import Confidence
        return self.make_report(cycle_id, topic="memory audit",
                                summary="MemoryAuditorAgent runs daily.",
                                confidence=Confidence(score=0.3, low=0.2, high=0.4), stance="uncertain")

    async def audit(self, sample: int = 15, stale_after_hours: int = 24) -> dict:
        from datetime import datetime, timedelta, timezone

        # Only review entries that have actually AGED — recent analyses are not "stale"
        # and must not be flagged. Audit time-sensitive kinds (news/model_output), oldest
        # first; never touch fresh (< stale_after_hours) or durable (lesson/decision) memory.
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_after_hours)
        entries = []
        for kind in ("news", "model_output"):
            entries += [e for e in self.bb.memory_by_kind(kind, limit=80)
                        if e.created_at <= cutoff]
        entries = sorted(entries, key=lambda e: e.created_at)[:sample]  # oldest first
        if not entries:
            return {"ok": True, "flagged": 0, "note": "nothing aged enough to audit"}

        listing = "\n".join(
            f"- [{e.kind}] {e.title} (stored {e.created_at.isoformat(timespec='minutes')}): {e.body[:160]}"
            for e in entries
        )
        user = (
            "These memory entries are now OLD (stored over a day ago). Against the current "
            "authoritative date, flag ONLY ones whose time-sensitive content (prices, events, "
            "guidance) is now outdated/superseded or was likely hallucinated. Do NOT flag an "
            "entry merely for being an opinion or for existing. If unsure, do not flag.\n\n"
            f"{listing}"
        )
        text = await self.think(_SYSTEM, user)
        parsed = parse_json_block(text) or {}
        flagged = parsed.get("flagged", []) if isinstance(parsed, dict) else []

        for f in flagged[:sample]:
            title = str(f.get("title", ""))[:120]
            reason = str(f.get("reason", ""))[:300]
            if title:
                self.memory.write_lesson(
                    title=f"Stale memory (re-verify before use): {title}",
                    body=f"Daily audit: this aged entry may be outdated — re-verify. {reason}",
                    outcome="unknown")  # stale != a wrong call; don't pollute as 'incorrect'
        summary = str(parsed.get("summary", ""))[:400] if isinstance(parsed, dict) else ""
        self.log.info("memory_audit", reviewed=len(entries), flagged=len(flagged))
        return {"ok": True, "reviewed": len(entries), "flagged": len(flagged), "summary": summary}
