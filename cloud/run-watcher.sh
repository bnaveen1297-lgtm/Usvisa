#!/usr/bin/env bash
# Runs the watcher in the remote desktop and restarts it if it stops unexpectedly.
cd "$(dirname "$0")/.." || exit 1
# shellcheck disable=SC1091
source .venv/bin/activate

if [ ! -f captured_requests.json ]; then
  cat <<'MSG'
The watcher isn't set up yet. Double-click "Visa watcher terminal" on the desktop
and follow the steps it shows. Then double-click "Start visa watcher".
MSG
  exit 0
fi

while true; do
  python -m watcher watch
  code=$?
  case $code in
    0) exit 0 ;;  # you pressed Ctrl+C
    2) echo "Fix the setup problem above, then double-click \"Start visa watcher\"."; exit 2 ;;
  esac
  echo "Watcher stopped unexpectedly (exit $code). Restarting in 60 seconds; close this window to cancel."
  sleep 60
done
