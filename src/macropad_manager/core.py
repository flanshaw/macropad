"""Shared logic: config dir, state.json, profile YAML, ch57x-keyboard-tool wrapper."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_DIR = Path.home() / ".config" / "macropad-manager"
PROFILES_DIR = CONFIG_DIR / "profiles"
STATE_FILE = CONFIG_DIR / "state.json"

TOOL = "ch57x-keyboard-tool"

# Slot keys used by the GUI/editor, in display order.
SLOTS = ["button1", "button2", "button3", "knob_ccw", "knob_press", "knob_cw"]

DEFAULT_PROFILE = {
    "orientation": "normal",
    "rows": 1,
    "columns": 3,
    "knobs": 1,
    "layers": [
        {
            "buttons": [["a", "b", "c"]],
            "knobs": [{"ccw": "volumedown", "press": "mute", "cw": "volumeup"}],
        }
    ],
}


def ensure_dirs() -> None:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------- state ------

def load_state() -> dict:
    ensure_dirs()
    try:
        state = json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    state.setdefault("active_index", 0)
    order = state.get("order")
    if not isinstance(order, list):
        # bootstrap order from whatever profiles exist
        order = sorted(p.name for p in PROFILES_DIR.glob("*.yaml"))
        state["order"] = order
    # drop entries whose file disappeared
    state["order"] = [n for n in state["order"] if (PROFILES_DIR / n).exists()]
    if state["order"]:
        state["active_index"] %= len(state["order"])
    else:
        state["active_index"] = 0
    return state


def save_state(state: dict) -> None:
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")


def active_profile_name(state: dict | None = None) -> str | None:
    state = state or load_state()
    if not state["order"]:
        return None
    return state["order"][state["active_index"]]


# -------------------------------------------------------------- profiles -----

def profile_path(name: str) -> Path:
    return PROFILES_DIR / name


def list_profiles() -> list[str]:
    ensure_dirs()
    return sorted(p.name for p in PROFILES_DIR.glob("*.yaml"))


def load_profile(name: str) -> dict:
    data = yaml.safe_load(profile_path(name).read_text()) or {}
    data["model"] = "ch57x-2"
    return data


def save_profile(name: str, data: dict) -> Path:
    ensure_dirs()
    data = dict(data)
    data["model"] = "ch57x-2"
    path = profile_path(name)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def profile_bindings(data: dict) -> dict[str, str]:
    """Extract the 6 slot bindings from layer 1 of a profile dict."""
    out = dict.fromkeys(SLOTS, "")
    try:
        layer = data["layers"][0]
        row = layer["buttons"][0]
        for i in range(3):
            out[f"button{i + 1}"] = str(row[i]) if i < len(row) else ""
        knob = layer["knobs"][0]
        out["knob_ccw"] = str(knob.get("ccw", ""))
        out["knob_press"] = str(knob.get("press", ""))
        out["knob_cw"] = str(knob.get("cw", ""))
    except (KeyError, IndexError, TypeError):
        pass
    return out


def profile_labels(data: dict) -> dict[str, str]:
    """Friendly names per slot (e.g. button2 -> "TERMINAL").

    Stored under a `labels:` key in the profile YAML. ch57x-keyboard-tool
    ignores unknown top-level keys, so profiles stay valid for direct CLI use.
    """
    raw = data.get("labels") or {}
    return {slot: str(raw.get(slot) or "") for slot in SLOTS}


def apply_labels(data: dict, labels: dict[str, str]) -> dict:
    data = dict(data) if data else {}
    cleaned = {slot: labels[slot].strip() for slot in SLOTS
               if labels.get(slot, "").strip()}
    if cleaned:
        data["labels"] = cleaned
    else:
        data.pop("labels", None)
    return data


def apply_bindings(data: dict, bindings: dict[str, str]) -> dict:
    """Write the 6 slot bindings back into layer 1 of a profile dict."""
    data = dict(data) if data else {}
    data.setdefault("orientation", "normal")
    data["rows"], data["columns"], data["knobs"] = 1, 3, 1
    layers = data.get("layers") or [{}]
    layer = layers[0] or {}
    layer["buttons"] = [[bindings.get(f"button{i + 1}", "") for i in range(3)]]
    layer["knobs"] = [{
        "ccw": bindings.get("knob_ccw", ""),
        "press": bindings.get("knob_press", ""),
        "cw": bindings.get("knob_cw", ""),
    }]
    layers[0] = layer
    data["layers"] = layers
    data["model"] = "ch57x-2"
    return data


# ------------------------------------------------------------------ tool -----

@dataclass
class ToolResult:
    ok: bool
    output: str


def _run_tool(subcommand: str, yaml_path: Path) -> ToolResult:
    if shutil.which(TOOL) is None:
        return ToolResult(False, f"{TOOL} not found in PATH")
    try:
        proc = subprocess.run(
            [TOOL, subcommand],
            stdin=yaml_path.open("rb"),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return ToolResult(False, str(e))
    output = (proc.stdout + proc.stderr).strip()
    return ToolResult(proc.returncode == 0, output)


def validate(yaml_path: Path) -> ToolResult:
    return _run_tool("validate", yaml_path)


def upload(yaml_path: Path) -> ToolResult:
    return _run_tool("upload", yaml_path)


def notify(title: str, body: str = "") -> None:
    if shutil.which("notify-send"):
        subprocess.run(
            ["notify-send", "-a", "Macropad", "-t", "2500", title, body],
            check=False,
        )
