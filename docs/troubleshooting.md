# Troubleshooting

## The HUD does not appear

**First, check whether it is loaded:**

```bash
gnome-extensions info macropad-hud@flanshaw.org
journalctl --user -b | grep macropad-hud
```

| Symptom | Cause and fix |
|---|---|
| `does not exist` | The shell has not scanned it yet. Log out and back in |
| `State: INACTIVE` | `gnome-extensions enable macropad-hud@flanshaw.org` |
| `State: ERROR` | See the traceback in the journal output above |
| `State: ACTIVE` but nothing on screen | Something is covering it — see below |

**Active but invisible** almost always means `"stacking": "desktop"` combined
with a desktop-icons extension. Desktop Icons NG (`ding`) is enabled by default
on Ubuntu and covers the desktop with a full-screen window, hiding the widget
and swallowing its clicks. Fix by floating the HUD above windows:

```bash
echo '{"stacking": "top", "font_delta": 2}' > ~/.config/macropad-manager/hud.json
```

That applies immediately. To keep desktop level instead, disable the icons
extension: `gnome-extensions disable ding@rastersoft.com`.

## Changes to the HUD have no effect

If you edited `extension.js` or `stylesheet.css`, you must log out and back in
— disabling and re-enabling the extension runs the cached module, not your new
code, and `ReloadExtension` was removed in GNOME 50. Confirm which build is
live with:

```bash
journalctl --user -b | grep "macropad-hud: enable"
```

Changes to `hud.json`, profiles and labels need no reload at all. See
[development.md](development.md) for the full matrix.

## `Super+Q` does nothing

1. Confirm the binding is registered:

   ```bash
   gsettings get org.gnome.settings-daemon.plugins.media-keys.custom-keybinding:\
   /org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/macropad-cycle/ binding
   ```

   It should print `'<Super>q'`. It also appears in Settings → Keyboard → View
   and Customize Shortcuts → Custom Shortcuts as "Macropad cycle profile".

2. If it is registered but unresponsive, log out and back in —
   `gnome-settings-daemon` sometimes needs a session restart to pick up a newly
   added custom shortcut.

3. Test the command directly. If this works but the hotkey does not, the
   problem is the binding, not the app:

   ```bash
   macropad-cycle
   ```

4. Another application may have claimed the shortcut. Re-run the installer with
   a different one: `./install.sh '<Super>F9'`.

## Upload fails

Run it in a terminal to see the error:

```bash
macropad-cycle
```

| Error | Fix |
|---|---|
| Permission / access denied | Missing udev rule — see [README](../README.md#device-permissions), then replug |
| `device not found` / no device | `lsusb -d 1189:8890` to confirm it is connected |
| `ch57x-keyboard-tool not found in PATH` | Install it, or ensure `~/.cargo/bin` is on `PATH` |
| `error MapRes at: …` | An invalid binding name — check `ch57x-keyboard-tool show-keys` |

Note that a failed upload deliberately leaves `active_index` unchanged, so the
recorded state keeps matching the device.

## Validation fails on media keys

Use `prev`, `play`, `next` — not `prevsong`, `playpause` or `nextsong`. Full
list:

```bash
ch57x-keyboard-tool show-keys
```

## The GUI will not start

```bash
macropad-manager
```

`ModuleNotFoundError: No module named 'gi'` means the package was installed
without access to system PyGObject. Reinstall with:

```bash
pipx install --force --system-site-packages .
```

## The device forgets its mapping after reboot

That is expected — the mapping is volatile. The `macropad-daemon` user service
re-flashes the active profile at login:

```bash
systemctl --user status macropad-daemon.service
systemctl --user enable --now macropad-daemon.service
```

If it runs before the device is ready, just press `Super+Q` twice to cycle back
around, or run `macropad-cycle --restore`.

## Profiles disappeared from the cycle

`state.json` drops entries whose file no longer exists. If you renamed or moved
a profile outside the GUI, re-add it by editing `order` in
`~/.config/macropad-manager/state.json`, or delete the file entirely to have it
rebuilt from the contents of `profiles/`.
