"""BaseAgent: shared plumbing for every specialized agent.

Provides access to the router (LLM), blackboard (shared memory), tool registry,
and the house rules. Subclasses implement `run(cycle_id)` to do their analysis
and return an AgentReport.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from core.blackboard import Blackboard
from core.config import ROOT
from core.logging import get_logger
from models_adapter.base import Message
from models_adapter.router import ModelRouter
from schemas import AgentReport, Confidence
from tools.registry import ToolRegistry


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class BaseAgent(ABC):
    name: str = "BaseAgent"

    def __init__(
        self,
        blackboard: Blackboard,
        router: ModelRouter,
        tools: ToolRegistry,
    ) -> None:
        self.bb = blackboard
        self.router = router
        self.tools = tools
        self.log = get_logger(self.name)

    def house_rules(self) -> str:
        # STRATEGY.md lives in docs/; fall back to the old root location for
        # backward compatibility with existing checkouts.
        path = ROOT / "docs" / "STRATEGY.md"
        if not path.exists():
            path = ROOT / "STRATEGY.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def sys(self, text: str) -> str:
        """Prepend the operating-truth + authoritative-time preamble to a system
        prompt. Use this for ALL completions so every agent knows the real time,
        its training cutoff, and that it must verify everything."""
        from core.preamble import system_preamble

        return f"{system_preamble()}\n\n{text}"

    async def think(self, system: str, user: str, profile: str = "default") -> str:
        return await self.router.complete(
            self.name,
            [Message("system", self.sys(system)), Message("user", user)],
            profile=profile,
        )

    def make_report(
        self,
        cycle_id: str,
        topic: str,
        summary: str,
        confidence: Confidence,
        **kwargs: object,
    ) -> AgentReport:
        return AgentReport(
            id=new_id(),
            agent=self.name,
            cycle_id=cycle_id,
            created_at=now(),
            topic=topic,
            summary=summary,
            confidence=confidence,
            model_used=self.router.resolve(self.name).get("model", ""),
            **kwargs,  # type: ignore[arg-type]
        )

    @abstractmethod
    async def run(self, cycle_id: str) -> AgentReport:
        raise NotImplementedError
