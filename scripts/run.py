"""CLI entrypoint.

Normally you do not call this directly. Use the launcher at the repo root, which
installs dependencies on first run and then forwards the command here:

  ./start.sh                 # launch the local dashboard (FastAPI + loop control)
  ./start.sh cycle           # run ONE full research/decision cycle now (needs a model)
  ./start.sh status          # print current portfolio snapshot
  ./start.sh backtest NVDA   # quick momentum backtest of one ticker
  ./start.sh backup          # snapshot runtime state now
  ./start.sh backups         # list backups
  ./start.sh restore <name>  # restore a backup (snapshots current first)
  ./start.sh reset           # wipe runtime state (after a safety backup)

On Windows use start.bat instead. To call this file directly, run it from the
repo root with the root on PYTHONPATH, e.g.
`PYTHONPATH=. .venv/bin/python scripts/run.py serve`.

Dry mode only unless you deliberately enable live (see core/app.py gate).
"""

from __future__ import annotations

import asyncio
import json
import sys

from core.logging import get_logger

log = get_logger("run")


def _serve() -> None:
    import os

    import uvicorn

    from core.config import settings
    from dashboard.api.server import build_default_app

    cfg = settings().get("dashboard", {})
    # Env overrides win so a user can change the port without editing config.
    host = os.environ.get("LOOPFUND_HOST") or cfg.get("host", "127.0.0.1")
    port = int(os.environ.get("LOOPFUND_PORT") or cfg.get("port", 8500))
    # The browser needs a routable host; 0.0.0.0 isn't one.
    open_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    url = f"http://{open_host}:{port}"

    app = build_default_app()
    if os.environ.get("LOOPFUND_NO_BROWSER") != "1":
        _open_browser_when_ready(url)

    bar = "=" * 56
    print(f"\n{bar}\n  loopfund dashboard:  {url}\n  (opens in your browser automatically once ready)\n  Press Ctrl+C to stop.\n{bar}\n")
    uvicorn.run(app, host=host, port=port, log_level="info")


def _open_browser_when_ready(url: str) -> None:
    """Poll /api/health in a background thread; open the browser when it's up.

    Runs in a daemon thread so it never blocks shutdown. Best-effort: a headless
    box without a browser just gets the printed URL.
    """
    import threading
    import time
    import urllib.request
    import webbrowser

    def _wait() -> None:
        for _ in range(120):  # up to ~60s
            try:
                with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
                    if r.status == 200:
                        break
            except Exception:
                pass
            time.sleep(0.5)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_wait, daemon=True).start()


async def _cycle() -> None:
    from core.app import build_orchestrator

    orch = build_orchestrator()
    result = await orch.run_cycle()
    d = result["decision"]
    print(json.dumps({
        "action": d["action"], "asset": d.get("asset"),
        "confidence": d["confidence"]["score"], "reasoning": d["reasoning"][:300],
        "executed_trade_id": result["executed_trade_id"],
        "portfolio": result["portfolio"],
    }, indent=2))


async def _status() -> None:
    from core.app import build_orchestrator

    orch = build_orchestrator()
    print(json.dumps(await orch.portfolio_snapshot(), indent=2))


async def _backtest(ticker: str) -> None:
    from quant import backtest, factors
    from tools import market

    hist = await market.get_history(ticker, period="2y")
    closes = [b["close"] for b in hist.get("bars", [])]
    if len(closes) < 150:
        print(f"insufficient history for {ticker} ({len(closes)} bars)")
        return
    # simple long-when-positive-momentum signal
    sig = []
    for i in range(len(closes)):
        window = closes[: i + 1]  # walk-forward, no lookahead
        m = factors.momentum(window)
        sig.append(1.0 if (m or 0) > 0 else 0.0)
    res = backtest.backtest_signal(closes, sig)
    print(json.dumps({"ticker": ticker, **res}, indent=2))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "serve":
        _serve()
    elif cmd == "cycle":
        asyncio.run(_cycle())
    elif cmd == "status":
        asyncio.run(_status())
    elif cmd == "backtest":
        if len(sys.argv) < 3:
            print("usage: python run.py backtest TICKER")
            return
        asyncio.run(_backtest(sys.argv[2]))
    elif cmd == "backup":
        from core.backup import backup_now
        print("backup:", backup_now(tag="manual"))
    elif cmd == "backups":
        from core.backup import list_backups
        print("\n".join(list_backups()) or "(none)")
    elif cmd == "restore":
        from core.backup import restore
        if len(sys.argv) < 3:
            print("usage: python run.py restore <backup-name>")
            return
        print("restored" if restore(sys.argv[2]) else "not found:", sys.argv[2])
    elif cmd == "reset":
        from core.backup import reset
        reset(make_backup=True)
        print("runtime state reset (a pre_reset backup was saved)")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
