#!/usr/bin/env bash
# Install macropad-manager: pipx package, systemd user unit, GNOME Super+Q hotkey.
set -euo pipefail
cd "$(dirname "$0")"

HOTKEY="${1:-<Super>q}"

echo "==> Checking prerequisites..."
command -v ch57x-keyboard-tool >/dev/null ||
  echo "    WARNING: ch57x-keyboard-tool not found on PATH - uploads will fail."

UDEV_RULE=/etc/udev/rules.d/99-ch57x-macropad.rules
if [ ! -e "$UDEV_RULE" ]; then
  # Writing to the device needs permissions; not done automatically as it needs root.
  echo "    WARNING: no udev rule for the macropad. Uploads will fail unless run"
  echo "    as root. To fix (then replug the device):"
  echo
  echo "      echo 'SUBSYSTEM==\"usb\", ATTR{idVendor}==\"1189\", ATTR{idProduct}==\"8890\", MODE=\"0666\"' \\"
  echo "        | sudo tee $UDEV_RULE"
  echo "      sudo udevadm control --reload-rules && sudo udevadm trigger"
  echo
fi

echo "==> Installing package with pipx..."
pipx install --force --system-site-packages .

echo "==> Installing systemd user unit..."
mkdir -p ~/.config/systemd/user
cp systemd/macropad-daemon.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now macropad-daemon.service || true

echo "==> Installing GNOME Shell HUD extension..."
UUID=macropad-hud@flanshaw.org
EXTDIR=~/.local/share/gnome-shell/extensions/$UUID
mkdir -p "$EXTDIR"
cp extension/$UUID/* "$EXTDIR/"
# GNOME Shell only scans for extensions at startup, so enable via gsettings
# rather than `gnome-extensions enable` (which fails until the shell sees it).
python3 - "$UUID" <<'PY'
import ast, subprocess, sys
uuid = sys.argv[1]
cur = subprocess.run(['gsettings', 'get', 'org.gnome.shell', 'enabled-extensions'],
                     capture_output=True, text=True).stdout.strip()
lst = [] if cur in ('@as []', '[]') else ast.literal_eval(cur)
if uuid not in lst:
    lst.append(uuid)
    subprocess.run(['gsettings', 'set', 'org.gnome.shell', 'enabled-extensions',
                    '[' + ', '.join(f"'{x}'" for x in lst) + ']'], check=True)
PY

echo "==> Registering GNOME custom keybinding ($HOTKEY -> macropad-cycle)..."
BASE=org.gnome.settings-daemon.plugins.media-keys
KEYPATH=/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/macropad-cycle/
current=$(gsettings get $BASE custom-keybindings)
if [[ "$current" != *"$KEYPATH"* ]]; then
  if [[ "$current" == "@as []" || "$current" == "[]" ]]; then
    new="['$KEYPATH']"
  else
    new="${current%]*}, '$KEYPATH']"
  fi
  gsettings set $BASE custom-keybindings "$new"
fi
SCHEMA="$BASE.custom-keybinding:$KEYPATH"
gsettings set "$SCHEMA" name 'Macropad cycle profile'
gsettings set "$SCHEMA" command "$HOME/.local/bin/macropad-cycle"
gsettings set "$SCHEMA" binding "$HOTKEY"

echo "==> Done. Press $HOTKEY to cycle profiles; run 'macropad-manager' for the GUI."
echo "    Log out and back in to load the desktop HUD (GNOME Shell only scans"
echo "    for new extensions at session start)."
