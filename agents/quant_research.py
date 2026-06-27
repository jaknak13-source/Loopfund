"""QuantResearchAgent: the self-taught researcher. During idle time it forms a
hypothesis, WRITES its own Python script to test it, RUNS it in the sandbox, reads
the result, and — if the method is sound — saves it to a growing method library
and records what it learned. This is how the system invents and validates its own
quant/IB/PE methods over time rather than only using hand-coded models.

It can also pull references from the web. Everything is gated by the
settings.agents flags and bounded by a timeout.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

from agents.base import BaseAgent
from agents.memory_agent import MemoryAgent
from agents.util import parse_json_block
from core.blackboard import Blackboard
from core.config import ROOT, settings
from core.logging import get_logger
from models_adapter.base import Message
from models_adapter.router import ModelRouter
from tools.code_runner import SANDBOX, code_execution_allowed
from tools.registry import ToolRegistry

LIBRARY = ROOT / "quant" / "scripts" / "library"

_SYSTEM = (
    "You are the QuantResearchAgent. You invent and test quantitative methods by "
    "writing real Python. Be rigorous and skeptical: avoid lookahead bias, account "
    "for costs, and report honest metrics. Prefer simple, robust signals."
)


class QuantResearchAgent(BaseAgent):
    name = "QuantResearchAgent"

    def __init__(self, bb: Blackboard, router: ModelRouter, tools: ToolRegistry,
                 memory: MemoryAgent, watchlist: list[str] | None = None) -> None:
        super().__init__(bb, router, tools)
        self.memory = memory
        self.watchlist = watchlist or ["SPY", "QQQ", "NVDA", "AAPL", "MSFT"]

    async def run(self, cycle_id: str):
        """Not part of the per-cycle agent loop — this agent works during idle
        deep-research via research(). Provided to satisfy the BaseAgent interface."""
        from schemas import Confidence

        return self.make_report(
            cycle_id=cycle_id, topic="quant research",
            summary="QuantResearchAgent runs during idle deep-research (writes/runs its own methods).",
            confidence=Confidence(score=0.3, low=0.2, high=0.4, rationale="idle-only agent"),
            stance="uncertain")

    async def _dump_prices_csv(self) -> str | None:
        cols: dict[str, list[float]] = {}
        for tkr in self.watchlist:
            try:
                res, _ = await self.tools.call(self.name, "history", ticker=tkr, period="2y")
            except Exception:
                continue
            closes = [b["close"] for b in res.get("bars", [])]
            if len(closes) >= 100:
                cols[tkr] = closes
        if not cols:
            return None
        n = min(len(v) for v in cols.values())
        SANDBOX.mkdir(parents=True, exist_ok=True)
        path = SANDBOX / "research_prices.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            tickers = list(cols)
            w.writerow(tickers)
            for i in range(n):
                w.writerow([cols[t][-n + i] for t in tickers])
        return str(path)

    async def research(self, hypothesis: str | None = None) -> dict:
        if not code_execution_allowed():
            return {"ok": False, "reason": "code execution disabled"}

        csv_path = await self._dump_prices_csv()
        if not csv_path:
            return {"ok": False, "reason": "no price data"}

        lessons = self.memory.lessons_context("quant method research backtest")
        hyp = hypothesis or "Find a simple, robust cross-sectional or time-series signal with positive risk-adjusted return after costs."
        base_user = (
            f"Prior lessons:\n{lessons}\n\n"
            f"Hypothesis to test: {hyp}\n\n"
            f"Price data CSV at: {csv_path}\n"
            f"The CSV is WIDE: the first row is a header of ticker symbols {self.watchlist}; "
            f"every following row is one day's closing prices (chronological). "
            f"Load it with `pandas.read_csv(path)` — columns ARE the tickers, there is no date column.\n\n"
            "Write a COMPLETE standalone Python script (numpy/pandas + stdlib only, no network) "
            "that loads that CSV, builds a signal, runs a simple walk-forward backtest with a "
            "5 bps cost, and avoids lookahead. Print EXACTLY ONE final line:\n"
            'RESULT: {"method": "<short name>", "sharpe": <float>, "total_return": <float>, '
            '"max_drawdown": <float>, "notes": "<one line>"}\n'
            "Output ONLY the Python code, no prose, no code fences."
        )

        timeout = int(settings().get("agents", {}).get("research_timeout_s", 90))
        attempts = int(settings().get("agents", {}).get("research_max_attempts", 3))
        messages = [Message("system", self.sys(_SYSTEM)), Message("user", base_user)]
        last_run: dict = {}

        for attempt in range(1, attempts + 1):
            code = _strip_fences(await self.router.complete(self.name, messages))
            run, _rec = await self.tools.call(self.name, "run_python", code=code,
                                              script_name="research_method", timeout_s=timeout)
            last_run = run
            result = self._parse_result(run.get("stdout", ""))
            if run.get("ok") and result and "sharpe" in result:
                saved = self._save_method(code, result)
                self.memory.write_lesson(
                    title=f"Self-researched method: {result.get('method', 'unnamed')}",
                    body=(f"sharpe={result.get('sharpe')}, total_return={result.get('total_return')}, "
                          f"maxdd={result.get('max_drawdown')}. {result.get('notes', '')} "
                          f"Saved: {saved} (attempt {attempt})"),
                    outcome="correct" if (result.get("sharpe") or 0) > 0.5 else "partial")
                get_logger("quant_research").info("method_learned", method=result.get("method"),
                                                  sharpe=result.get("sharpe"), attempt=attempt)
                return {"ok": True, "result": result, "saved": saved, "attempts": attempt}

            # self-correct: feed the failure back and ask for a fix
            err = (run.get("stderr") or run.get("error") or "no RESULT line printed")[:1200]
            messages.append(Message("assistant", code[:4000]))
            messages.append(Message("user",
                f"That script failed (attempt {attempt}/{attempts}). Error/output:\n{err}\n\n"
                "Fix the bug and return the FULL corrected script only (no prose, no fences). "
                "Make sure it prints the RESULT: <json> line."))

        return {"ok": False, "reason": f"script failed after {attempts} attempts",
                "stderr": (last_run.get("stderr") or "")[:500], "stdout_tail": (last_run.get("stdout") or "")[-300:]}

    @staticmethod
    def _parse_result(stdout: str) -> dict | None:
        # preferred: an explicit RESULT: <json> line
        for line in reversed(stdout.splitlines()):
            if line.strip().startswith("RESULT:"):
                obj = parse_json_block(line.split("RESULT:", 1)[1])
                if obj:
                    return obj
        # lenient fallback: any JSON object in the output that reports a sharpe
        for line in reversed(stdout.splitlines()):
            if "sharpe" in line.lower() and "{" in line:
                obj = parse_json_block(line)
                if obj and "sharpe" in obj:
                    return obj
        blob = parse_json_block(stdout)
        return blob if (blob and "sharpe" in blob) else None

    def _save_method(self, code: str, result: dict) -> str:
        LIBRARY.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        name = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(result.get("method", "method")))[:40]
        path = LIBRARY / f"{ts}_{name}.py"
        header = f"# Self-researched method. metrics={json.dumps(result)}\n"
        path.write_text(header + code, encoding="utf-8")
        return str(path)


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.endswith("```"):
            t = t[: t.rfind("```")]
    return t.strip()
