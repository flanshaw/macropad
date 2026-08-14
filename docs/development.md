# Development

## Layout

```
src/macropad_manager/       Python package (core, gui, cycle, status)
extension/                  GNOME Shell extension source (GJS)
systemd/                    user unit
install.sh                  installs all of the above
```

`install.sh` is idempotent — re-run it after any change to reinstall the
package, refresh the extension files and re-apply the GNOME settings.

## Working on the Python side

```bash
pipx install --force --system-site-packages .     # reinstall after edits
python3 -m py_compile src/macropad_manager/*.py   # quick syntax check
```

`--system-site-packages` is required: the GUI imports PyGObject, which is
installed system-wide by Ubuntu and cannot be pip-installed into the pipx venv.

Run without installing:

```bash
PYTHONPATH=src python3 -m macropad_manager.gui
PYTHONPATH=src python3 -m macropad_manager.status
```

Changes to Python take effect on the next run of the command — no session
restart, and the HUD picks up new `macropad-status` output automatically.

## Working on the extension

```bash
node --check extension/macropad-hud@flanshaw.org/extension.js   # syntax check
cp extension/macropad-hud@flanshaw.org/* \
   ~/.local/share/gnome-shell/extensions/macropad-hud@flanshaw.org/
```

### Reloading — read this before debugging a change that "did nothing"

| What changed | What is needed |
|---|---|
| `hud.json` | Nothing. Applied live within ~250ms |
| Profiles, bindings, labels | Nothing. File monitors trigger a redraw |
| Python code | Reinstall; next invocation uses it |
| **`extension.js` or `stylesheet.css`** | **Log out and back in** |

There is no lighter way to reload the extension on GNOME 50 / Wayland:

- `gnome-extensions disable && enable` calls `disable()`/`enable()` on the
  **already-imported** module. GNOME caches the ES module, so an edited file is
  never re-read. The widget visibly disappears and comes back, which looks like
  a reload but runs the old code.
- `ReloadExtension` over D-Bus returns
  `"ReloadExtension is deprecated and does not work"`.
- Wayland has no in-place shell restart; the X11 Alt+F2 → `r` trick is gone.
- A newly *installed* extension is likewise not detected until session start,
  which is why `install.sh` enables it through `gsettings` rather than
  `gnome-extensions enable` (that fails with "does not exist" until the shell
  has scanned).

Because of this, anything likely to need tuning belongs in `hud.json` rather
than in the code — that is why stacking and font size live there.

### Checking which build is live

The extension logs its version on enable:

```bash
journalctl --user -b | grep macropad-hud
# macropad-hud: enable() version 0.2.0
```

If the version does not match `HUD_VERSION` in the source, the shell is still
running an older module and any behaviour you observe is stale. Runtime errors
from the extension appear in the same place.

Bump `HUD_VERSION` in `extension.js` alongside `version-name` in
`metadata.json` when making changes, so this check stays meaningful.

## Testing against the device

```bash
macropad-status | python3 -m json.tool     # what the HUD sees
macropad-cycle --set media                 # flash a specific profile
ch57x-keyboard-tool validate < ~/.config/macropad-manager/profiles/media.yaml
```

`validate` needs no hardware; `upload` needs the macropad plugged in and the
udev rule from the README in place.

## Gotchas worth knowing

- The installed `ch57x-keyboard-tool` reads configs from **stdin**, not a
  filename argument. `core._run_tool` pipes the file in.
- Media keys are `prev` / `play` / `next`. `prevsong` and friends fail
  validation with a `MapRes` error.
- St widget sizing: keycaps use `min-width`/`padding` rather than fixed
  `width`, so they grow with `font_delta` instead of clipping.
- GNOME 48+ removed `St.BoxLayout`'s `vertical` property; use
  `orientation: Clutter.Orientation.VERTICAL`.
- The HUD positions itself from `getWorkAreaForMonitor`, not monitor bounds, so
  it clears docks and panels. It repositions on `monitors-changed`,
  `workareas-changed` and its own height changes.
