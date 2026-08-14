# Architecture

## Overview

Four small programs share one directory of state. Nothing talks over a socket
or a bus; the filesystem is the integration point, and file monitors provide
change notification.

```
        Super+Q  ──▶  macropad-cycle  ──┐
                                        │  writes state.json
   HUD click     ──▶  macropad-cycle ──┤  uploads via ch57x-keyboard-tool
                                        │
   GUI save      ──▶  macropad-manager ─┤  writes profiles/*.yaml
                                        │
                                        ▼
                        ~/.config/macropad-manager/
                                        │
                       file monitors    │
                                        ▼
                   HUD (GNOME Shell extension)
                        │
                        └─▶ runs macropad-status ──▶ JSON ──▶ redraw
```

Consequences of this design:

- The GUI does not need to run for cycling, the HUD, or the hotkey to work.
- The HUD updates itself whenever any other component changes state, without
  polling.
- Any component can be replaced or scripted independently — `macropad-cycle`
  and `macropad-status` are ordinary CLIs.

## Components

### `macropad_manager.core`

The only module that knows about the on-disk formats. Everything else goes
through it.

- `load_state()` / `save_state()` — `state.json`, with self-healing: entries
  whose profile file has been deleted are dropped, and `active_index` is
  clamped into range.
- `load_profile()` / `save_profile()` — profile YAML, always forcing
  `model: ch57x-2`.
- `profile_bindings()` / `apply_bindings()` — map between the flat six-slot
  view the UI uses (`button1..3`, `knob_ccw`, `knob_press`, `knob_cw`) and the
  nested `layers[0]` structure the CLI expects.
- `profile_labels()` / `apply_labels()` — the `labels:` extension key.
- `validate()` / `upload()` — wrap `ch57x-keyboard-tool`, capturing stdout and
  stderr together so the GUI can display failures instead of swallowing them.
- `notify()` — `notify-send`, best-effort.

### `macropad-cycle`

Stateless CLI. Computes the target index (next, explicit `--set`, or current
for `--restore`), uploads, and only then commits the new index to `state.json`
— a failed upload leaves the recorded state matching the device.

### `macropad-status`

Prints the whole picture as JSON. Exists because the HUD is written in GJS,
which has no YAML parser; rather than reimplement the format there, the
extension shells out to Python and parses JSON.

### `macropad-manager` (GUI)

GTK4 + libadwaita. Chosen over PyQt because PyGObject ships with Ubuntu GNOME,
so there is no extra dependency and the window matches the desktop.

Editing operations save first and then act, so *Validate* and *Upload now*
always operate on exactly what is on screen. Renaming a profile rewrites the
file and repairs `state.json` order and active index in the same step.

### HUD (GNOME Shell extension)

Wayland does not let an application position its own window, and Mutter does
not implement the layer-shell protocol that desktop widgets use on other
compositors. A GNOME Shell extension draws directly on the shell, which is the
only reliable way to pin a widget to a screen corner on GNOME/Wayland.

- **Placement** uses the *work area*, not the monitor bounds, so the widget
  clears docks and panels.
- **Stacking** is switchable at runtime between the chrome layer (above
  windows) and below `global.window_group` (desktop level).
- **Refresh** is triggered by `Gio.FileMonitor` on `state.json`, the profiles
  directory and `hud.json`, debounced by 250ms because a single save emits
  several change events.
- **Fonts** are applied as inline styles computed from `font_delta` rather than
  fixed in the stylesheet, so size changes do not require reloading the
  extension.

### `macropad-window`

A thin D-Bus client. The knob's rotation is bound to hidden GNOME hotkeys
(`ctrl-alt-shift-f9/f10/f11`) whose command is `macropad-window prev|overview|
next`; each call invokes `NextWindow`, `PrevWindow` or `ToggleOverview` on
`org.flanshaw.MacropadHud`, exported by the HUD extension.

The indirection is forced by Wayland: no client may raise or focus another
application's window, so the actual switching has to happen inside GNOME Shell.
The CLI exists only because GNOME's keybinding mechanism runs commands, not
D-Bus calls.

### `macropad-daemon`

A `Type=oneshot` user unit running `macropad-cycle --restore` at login. The
device forgets its mapping when unplugged or on reboot, so this re-flashes
whatever `state.json` says is active. There is no long-running daemon process:
GNOME invokes the hotkey command directly, so nothing needs to sit resident.

## Key decisions

**Shelling out to `ch57x-keyboard-tool`.** The USB protocol is already
implemented and maintained upstream. Note that the installed version reads
configs from **stdin**, not a file argument, so `core._run_tool` pipes the file
in.

**Window switching by creation order, not MRU.** `get_tab_list` returns
windows most-recently-used first, which reorders itself after every activation:
two detents in the same direction would land back on the starting window.
Sorting by `get_stable_sequence()` gives a list that is stable across the walk,
so a full turn visits every window exactly once. The switcher also trusts its
own cursor for a second after activating, since a fast burst of detents can
outrun `get_focus_window()` catching up.

**No switcher popup.** Each detent activates its window outright rather than
highlighting it in an OSD. The knob has no "release" event to commit a
selection on, so there is nothing to close a popup with.

**Labels inside the profile YAML.** Storing them in a sidecar file would have
kept profiles pristine, but it doubles the number of files to keep in sync.
`ch57x-keyboard-tool validate` accepts unknown top-level keys, so `labels:`
rides along in the same file and profiles remain directly usable with the CLI.

**GNOME custom keybinding instead of raw key grabbing.** Global key grabs are
unreliable or blocked under Wayland. Registering a custom shortcut through
`gsettings` is the supported path, and it means no process has to be listening.
