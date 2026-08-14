# Macropad Layer Manager — Software Spec

> **Historical document.** This is the original design spec the project was
> built from, kept for context. It is not maintained as the implementation
> evolves — see [architecture.md](architecture.md) for how the system actually
> works today, and [configuration.md](configuration.md) for current formats.
>
> Notable divergences from this spec:
> - The desktop HUD (a GNOME Shell extension) was added afterwards and is now
>   the primary interface; it is not described here.
> - `ch57x-keyboard-tool` reads configs from **stdin**, not a file argument.
> - There is no resident daemon process: GNOME runs `macropad-cycle` directly,
>   and the systemd unit is a `oneshot` that restores the active profile at
>   login.
> - Profiles carry an extra `labels:` key for display names.

## Overview
A lightweight Python GUI + background hotkey daemon for Ubuntu 24.04 that manages
multiple keybinding profiles ("mappings") for a CH57x-based 3-key + 1-knob USB
macropad (VID:PID `1189:8890`), and re-flashes the device via the existing CLI
tool `ch57x-keyboard-tool` when the user cycles profiles with a global hotkey
(default: `Super+Q`).

This is a **companion/config-manager app**, not a replacement for
`ch57x-keyboard-tool`. All actual writing to the device is done by shelling out
to `ch57x-keyboard-tool upload <file>.yaml`.

---

## Functional Requirements

1. **Visual layout view**
   - Show a simple on-screen diagram: 3 buttons in a row + 1 knob (rotate CW/CCW + press).
   - Above/on each button and the knob, display the currently assigned action
     (e.g. `ctrl-shift-c`), pulled from the active mapping file.
   - Display the name of the currently active mapping profile prominently
     (e.g. header text: "Active profile: Coding").

2. **Mapping editor**
   - User can create/edit a mapping: assign an action string to each of the
     3 buttons and to knob CW / knob CCW / knob press.
   - User can name each mapping (e.g. "Coding", "Media", "Discord").
   - "Validate" button runs `ch57x-keyboard-tool validate <file>.yaml` and shows
     pass/fail + error output inline (don't just shell out blind — capture
     stderr and display it in the UI).
   - "Save" writes the mapping to its own YAML file, `model: ch57x-2` always
     included.
   - Optionally: "Upload now" button to flash the currently-edited mapping
     immediately for testing, without waiting for the hotkey cycle.

3. **Global hotkey cycling**
   - Listen system-wide for `Super+Q` (must work outside the app window,
     i.e. even when another app has focus).
   - On each press: advance to the *next* mapping in a user-defined ordered
     list (wrapping: 1 → 2 → 3 → 1 → ...).
   - On advance: run `ch57x-keyboard-tool upload <next-mapping>.yaml`, update
     "active profile" state, and refresh the GUI's displayed layout if open.
   - Should show a brief desktop notification (via `notify-send` or
     `libnotify`/`Gio.Notification`) confirming which profile was just loaded
     — since upload isn't instant and there's no on-device feedback.

4. **Language / performance**
   - Python 3 (Ubuntu 24.04 ships 3.12).
   - Must be lightweight and fast: avoid Electron-style stacks entirely.
     Recommended: **PyQt6** or **PySide6** for the GUI (native, fast, good
     Wayland/X11 support on GNOME 46 which ships with 24.04), OR **GTK4 +
     libadwaita via PyGObject** if a native GNOME look is preferred.
   - The hotkey listener + upload logic should run as a small background
     process independent of whether the GUI window is open (see Architecture).

---

## Architecture

Two logical components, one codebase:

### A. Background daemon (`macropad-daemon`)
- Runs at login (systemd `--user` service is the right mechanism on Ubuntu 24.04
  — avoids needing root, restarts on crash, starts on login automatically).
- Responsibilities:
  - Registers the global hotkey. On GNOME/Wayland (default in 24.04), global
    hotkeys should be registered via **GNOME's custom keybinding D-Bus/
    gsettings mechanism** (i.e. the app installs a custom keybinding into
    `org.gnome.settings-daemon.plugins.media-keys.custom-keybindings` pointing
    at a small CLI entrypoint like `macropad-cycle`), rather than trying to
    do raw global key-grabbing, which is unreliable/blocked under Wayland.
  - `macropad-cycle` (small CLI command, called by the GNOME custom shortcut):
    reads current state (which mapping index is active) from a state file,
    computes the next index, calls `ch57x-keyboard-tool upload`, updates
    state file, fires a desktop notification.
  - Maintains `~/.config/macropad-manager/state.json` — active profile index,
    ordered list of profile file paths.

### B. GUI application (`macropad-manager`)
- Standalone window, launched from app menu or `macropad-manager` command.
- Reads the same `~/.config/macropad-manager/` directory:
  - `profiles/*.yaml` — one file per mapping, named by the user.
  - `state.json` — shared state (active profile, cycle order).
- Renders the button/knob diagram + current bindings.
- Edits/validates/saves profile YAML files.
- Lets user reorder/add/remove profiles from the cycle list.
- Does **not** need to be running for hotkey cycling to work — it's purely a
  viewer/editor. The daemon + GNOME custom shortcut handle cycling
  independently.

### Shared logic (`macropad_core` module)
- Wraps calls to `ch57x-keyboard-tool` (validate / upload), parses its
  stdout/stderr.
- Reads/writes profile YAML (thin wrapper — no need to reinvent the config
  schema, just read/write the same format `ch57x-keyboard-tool` expects).
- Reads/writes `state.json`.

---

## File Layout

```
~/.config/macropad-manager/
    state.json              # {"active_index": 0, "order": ["coding.yaml", "media.yaml"]}
    profiles/
        coding.yaml
        media.yaml
        discord.yaml
```

Each profile YAML is a valid `ch57x-keyboard-tool` config (with `model:
ch57x-2`, `orientation`, `rows`, `columns`, `knobs`, `layers` etc.) — no custom
schema needed on top, so profiles remain directly compatible with the CLI tool
for manual use/debugging.

---

## Installation / Packaging

- Ship as a `pipx`-installable package or a `.deb` if the developer wants
  a cleaner install experience — either is fine, pipx is less effort.
- Include a systemd `--user` unit file for the daemon:
  `~/.config/systemd/user/macropad-daemon.service`
- Include a small install script that:
  1. Registers the GNOME custom keybinding for `Super+Q` → `macropad-cycle`
     via `gsettings`.
  2. Enables + starts the systemd user service.

---

## Non-goals / out of scope
- No support for chorded key detection (key1+key2 pressed together) — this is
  a hardware/firmware limitation, not something this app can add.
- No cross-platform support required — Ubuntu 24.04 / GNOME only.
- No need to reimplement `ch57x-keyboard-tool`'s upload/validate logic —
  always shell out to the existing binary.

---

## Suggested tech stack summary
| Concern | Choice |
|---|---|
| Language | Python 3.12 |
| GUI | PyQt6 or GTK4 (PyGObject) |
| Global hotkey | GNOME custom keybinding (gsettings) → CLI entrypoint |
| Background process | systemd `--user` service |
| Device programming | Shell out to `ch57x-keyboard-tool` (existing Rust CLI) |
| Config format | YAML (reuse `ch57x-keyboard-tool`'s own schema) |
| Notifications | `notify-send` / `Gio.Notification` |
