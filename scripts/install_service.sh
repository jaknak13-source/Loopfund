#!/usr/bin/env bash
# Install the fund as a macOS launchd service: auto-starts on login, auto-restarts
# on crash, and auto-runs the 24/7 research/trade loop. Dry mode only.
#
#   ./scripts/install_service.sh [interval_seconds]   # default 1800 (30 min)
#   ./scripts/install_service.sh --uninstall
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LABEL="com.loopfund.fund"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ "${1:-}" = "--uninstall" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "[service] uninstalled $LABEL"
  exit 0
fi

INTERVAL="${1:-5}"   # gap between continuous research tasks (decisions paced by decision.interval_hours)
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "venv missing — run ./start.sh once first"; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/logs"
cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$ROOT/scripts/run.py</string>
    <string>serve</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>LOOPFUND_AUTOLOOP</key><string>$INTERVAL</string>
    <key>PYTHONPATH</key><string>$ROOT</string>
  </dict>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/logs/service.out.log</string>
  <key>StandardErrorPath</key><string>$ROOT/logs/service.err.log</string>
</dict></plist>
PLIST_EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "[service] installed + loaded $LABEL (loop interval ${INTERVAL}s)."
echo "[service] auto-starts on login, auto-restarts on crash, auto-runs the loop."
echo "[note] keep LM Studio running + the Mac awake (caffeinate -dimsu &)."
echo "[note] uninstall: ./scripts/install_service.sh --uninstall"
