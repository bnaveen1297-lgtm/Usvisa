#!/usr/bin/env bash
# One-time setup for a Debian 12 Google Cloud VM. In the VM's SSH window, run:
#   curl -fsSL https://raw.githubusercontent.com/bnaveen1297-lgtm/Usvisa/master/cloud/setup-vm.sh | bash
# Safe to run again (e.g. after an update).
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/bnaveen1297-lgtm/Usvisa.git}"
APP_DIR="${APP_DIR:-$HOME/Usvisa}"

if [ "$(id -u)" -eq 0 ]; then
  echo "Run this as your normal user (no sudo); it asks for sudo itself where needed." >&2
  exit 1
fi

step() { printf '\n==> %s\n' "$*"; }

step "Installing a desktop, Python and git (takes a few minutes)"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  xfce4 xfce4-terminal desktop-base dbus-x11 xscreensaver \
  python3 python3-venv git curl nano
# Chrome Remote Desktop brings its own display, so the normal login screen isn't needed.
sudo systemctl disable --now lightdm.service 2>/dev/null || true

step "Installing Chrome Remote Desktop"
if ! dpkg -s chrome-remote-desktop >/dev/null 2>&1; then
  curl -fsSL -o /tmp/chrome-remote-desktop.deb \
    https://dl.google.com/linux/direct/chrome-remote-desktop_current_amd64.deb
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q /tmp/chrome-remote-desktop.deb
  rm -f /tmp/chrome-remote-desktop.deb
fi
echo "exec /etc/X11/Xsession /usr/bin/xfce4-session" | sudo tee /etc/chrome-remote-desktop-session >/dev/null
# Never blank or lock the remote screen: cloud VM users have no password to unlock it with.
printf 'mode:\toff\nlock:\tFalse\n' > "$HOME/.xscreensaver"

step "Setting the clock to India time"
sudo timedatectl set-timezone Asia/Kolkata 2>/dev/null || true

step "Downloading the watcher to $APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone -q "$REPO_URL" "$APP_DIR"
fi

step "Installing the watcher and its browser"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements.txt"
sudo "$APP_DIR/.venv/bin/python" -m playwright install-deps chromium
"$APP_DIR/.venv/bin/python" -m playwright install chromium
[ -f "$APP_DIR/config.toml" ] || cp "$APP_DIR/config.example.toml" "$APP_DIR/config.toml"
chmod +x "$APP_DIR/cloud/"*.sh

step "Adding desktop shortcuts and auto-start"
mkdir -p "$HOME/Desktop" "$HOME/.config/autostart"
launcher() { # file name, title, command
  cat > "$1" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$2
Exec=xfce4-terminal --title="$2" --hold --command="$3"
Icon=utilities-terminal
Terminal=false
DESKTOP
  chmod +x "$1"
}
launcher "$HOME/Desktop/visa-watcher-terminal.desktop" "Visa watcher terminal" \
  "bash --init-file $APP_DIR/cloud/shell-init.sh"
launcher "$HOME/Desktop/start-visa-watcher.desktop" "Start visa watcher" "$APP_DIR/cloud/run-watcher.sh"
# Starts the watcher whenever the remote desktop session starts, including after a VM reboot.
cp "$HOME/Desktop/start-visa-watcher.desktop" "$HOME/.config/autostart/visa-watcher.desktop"

cat <<'DONE'

==> Done.

Next: connect Chrome Remote Desktop (step 4 in docs/google-cloud.md):
  1. On your own computer, open https://remotedesktop.google.com/headless
  2. Begin -> Next -> Authorize, then copy the "Debian Linux" command.
  3. Paste it into THIS window, press Enter, and choose a 6-digit PIN.
DONE
