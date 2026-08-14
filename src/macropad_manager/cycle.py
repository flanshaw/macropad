"""macropad-cycle: switch the active profile and flash it.

Invoked by the GNOME custom keybinding (Super+Q by default) with no arguments
to advance to the next profile, and by the HUD extension with --set to jump
straight to a named profile.
"""

from __future__ import annotations

import argparse
import sys

from . import core


def _resolve_index(state: dict, args: argparse.Namespace) -> int | None:
    order = state["order"]
    if args.restore:
        return state["active_index"]
    if args.set:
        name = args.set if args.set.endswith(".yaml") else args.set + ".yaml"
        if name not in order:
            return None
        return order.index(name)
    return (state["active_index"] + 1) % len(order)


def main() -> int:
    parser = argparse.ArgumentParser(description="Switch macropad profile")
    parser.add_argument("--set", metavar="PROFILE",
                        help="switch to this profile instead of advancing")
    parser.add_argument("--restore", action="store_true",
                        help="re-flash the currently active profile")
    args = parser.parse_args()

    state = core.load_state()
    if not state["order"]:
        if not args.restore:
            core.notify("Macropad", "No profiles configured")
            return 1
        return 0

    index = _resolve_index(state, args)
    if index is None:
        print(f"No such profile: {args.set}", file=sys.stderr)
        return 2

    name = state["order"][index]
    result = core.upload(core.profile_path(name))
    if result.ok:
        state["active_index"] = index
        core.save_state(state)
        core.notify(f"Macropad: {name.removesuffix('.yaml')}", "Profile loaded")
        return 0

    core.notify("Macropad upload failed", result.output[:200])
    print(result.output, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
