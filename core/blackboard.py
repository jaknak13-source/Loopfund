"""The shared blackboard. Agents never call each other directly — they read and
write here. Typed wrapper over SqliteStore that handles pydantic (de)serialization.
"""

from __future__ import annotations

from pathlib import Path

from core.store import SqliteStore
from schemas import (
    ActivityEvent,
    AgentReport,
    HumanInstruction,
    MemoryEntry,
    PortfolioDecision,
    SimulatedTrade,
    ToolCall,
)


class Blackboard:
    def __init__(self, path: Path | None = None) -> None:
        self.store = SqliteStore(path)

    # --- reports ---
    def write_report(self, report: AgentReport) -> None:
        self.store._put(
            "reports",
            {
                "id": report.id,
                "cycle_id": report.cycle_id,
                "agent": report.agent,
                "created_at": report.created_at.isoformat(),
            },
            report.model_dump_json(),
        )

    def get_report(self, report_id: str) -> AgentReport | None:
        raw = self.store._get("reports", report_id)
        return AgentReport.model_validate(raw) if raw else None

    def reports_for_cycle(self, cycle_id: str) -> list[AgentReport]:
        rows = self.store._query("reports", "cycle_id=?", (cycle_id,))
        return [AgentReport.model_validate(r) for r in rows]

    def recent_reports(self, limit: int = 50) -> list[AgentReport]:
        rows = self.store._query("reports", limit=limit)
        return [AgentReport.model_validate(r) for r in rows]

    # --- decisions ---
    def write_decision(self, decision: PortfolioDecision) -> None:
        self.store._put(
            "decisions",
            {
                "id": decision.id,
                "decision_date": decision.decision_date.isoformat(),
                # store the precise datetime so the log shows the real time and
                # same-day decisions sort correctly (was date-only before)
                "created_at": decision.created_at.isoformat(),
            },
            decision.model_dump_json(),
        )

    def get_decision(self, decision_id: str) -> PortfolioDecision | None:
        raw = self.store._get("decisions", decision_id)
        return PortfolioDecision.model_validate(raw) if raw else None

    def latest_decisions(self, limit: int = 30) -> list[PortfolioDecision]:
        rows = self.store._query("decisions", limit=limit)
        return [PortfolioDecision.model_validate(r) for r in rows]

    # --- trades ---
    def write_trade(self, trade: SimulatedTrade) -> None:
        self.store._put(
            "trades",
            {
                "id": trade.id,
                "decision_id": trade.decision_id,
                "asset": trade.asset,
                "status": trade.status,
                "created_at": trade.placed_at.isoformat(),
            },
            trade.model_dump_json(),
        )

    def trades_for_asset(self, asset: str) -> list[SimulatedTrade]:
        rows = self.store._query("trades", "asset=?", (asset,))
        return [SimulatedTrade.model_validate(r) for r in rows]

    def latest_trades(self, limit: int = 50) -> list[SimulatedTrade]:
        rows = self.store._query("trades", limit=limit)
        return [SimulatedTrade.model_validate(r) for r in rows]

    # --- tool calls ---
    def log_tool_call(self, call: ToolCall) -> None:
        self.store._put(
            "tool_calls",
            {
                "id": call.id,
                "agent": call.agent,
                "tool": call.tool,
                "created_at": call.started_at.isoformat(),
            },
            call.model_dump_json(),
        )

    # --- memory ---
    def write_memory(self, entry: MemoryEntry) -> None:
        self.store._put(
            "memory",
            {
                "id": entry.id,
                "kind": entry.kind,
                "created_at": entry.created_at.isoformat(),
            },
            entry.model_dump_json(),
        )

    def memory_by_kind(self, kind: str, limit: int = 100) -> list[MemoryEntry]:
        rows = self.store._query("memory", "kind=?", (kind,), limit=limit)
        return [MemoryEntry.model_validate(r) for r in rows]

    # --- activity feed (Mind tab) ---
    def write_activity(self, event: ActivityEvent) -> None:
        search = f"{event.agent} {event.kind} {event.title} {event.summary}".lower()
        self.store._put(
            "activity",
            {
                "id": event.id,
                "agent": event.agent,
                "kind": event.kind,
                "cycle_id": event.cycle_id,
                "created_at": event.ts.isoformat(),
                "search": search,
            },
            event.model_dump_json(),
        )

    def latest_activity(self, agent: str = "", kind: str = "", cycle_id: str = "",
                        q: str = "", limit: int = 100) -> list[ActivityEvent]:
        rows = self.store.query_activity(agent=agent, kind=kind, cycle_id=cycle_id, q=q, limit=limit)
        return [ActivityEvent.model_validate(r) for r in rows]

    # --- instructions ---
    def write_instruction(self, instr: HumanInstruction) -> None:
        self.store._put(
            "instructions",
            {
                "id": instr.id,
                "active": 1 if instr.active else 0,
                "created_at": instr.received_at.isoformat(),
            },
            instr.model_dump_json(),
        )

    def active_instructions(self, limit: int = 50) -> list[HumanInstruction]:
        rows = self.store._query("instructions", "active=1", (), limit=limit)
        return [HumanInstruction.model_validate(r) for r in rows]
