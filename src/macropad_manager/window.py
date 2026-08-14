"""macropad-window: drive GNOME window focus from the macropad knob.

Bound to three hidden GNOME hotkeys that the knob emits (see install.sh). All
this does is call the HUD extension over D-Bus: on Wayland only GNOME Shell
itself may move focus between windows, so the switching lives in the extension
and this is the bridge from a keypress to it.
"""

from __future__ import annotations

import sys

from gi.repository import Gio, GLib

from . import core

BUS_NAME = "org.flanshaw.MacropadHud"
OBJECT_PATH = "/org/flanshaw/MacropadHud"
INTERFACE = "org.flanshaw.MacropadHud"

ACTIONS = {
    "next": "NextWindow",
    "prev": "PrevWindow",
    "overview": "ToggleOverview",
}


def call(method: str) -> str | None:
    """Invoke a method on the HUD extension; returns an error string or None."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            BUS_NAME, OBJECT_PATH, INTERFACE, method,
            None, None, Gio.DBusCallFlags.NONE, 2000, None,
        )
    except GLib.Error as e:
        return e.message
    return None


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ACTIONS:
        print(f"usage: macropad-window {{{'|'.join(ACTIONS)}}}", file=sys.stderr)
        return 2

    error = call(ACTIONS[sys.argv[1]])
    if error is None:
        return 0

    # By far the likeliest cause is the HUD extension being off or not yet
    # reloaded, so say that rather than echoing a raw D-Bus error.
    core.notify("Macropad", "Window switching needs the HUD extension enabled")
    print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
