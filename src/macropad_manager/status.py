"""macropad-status: emit current state + bindings as JSON.

Used by the GNOME Shell HUD extension, which has no YAML parser of its own.
"""

from __future__ import annotations

import json
import sys

from . import core


def snapshot() -> dict:
    state = core.load_state()
    profiles = []
    for name in state["order"]:
        try:
            data = core.load_profile(name)
            bindings = core.profile_bindings(data)
            labels = core.profile_labels(data)
        except Exception:
            bindings = dict.fromkeys(core.SLOTS, "")
            labels = dict.fromkeys(core.SLOTS, "")
        profiles.append({
            "file": name,
            "name": name.removesuffix(".yaml"),
            "bindings": bindings,
            "labels": labels,
        })
    return {"active_index": state["active_index"], "profiles": profiles}


def main() -> int:
    json.dump(snapshot(), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
