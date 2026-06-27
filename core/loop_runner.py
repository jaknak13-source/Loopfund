"""Background loop runner. Drives the orchestrator on an interval as an asyncio
task. Default: stopped — the human starts it from the dashboard. Survives cycle
errors (logged, loop continues). This is the 24/7 driver.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from core.logging import get_logger

log = get_logger("loop")


class LoopRunner:
    def __init__(self, orchestrator) -> None:
        self.orch = orchestrator
        self._task: asyncio.Task | None = None
        self.running = False
        # Gap BETWEEN loop iterations. Default from settings.loops.loop_interval_seconds
        # (1800s = 30 min) so a 24/7 run stays cheap. Full decision cycles run on
        # decision.interval_hours; iterations in between run one deep research task.
        from core.config import settings
        self.interval_s = int(settings().get("loops", {}).get("loop_interval_seconds", 1800))
        self.cycles_run = 0
        self.research_idx = 0
        self.last_cycle_at: str | None = None
        self.last_research: dict | None = None
        self.last_result: dict | None = None
        self.last_error: str | None = None

    def status(self) -> dict:
        return {
            "running": self.running,
            "mode": "continuous-research",
            "research_tasks_run": self.research_idx,
            "last_research": self.last_research,
            "interval_s": self.interval_s,
            "cycles_run": self.cycles_run,
            "last_cycle_at": self.last_cycle_at,
            "last_error": self.last_error,
        }

    async def _loop(self) -> None:
        self.running = True
        self.research_idx = getattr(self, "research_idx", 0)
        log.info("loop_started", interval_s=self.interval_s, mode="continuous")
        try:
            while self.running:
                try:
                    if self.orch.decision_due():
                        # full multi-agent decision cycle (may trade), on the cadence
                        self.last_result = await self.orch.run_cycle()
                        self.cycles_run += 1
                        self.last_cycle_at = datetime.now(timezone.utc).isoformat()
                    else:
                        # NEVER idle: continuous deep research between decision cycles,
                        # accumulating knowledge in memory for future decisions
                        self.last_research = await self.orch.research_task(self.research_idx)
                        self.research_idx += 1
                    self.last_error = None
                except Exception as exc:
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    log.error("loop_iteration_failed", error=self.last_error)
                    try:
                        from core.resilience import record_error
                        record_error("loop", exc)
                    except Exception:
                        pass
                # tiny gap only — keeps it near-continuous without a 100% tight spin
                await asyncio.sleep(self.interval_s)
        finally:
            self.running = False
            log.info("loop_stopped")

    def start(self, interval_s: int | None = None) -> dict:
        if self.running:
            return self.status()
        if interval_s:
            self.interval_s = max(2, int(interval_s))  # small gap allowed (continuous research)
        # Set running synchronously so the API response (and dashboard) reflects "running"
        # immediately, instead of racing the not-yet-scheduled loop task.
        self.running = True
        self._task = asyncio.create_task(self._loop())
        return self.status()

    async def stop(self) -> dict:
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        return self.status()
