# `loopfund_mcp`: MCP server

Exposes the loopfund multi-agent system as Model Context Protocol tools. Any MCP
client (Claude Desktop, the MCP Inspector, or another agent) can inspect the
portfolio, read every agent's analysis and the council debate, ask why a decision
did/didn't trade, search the system's memory, and trigger a fresh deliberation
cycle.

All inference behind these tools runs on whichever model backend is configured
(see the model backend settings and `.env.example`).

## Tools

| Tool | What it does | Reads only |
|---|---|---|
| `fund_get_status` | Mode, active model/backend, memory size, watchlist, can-trade | yes |
| `fund_get_portfolio` | Total value, cash, open positions | yes |
| `fund_get_decisions` | Recent allocation decisions + reasoning + block reason | yes |
| `fund_get_trades` | Recent simulated trades | yes |
| `fund_get_agent_reports` | Each specialist agent's stance / findings / confidence | yes |
| `fund_get_activity` | The "Mind" feed: thinking, disagreement, decisions | yes |
| `fund_why_no_trade` | Tally of why decisions did/didn't trade | yes |
| `fund_search_memory` | Semantic search over the fund's long-term memory | yes |
| `fund_get_calibration` | Learned agent/source trust + S&P 500 benchmark | yes |
| `fund_run_cycle` | Run ONE full multi-agent deliberation cycle (needs a model backend) | no (action) |

## Run locally (stdio)

```bash
.venv/bin/python -m mcp_server.server
```

### Connect from an MCP client

Add to the client's MCP config (`claude_desktop_config.json` or equivalent).
Replace `/path/to/loopfund` with the absolute path to your checkout:

```json
{
  "mcpServers": {
    "loopfund_mcp": {
      "command": "/path/to/loopfund/.venv/bin/python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/loopfund"
    }
  }
}
```

### Inspect with the MCP Inspector

```bash
npx @modelcontextprotocol/inspector .venv/bin/python -m mcp_server.server
```

## Run over HTTP (streamable, for remote MCP clients)

```bash
MCP_TRANSPORT=http MCP_PORT=8600 .venv/bin/python -m mcp_server.server
# serves the MCP endpoint on http://<host>:8600/mcp
```
