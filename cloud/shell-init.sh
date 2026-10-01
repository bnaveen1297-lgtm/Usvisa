# shellcheck shell=bash
# Opens a terminal ready to run watcher commands (used by the "Visa watcher terminal" shortcut).
# shellcheck disable=SC1090,SC1091
[ -f ~/.bashrc ] && source ~/.bashrc
cd "$(dirname "${BASH_SOURCE[0]}")/.." || return
source .venv/bin/activate
cat <<'MSG'

  Visa slot watcher: one-time setup, in this order
  ------------------------------------------------
  1. python -m watcher setup-telegram     (and/or)   python -m watcher setup-email
  2. nano config.toml                     set your dates; save with Ctrl+O, Enter, Ctrl+X
  3. python -m watcher learn              log in in the browser that opens, open each calendar
  4. Close this window and double-click "Start visa watcher".
     (It also starts by itself whenever the VM restarts.)

  Other: python -m watcher test-alerts    |   update: git pull

MSG
