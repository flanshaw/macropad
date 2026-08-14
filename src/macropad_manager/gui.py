"""macropad-manager: GTK4/libadwaita GUI for viewing and editing profiles."""

from __future__ import annotations

import re
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import core  # noqa: E402

SLOT_LABELS = {
    "button1": "Button 1",
    "button2": "Button 2",
    "button3": "Button 3",
    "knob_ccw": "Knob CCW",
    "knob_press": "Knob press",
    "knob_cw": "Knob CW",
}


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Macropad Manager")
        self.set_default_size(760, 560)
        self.selected: str | None = None
        self.profile_data: dict = {}

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        self.active_label = Gtk.Label(label="")
        self.active_label.add_css_class("title-4")
        header.set_title_widget(self.active_label)

        add_btn = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="New profile")
        add_btn.connect("clicked", self.on_add)
        header.pack_start(add_btn)
        toolbar.add_top_bar(header)

        self.toasts = Adw.ToastOverlay()
        toolbar.set_content(self.toasts)
        self.set_content(toolbar)

        split = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.toasts.set_child(split)

        # --- sidebar: profile cycle order ---
        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=6)
        side.set_size_request(220, -1)
        side.append(Gtk.Label(label="Cycle order", xalign=0, css_classes=["heading"]))
        self.listbox = Gtk.ListBox(css_classes=["boxed-list"])
        self.listbox.connect("row-selected", self.on_select)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=self.listbox)
        side.append(scroll)

        btns = Gtk.Box(spacing=6)
        for icon, tip, cb in [
            ("go-up-symbolic", "Move up", lambda *_: self.move_selected(-1)),
            ("go-down-symbolic", "Move down", lambda *_: self.move_selected(1)),
            ("user-trash-symbolic", "Delete profile", self.on_delete),
        ]:
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.connect("clicked", cb)
            btns.append(b)
        side.append(btns)
        split.append(side)
        split.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        # --- main pane: diagram + editor ---
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       margin_top=12, margin_bottom=12, margin_start=12, margin_end=12,
                       hexpand=True)
        split.append(main)

        # diagram
        diagram = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER)
        self.key_labels: dict[str, Gtk.Label] = {}
        self.key_subs: dict[str, Gtk.Label] = {}
        row = Gtk.Box(spacing=12)
        for slot in ("button1", "button2", "button3"):
            row.append(self._keycap(slot, 110, 90))
        knob_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, halign=Gtk.Align.CENTER)
        arrows = Gtk.Box(spacing=6)
        arrows.append(self._keycap("knob_ccw", 90, 60, "⟲ "))
        arrows.append(self._keycap("knob_press", 90, 90, "◉ "))
        arrows.append(self._keycap("knob_cw", 90, 60, "⟳ "))
        knob_col.append(arrows)
        row.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        row.append(knob_col)
        diagram.append(row)
        main.append(diagram)
        main.append(Gtk.Separator())

        # editor
        self.name_row = Adw.EntryRow(title="Profile name")
        self.entries: dict[str, Gtk.Entry] = {}
        self.label_entries: dict[str, Gtk.Entry] = {}
        group = Adw.PreferencesGroup(title="Bindings")
        group.add(self.name_row)
        for slot in core.SLOTS:
            row = Adw.ActionRow(title=SLOT_LABELS[slot])
            label_entry = Gtk.Entry(placeholder_text="Label", width_chars=12,
                                    valign=Gtk.Align.CENTER)
            binding_entry = Gtk.Entry(placeholder_text="Binding", width_chars=16,
                                      valign=Gtk.Align.CENTER)
            self.label_entries[slot] = label_entry
            self.entries[slot] = binding_entry
            row.add_suffix(label_entry)
            row.add_suffix(binding_entry)
            group.add(row)
        editor_scroll = Gtk.ScrolledWindow(vexpand=True, child=group)
        main.append(editor_scroll)

        actions = Gtk.Box(spacing=8, halign=Gtk.Align.END)
        for label, cb, style in [
            ("Validate", self.on_validate, None),
            ("Save", self.on_save, "suggested-action"),
            ("Upload now", self.on_upload, "destructive-action"),
        ]:
            b = Gtk.Button(label=label)
            if style:
                b.add_css_class(style)
            b.connect("clicked", cb)
            actions.append(b)
        main.append(actions)

        self.status = Gtk.Label(xalign=0, wrap=True, selectable=True)
        main.append(self.status)

        # refresh when state.json changes (e.g. hotkey cycled)
        self.monitor = Gio.File.new_for_path(str(core.STATE_FILE)).monitor_file(
            Gio.FileMonitorFlags.NONE, None)
        self.monitor.connect("changed", lambda *_: GLib.idle_add(self.refresh_header_and_list))

        core.ensure_dirs()
        self.refresh_header_and_list()

    def _keycap(self, slot: str, w: int, h: int, prefix: str = "") -> Gtk.Widget:
        frame = Gtk.Frame()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER,
                      valign=Gtk.Align.CENTER)
        box.set_size_request(w, h)
        title = Gtk.Label(label=prefix + SLOT_LABELS[slot], css_classes=["dim-label", "caption"])
        val = Gtk.Label(label="—", wrap=True, justify=Gtk.Justification.CENTER,
                        css_classes=["heading"])
        sub = Gtk.Label(label="", wrap=True, justify=Gtk.Justification.CENTER,
                        css_classes=["dim-label", "caption"])
        self.key_labels[slot] = val
        self.key_subs[slot] = sub
        box.append(title)
        box.append(val)
        box.append(sub)
        frame.set_child(box)
        return frame

    # ------------------------------------------------------------ refresh ----

    def refresh_header_and_list(self):
        state = core.load_state()
        active = core.active_profile_name(state)
        self.active_label.set_label(
            f"Active profile: {active.removesuffix('.yaml')}" if active else "No profiles")

        prev = self.selected
        self.listbox.remove_all()
        for name in state["order"]:
            row = Gtk.ListBoxRow()
            label = name.removesuffix(".yaml")
            if name == active:
                label = "● " + label
            row.set_child(Gtk.Label(label=label, xalign=0, margin_top=8, margin_bottom=8,
                                    margin_start=8))
            row.profile_name = name
            self.listbox.append(row)
        # reselect
        target = prev if prev in state["order"] else active
        i = 0
        row = self.listbox.get_row_at_index(0)
        while row is not None:
            if row.profile_name == target:
                self.listbox.select_row(row)
                break
            i += 1
            row = self.listbox.get_row_at_index(i)

    def load_selected(self):
        if not self.selected:
            return
        try:
            self.profile_data = core.load_profile(self.selected)
        except Exception as e:
            self.status.set_label(f"Failed to read {self.selected}: {e}")
            return
        bindings = core.profile_bindings(self.profile_data)
        labels = core.profile_labels(self.profile_data)
        self.name_row.set_text(self.selected.removesuffix(".yaml"))
        for slot in core.SLOTS:
            self.entries[slot].set_text(bindings[slot])
            self.label_entries[slot].set_text(labels[slot])
            # Label leads when set; the raw binding drops to the subtitle.
            self.key_labels[slot].set_label(labels[slot] or bindings[slot] or "—")
            self.key_subs[slot].set_label(bindings[slot] if labels[slot] else "")
        self.status.set_label("")

    # ------------------------------------------------------------ handlers ---

    def on_select(self, _lb, row):
        if row is not None:
            self.selected = row.profile_name
            self.load_selected()

    def on_add(self, _btn):
        state = core.load_state()
        n = 1
        while core.profile_path(f"profile{n}.yaml").exists():
            n += 1
        name = f"profile{n}.yaml"
        core.save_profile(name, dict(core.DEFAULT_PROFILE))
        state["order"].append(name)
        core.save_state(state)
        self.selected = name
        self.refresh_header_and_list()

    def on_delete(self, _btn):
        if not self.selected:
            return
        state = core.load_state()
        if self.selected in state["order"]:
            state["order"].remove(self.selected)
        core.profile_path(self.selected).unlink(missing_ok=True)
        state["active_index"] = min(state["active_index"], max(len(state["order"]) - 1, 0))
        core.save_state(state)
        self.selected = None
        self.refresh_header_and_list()

    def move_selected(self, delta: int):
        if not self.selected:
            return
        state = core.load_state()
        order = state["order"]
        active = core.active_profile_name(state)
        i = order.index(self.selected)
        j = i + delta
        if 0 <= j < len(order):
            order[i], order[j] = order[j], order[i]
            state["active_index"] = order.index(active) if active in order else 0
            core.save_state(state)
            self.refresh_header_and_list()

    def _collect(self) -> dict[str, str]:
        return {slot: self.entries[slot].get_text().strip() for slot in core.SLOTS}

    def _collect_labels(self) -> dict[str, str]:
        return {slot: self.label_entries[slot].get_text().strip() for slot in core.SLOTS}

    def _save_current(self) -> str | None:
        """Save editor contents; returns saved filename or None on error."""
        if not self.selected:
            return None
        new_name = self.name_row.get_text().strip()
        if not re.fullmatch(r"[\w. -]+", new_name or ""):
            self.status.set_label("Invalid profile name")
            return None
        new_file = new_name + ".yaml"
        data = core.apply_bindings(self.profile_data, self._collect())
        data = core.apply_labels(data, self._collect_labels())
        if new_file != self.selected:
            state = core.load_state()
            active = core.active_profile_name(state)
            core.profile_path(self.selected).unlink(missing_ok=True)
            state["order"] = [new_file if n == self.selected else n for n in state["order"]]
            if active == self.selected:
                active = new_file
            state["active_index"] = state["order"].index(active) if active in state["order"] else 0
            core.save_state(state)
            self.selected = new_file
        core.save_profile(self.selected, data)
        self.profile_data = data
        return self.selected

    def on_save(self, _btn):
        if self._save_current():
            self.toasts.add_toast(Adw.Toast(title=f"Saved {self.selected}"))
            self.refresh_header_and_list()
            self.load_selected()

    def on_validate(self, _btn):
        name = self._save_current()
        if not name:
            return
        res = core.validate(core.profile_path(name))
        self.status.set_label(("✔ Valid" if res.ok else "✘ Validation failed") +
                              (f"\n{res.output}" if res.output else ""))
        self.refresh_header_and_list()

    def on_upload(self, _btn):
        name = self._save_current()
        if not name:
            return
        res = core.upload(core.profile_path(name))
        if res.ok:
            state = core.load_state()
            if name in state["order"]:
                state["active_index"] = state["order"].index(name)
                core.save_state(state)
            self.toasts.add_toast(Adw.Toast(title=f"Uploaded {name}"))
        self.status.set_label(("✔ Uploaded" if res.ok else "✘ Upload failed") +
                              (f"\n{res.output}" if res.output else ""))
        self.refresh_header_and_list()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="org.flanshaw.MacropadManager")

    def do_activate(self):
        win = self.get_active_window() or MainWindow(self)
        win.present()


def main() -> int:
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
