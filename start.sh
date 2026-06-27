#!/usr/bin/env bash
# loopfund: one command to set everything up and launch the dashboard.
#
#   ./start.sh              install on first run, then start the dashboard
#                           (opens your browser and prints the URL)
#   ./start.sh cycle        run a single research/decision cycle
#   ./start.sh status       print the current portfolio snapshot
#   ./start.sh backtest NVDA
#   ./start.sh --dev        developer mode: backend + Vite dev server (hot reload)
#
# Runs fully local by default (no API keys). See README for choosing a model.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# --- pick a Python (3.11+) ---
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -n "$PY" ] || { echo "Python 3.11+ is required. Get it from https://www.python.org/downloads/"; exit 1; }

VENV="$ROOT/.venv"
VPY="$VENV/bin/python"

# --- install on first run (or if dependencies are missing) ---
if [ ! -x "$VPY" ]; then
  echo "[setup] creating virtual environment..."
  "$PY" -m venv "$VENV"
fi
if ! "$VPY" -c "import fastapi, yfinance, pydantic, uvicorn" >/dev/null 2>&1; then
  echo "[setup] installing dependencies..."
  "$VPY" -m pip install --quiet --upgrade pip
  "$VPY" -m pip install -r "$ROOT/scripts/requirements.txt"
fi

# --- build the dashboard if it is missing and Node is available ---
# A prebuilt dashboard ships in the repo, so this is only needed after source edits.
if [ ! -f "$ROOT/dashboard/web/dist/index.html" ] && command -v npm >/dev/null 2>&1; then
  echo "[setup] building dashboard..."
  ( cd "$ROOT/dashboard/web" && npm install && npm run build )
fi

# --- first-run config ---
[ -f "$ROOT/.env" ] || cp "$ROOT/.env.example" "$ROOT/.env"

export PYTHONPATH="$ROOT"

# --- developer mode: backend + Vite dev server with hot reload ---
if [ "${1:-}" = "--dev" ]; then
  command -v npm >/dev/null 2>&1 || { echo "Node/npm is required for --dev mode."; exit 1; }
  echo "[dev] backend on http://127.0.0.1:8500, dashboard (hot reload) on http://localhost:5173"
  LOOPFUND_NO_BROWSER=1 "$VPY" "$ROOT/scripts/run.py" serve &
  BPID=$!
  trap 'kill "$BPID" 2>/dev/null || true' INT TERM EXIT
  ( cd "$ROOT/dashboard/web" && { [ -d node_modules ] || npm install; } && npm run dev )
  exit 0
fi

# --- default: start the dashboard (or run a CLI subcommand if one is given) ---
exec "$VPY" "$ROOT/scripts/run.py" "${@:-serve}"
