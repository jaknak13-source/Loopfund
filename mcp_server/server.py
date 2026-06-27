#!/usr/bin/env python3
"""MCP server for the loopfund multi-agent system (`loopfund_mcp`).

Exposes the fund's multi-agent deliberation as Model Context Protocol tools so any
MCP client (Claude Desktop, the Inspector, or another agent) can inspect the
portfolio, read every agent's analysis and the council's bull/bear/synthesis
debate, ask why a decision did or didn't trade, search the fund's memory, and trigger
a fresh deliberation cycle.

Inference behind these tools uses whichever model backend is configured in
config/models.yaml (a local server, or any cloud provider via .env).

Transports:
  stdio (default)        — local clients (Claude Desktop / Inspector)
  streamable_http        — remote / cloud deployment (set MCP_TRANSPORT=http)

Run:
  .venv/bin/python -m mcp_server.server                 # stdio
  MCP_TRANSPORT=http MCP_PORT=8600 python -m mcp_server.server   # remote
"""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("loopfund_mcp")

# --- lazy orchestrator (built once, reused across tool calls) ---
_ORCH: Any = None


def _orch() -> Any:
    """Build the real orchestrator on first use and cache it.

    Read tools work fully offline (they hit the local blackboard DB). Only
    fund_run_cycle needs a reachable Qwen Cloud backend (DASHSCOPE_API_KEY).
    """
    global _ORCH
    if _ORCH is None:
        from core.app import build_orchestrator
        from core.config import reload

        reload()
        _ORCH = build_orchestrator()
    return _ORCH


def _dump(items: list[Any]) -> list[dict]:
    """Serialize a list of pydantic models to JSON-safe dicts."""
    return [it.model_dump(mode="json") for it in items]


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


# --- input models ---
class LimitInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    limit: int = Field(default=20, description="Maximum rows to return", ge=1, le=200)


class ActivityInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    agent: str = Field(default="", description="Filter to one agent name, e.g. 'RiskAgent' (empty = all)")
    kind: str = Field(default="", description="Event kind filter: thinking|status|decision|research|error (empty = all)")
    q: str = Field(default="", description="Substring search over event text (empty = no filter)")
    limit: int = Field(default=50, description="Maximum events to return", ge=1, le=200)


class MemoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    query: str = Field(..., description="Semantic search query over the fund's memory", min_length=1, max_length=500)
    k: int = Field(default=8, description="Number of memory hits to return", ge=1, le=50)
    kind: str | None = Field(default=None, description="Optional memory kind filter (e.g. 'lesson', 'thesis')")


_READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_ACTION = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}


@mcp.tool(name="fund_get_status", annotations={"title": "Fund status", **_READ})
async def fund_get_status() -> str:
    """Return the fund's current operating status: mode, the active Qwen model and
    backend, memory size, watchlist, loop state, and whether it can trade right now.

    Returns:
        str: JSON with keys: mode (str), model (str), backend (str),
        memory_size (int), watchlist (list[str]), loop (dict), can_trade_now (bool).
    """
    from core.config import settings

    orch = _orch()
    spec = orch.router.resolve("DecisionAgent")
    return _json({
        "mode": settings().get("mode", "dry"),
        "model": spec.get("model"),
        "backend": spec.get("backend"),
        "memory_size": orch.rag.size(),
        "watchlist": orch.watchlist,
        "can_trade_now": orch.can_trade_now(),
    })


@mcp.tool(name="fund_get_portfolio", annotations={"title": "Portfolio snapshot", **_READ})
async def fund_get_portfolio() -> str:
    """Return the current portfolio: total value, cash, and every open position.

    Returns:
        str: JSON with keys: snapshot (dict: total_value_eur, cash_eur, ...),
        positions (list of {asset, qty, avg_cost_eur, ccy}).
    """
    orch = _orch()
    snap = await orch.portfolio_snapshot()
    positions = [
        {"asset": a, "qty": p.qty, "avg_cost_eur": p.avg_cost_eur, "ccy": p.ccy}
        for a, p in orch.ledger.p.positions.items()
    ]
    return _json({"snapshot": snap, "positions": positions})


@mcp.tool(name="fund_get_decisions", annotations={"title": "Recent allocation decisions", **_READ})
async def fund_get_decisions(params: LimitInput) -> str:
    """Return the most recent portfolio decisions made by the DecisionAgent, each
    with action, asset, target weight, reasoning, assumptions, known risks, and any
    block_reason from the risk debate.

    Args:
        params (LimitInput): limit (int, 1-200) — how many decisions to return.

    Returns:
        str: JSON list of decision objects (newest first).
    """
    return _json(_dump(_orch().bb.latest_decisions(params.limit)))


@mcp.tool(name="fund_get_trades", annotations={"title": "Recent simulated trades", **_READ})
async def fund_get_trades(params: LimitInput) -> str:
    """Return the most recent simulated (dry-mode) trades the fund executed.

    Args:
        params (LimitInput): limit (int, 1-200).

    Returns:
        str: JSON list of trade objects (newest first).
    """
    return _json(_dump(_orch().bb.latest_trades(params.limit)))


@mcp.tool(name="fund_get_agent_reports", annotations={"title": "Per-agent analysis", **_READ})
async def fund_get_agent_reports(params: LimitInput) -> str:
    """Return the latest analysis reports from the specialist agents (Research, Macro,
    Fundamentals, Sentiment, Quant, SmartMoney, Risk, ...). This is the cross-agent
    visibility layer: each report carries the agent's stance, summary, findings, and
    calibrated confidence that peers build on during a cycle.

    Args:
        params (LimitInput): limit (int, 1-200) — how many reports across all agents.

    Returns:
        str: JSON list of report objects with keys: agent, topic, stance, summary,
        findings, confidence {score, low, high}, created_at.
    """
    return _json(_dump(_orch().bb.recent_reports(params.limit)))


@mcp.tool(name="fund_get_activity", annotations={"title": "Agent activity feed (the 'Mind')", **_READ})
async def fund_get_activity(params: ActivityInput) -> str:
    """Return the real-time activity feed — the fund's 'Mind' — showing agents
    thinking, disagreeing, researching, and deciding. Filter by agent, kind, or text.
    Use this to trace how the multi-agent council reached (or blocked) a decision.

    Args:
        params (ActivityInput): agent (str), kind (str), q (str), limit (int 1-200).

    Returns:
        str: JSON list of activity events with keys: ts, agent, kind, text, meta, cycle_id.
    """
    evs = _orch().bb.latest_activity(agent=params.agent, kind=params.kind, q=params.q, limit=params.limit)
    return _json(_dump(evs))


@mcp.tool(name="fund_why_no_trade", annotations={"title": "Why did/didn't the fund trade", **_READ})
async def fund_why_no_trade(params: LimitInput) -> str:
    """Explain trading outcomes by tallying the block reasons across recent decisions
    (e.g. 'below_floor', 'risk_veto', 'no_room', 'traded', 'model_no_action').

    Args:
        params (LimitInput): limit (int, 1-200) — decisions to scan.

    Returns:
        str: JSON {blockers: {reason: count}, n: int}.
    """
    orch = _orch()
    ds = orch.bb.latest_decisions(params.limit)
    tally: dict[str, int] = {}
    for d in ds:
        key = d.block_reason or ("traded" if d.action.value != "no_action" else "model_no_action")
        tally[key] = tally.get(key, 0) + 1
    return _json({"blockers": tally, "n": len(ds)})


@mcp.tool(name="fund_search_memory", annotations={"title": "Search fund memory", **_READ})
async def fund_search_memory(params: MemoryInput) -> str:
    """Semantically search the fund's long-term memory (past theses, lessons learned,
    verified facts) and return the most relevant entries.

    Args:
        params (MemoryInput): query (str), k (int 1-50), kind (optional str).

    Returns:
        str: JSON {size: int, results: list of memory hits}.
    """
    orch = _orch()
    hits = orch.rag.search(params.query, k=params.k, kind=params.kind)
    return _json({"size": orch.rag.size(), "results": _dump(hits)})


@mcp.tool(name="fund_get_calibration", annotations={"title": "Learned trust + benchmark", **_READ})
async def fund_get_calibration() -> str:
    """Return how well the fund is calibrated: learned per-agent and per-source trust
    weights and performance versus the S&P 500 benchmark.

    Returns:
        str: JSON with keys: benchmark (dict), horizon_days (int), plus learned
        agent/source metrics.
    """
    orch = _orch()
    snap = await orch.portfolio_snapshot()
    spy = await orch._price_eur(orch.benchmark_symbol)
    return _json({
        "benchmark": orch.learning.benchmark(spy, snap["total_value_eur"]),
        "horizon_days": orch.horizon_days,
        **orch.learning.metrics_snapshot(),
    })


@mcp.tool(name="fund_run_cycle", annotations={"title": "Run a deliberation cycle", **_ACTION})
async def fund_run_cycle() -> str:
    """Trigger ONE full multi-agent deliberation cycle: every specialist agent
    analyzes the watchlist, shares results on the blackboard, the council debates the
    top candidates (bull vs bear vs synthesis), the RiskAgent challenges, and the
    DecisionAgent makes a final risk-checked allocation. Executes simulated trades in
    dry mode. Requires a reachable Qwen Cloud backend (DASHSCOPE_API_KEY).

    Returns:
        str: JSON summary of the cycle (cycle_id, decisions, trades, timings).
    """
    try:
        result = await _orch().run_cycle()
    except Exception as exc:  # noqa: BLE001 — surface the real failure to the client
        return _json({
            "error": f"{type(exc).__name__}: {exc}",
            "hint": "If this is an auth/connection error, check DASHSCOPE_API_KEY and QWEN_BASE_URL in .env.",
        })
    return _json(result)


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport in ("http", "streamable_http", "streamable-http"):
        port = int(os.environ.get("MCP_PORT", "8600"))
        # Bind to localhost by default. The MCP tools can trigger model inference and
        # tool calls, so only expose to the network deliberately (set MCP_HOST=0.0.0.0)
        # and put authentication in front of it.
        mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
        mcp.settings.port = port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
