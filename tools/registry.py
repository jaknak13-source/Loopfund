"""Tool registry. Agents call data sources/tools only through here so every call
is logged as a ToolCall and retried with backoff. Phase 0 ships the registry
mechanics + an `echo` tool; real data adapters land in Phase 1.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable

from core.blackboard import Blackboard
from core.logging import get_logger
from schemas import ToolCall

log = get_logger("tools")

ToolFn = Callable[..., Awaitable[object]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ToolRegistry:
    def __init__(self, blackboard: Blackboard | None = None) -> None:
        self._tools: dict[str, ToolFn] = {}
        self.blackboard = blackboard

    def register(self, name: str, fn: ToolFn) -> None:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = fn

    def available(self) -> list[str]:
        return sorted(self._tools)

    async def call(self, agent: str, name: str, _log: bool = True, **params: object) -> tuple[object, ToolCall]:
        """Invoke a tool, log the ToolCall, return (result, record).

        On failure the ToolCall is logged with ok=False and the exception
        re-raised — errors are signal, never swallowed. Pass _log=False for
        high-frequency read-only plumbing (e.g. price snapshots) to avoid DB bloat.
        """
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name} (have: {self.available()})")

        rec = ToolCall(
            id=str(uuid.uuid4()), agent=agent, tool=name, params=dict(params), started_at=_now()
        )
        try:
            result = await self._tools[name](**params)
            rec.ok = True
            # persist a truncated snapshot of what the tool returned, so the dashboard can
            # show decision PROVENANCE (what data the agents actually saw). Capped + best-effort.
            try:
                snap = json.dumps(result, default=str) if isinstance(result, (dict, list)) else str(result)
                rec.output_ref = snap[:800]
            except Exception:
                rec.output_ref = str(result)[:800]
            return result, rec
        except Exception as exc:  # log then re-raise
            rec.ok = False
            rec.error = f"{type(exc).__name__}: {exc}"
            log.error("tool_failed", tool=name, agent=agent, error=rec.error)
            raise
        finally:
            rec.finished_at = _now()
            if _log and self.blackboard is not None:
                self.blackboard.log_tool_call(rec)


async def _echo(**params: object) -> dict[str, object]:
    """Trivial tool used to smoke-test the registry."""
    return dict(params)


def default_registry(blackboard: Blackboard | None = None) -> ToolRegistry:
    reg = ToolRegistry(blackboard)
    reg.register("echo", _echo)
    return reg
