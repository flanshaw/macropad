# Configuration reference

Everything lives in `~/.config/macropad-manager/`. All files are plain text and
safe to edit by hand — the GUI and HUD pick up external changes automatically.

```
~/.config/macropad-manager/
    state.json
    hud.json
    profiles/
        default.yaml
        media.yaml
```

---

## `state.json`

Which profiles are in the cycle, and which one is active.

```json
{
  "active_index": 0,
  "order": ["default.yaml", "media.yaml"]
}
```

| Field | Type | Meaning |
|---|---|---|
| `active_index` | integer | Index into `order` of the currently loaded profile |
| `order` | array of strings | Profile filenames, in `Super+Q` cycle order |

The file is self-healing on read: filenames whose profile no longer exists are
dropped, and `active_index` is wrapped into range. A missing file is treated as
an empty state and rebuilt from whatever is in `profiles/`.

`active_index` is only written **after** a successful upload, so if flashing
fails the recorded state still matches what is actually on the device.

---

## `hud.json`

Appearance and behaviour of the desktop widget. Read live — changes apply
within about 250ms, with no logout or extension reload.

```json
{
  "stacking": "top",
  "font_delta": 2
}
```

### `stacking`

| Value | Behaviour |
|---|---|
| `top` (default) | Floats above normal windows; automatically hidden while a fullscreen window is on the same monitor |
| `desktop` | Sits above the wallpaper but below every window |

`desktop` only works if nothing else owns the desktop layer. Desktop-icon
extensions — including **Desktop Icons NG (`ding`), enabled by default on
Ubuntu** — cover the desktop with a full-screen window that will hide the HUD
completely and swallow its clicks. That is why `top` is the default. To use
`desktop`, disable the icons extension first:

```bash
gnome-extensions disable ding@rastersoft.com
```

### `font_delta`

Integer pixels added to every font in the HUD. May be negative. Base sizes are
profile title 10, key labels 8, keycap text 8, section heading 8, profile list
9; `font_delta` shifts all of them together. Keycaps grow to fit their text, so
larger values will not clip.

```bash
# make everything noticeably bigger, applies immediately
echo '{"stacking": "top", "font_delta": 6}' > ~/.config/macropad-manager/hud.json
```

Unrecognised or malformed values fall back to the defaults rather than
breaking the widget.

---

## Profile YAML

One file per profile in `profiles/`. These are ordinary `ch57x-keyboard-tool`
configs and can be used with it directly:

```bash
ch57x-keyboard-tool validate < ~/.config/macropad-manager/profiles/default.yaml
ch57x-keyboard-tool upload   < ~/.config/macropad-manager/profiles/default.yaml
```

```yaml
model: ch57x-2          # always written by the app
orientation: normal
rows: 1
columns: 3
knobs: 1
layers:
  - buttons:
      - [ctrl-shift-c, ctrl-alt-t, ctrl-alt-shift-f]
    knobs:
      - ccw: volumedown
        press: mute
        cw: volumeup
labels:                 # optional, this app only
  button1: COPY
  button2: TERMINAL
  button3: FILES
  knob_cw: VOL
```

### Slots

The GUI and `macropad-status` use six flat slot names, which map onto the
nested structure above:

| Slot | Position in the YAML |
|---|---|
| `button1`, `button2`, `button3` | `layers[0].buttons[0][0..2]` |
| `knob_ccw` | `layers[0].knobs[0].ccw` |
| `knob_press` | `layers[0].knobs[0].press` |
| `knob_cw` | `layers[0].knobs[0].cw` |

### `labels`

Optional display names, one per slot, used by the HUD and the GUI diagram.
`ch57x-keyboard-tool` ignores the key, so adding it does not affect validation
or upload. Slots with no label fall back to showing the raw binding.

The HUD draws a single knob, so it shows the first label it finds among
`knob_cw`, `knob_press`, `knob_ccw` — label any one of them and it appears.

### Binding names

Valid binding strings come from `ch57x-keyboard-tool`:

```bash
ch57x-keyboard-tool show-keys
```

Modifiers combine with dashes (`ctrl-shift-c`). Media keys are `prev`, `play`,
`next`, `volumeup`, `volumedown`, `mute` — *not* `prevsong`/`nextsong`, which
will fail validation.

---

## GNOME settings written by the installer

These live in dconf rather than in this directory:

| Setting | Value |
|---|---|
| `org.gnome.settings-daemon.plugins.media-keys custom-keybindings` | gains `.../macropad-cycle/` |
| `…custom-keybinding:/…/macropad-cycle/ name` | `Macropad cycle profile` |
| `…custom-keybinding:/…/macropad-cycle/ command` | `~/.local/bin/macropad-cycle` |
| `…custom-keybinding:/…/macropad-cycle/ binding` | `<Super>q` |
| `org.gnome.shell enabled-extensions` | gains `macropad-hud@flanshaw.org` |

The shortcut is visible in Settings → Keyboard → View and Customize Shortcuts →
Custom Shortcuts as "Macropad cycle profile".
