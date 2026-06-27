"""Live execution adapter — INTENTIONALLY NOT IMPLEMENTED.

Live trading is gated behind an explicit, deliberate decision. No live broker is
wired yet (broker choice deferred — see task_plan.md). This stub exists so that
flipping mode=live without a real, reviewed adapter fails LOUDLY instead of
silently doing nothing or, worse, doing something unintended.

To go live later: implement `execute()` against a chosen broker API (e.g. IBKR),
require an explicit env flag, and add a human confirmation step.
"""

from __future__ import annotations

from execution.base import ExecutionAdapter
from schemas import PortfolioDecision, SimulatedTrade


class LiveExecutionNotConfigured(RuntimeError):
    pass


class LiveExecution(ExecutionAdapter):
    mode = "live"

    async def execute(self, decision: PortfolioDecision) -> SimulatedTrade | None:
        raise LiveExecutionNotConfigured(
            "Live trading is not configured. The system is dry-mode only. "
            "Implement a reviewed broker adapter and an explicit confirmation gate "
            "before enabling live execution."
        )
