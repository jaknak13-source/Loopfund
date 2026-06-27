"""The MCP server registers the expected tools and read tools return JSON without
needing a live Qwen backend."""

from __future__ import annotations

import asyncio
import json

import pytest


def test_mcp_registers_expected_tools():
    from mcp_server.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    expected = {
        "fund_get_status", "fund_get_portfolio", "fund_get_decisions", "fund_get_trades",
        "fund_get_agent_reports", "fund_get_activity", "fund_why_no_trade",
        "fund_search_memory", "fund_get_calibration", "fund_run_cycle",
    }
    assert expected <= names


def test_read_tools_offline(tmp_path, monkeypatch):
    """Read tools must work against an offline orchestrator (no Qwen key)."""
    from mcp_server import server as s
    from tests.helpers import build_offline_orchestrator

    s._ORCH = build_offline_orchestrator(tmp_path)  # inject offline fund

    out = json.loads(asyncio.run(s.fund_why_no_trade(s.LimitInput(limit=10))))
    assert "blockers" in out and "n" in out

    pf = json.loads(asyncio.run(s.fund_get_portfolio()))
    assert "snapshot" in pf and "positions" in pf

    s._ORCH = None  # reset shared state for other tests


@pytest.mark.parametrize("limit", [0, 9999])
def test_limit_input_validation_rejects_out_of_range(limit):
    from pydantic import ValidationError

    from mcp_server.server import LimitInput

    with pytest.raises(ValidationError):
        LimitInput(limit=limit)
