import Clutter from 'gi://Clutter';
import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const CONFIG_DIR = GLib.build_filenamev([GLib.get_home_dir(), '.config', 'macropad-manager']);
const STATE_FILE = GLib.build_filenamev([CONFIG_DIR, 'state.json']);
const PROFILES_DIR = GLib.build_filenamev([CONFIG_DIR, 'profiles']);
const HUD_CONFIG = GLib.build_filenamev([CONFIG_DIR, 'hud.json']);
const MARGIN = 12;
const HUD_VERSION = '0.2.0';

// Where the HUD sits in the stack, read from hud.json at runtime:
//   'top'     - floats above normal windows, hidden by fullscreen apps.
//   'desktop' - above the wallpaper but below every window. Note that
//               desktop-icon extensions (ding) cover the desktop with their
//               own window and will hide the HUD entirely.
const DEFAULT_STACKING = 'top';

// Base point sizes; hud.json's font_delta shifts all of them together.
// Applied as inline styles so font changes never need a shell restart.
const FONT_BASE = {title: 10, key: 8, cap: 8, heading: 8, item: 9};
const DEFAULT_FONT_DELTA = 2;

const BUTTONS = ['button1', 'button2', 'button3'];
// The HUD draws one knob, so it takes whichever knob action carries a label.
const KNOB_SLOTS = ['knob_cw', 'knob_press', 'knob_ccw'];

/** Entry points live in ~/.local/bin, which is not always on the shell's PATH. */
function commandPath(name) {
    return GLib.find_program_in_path(name) ??
        GLib.build_filenamev([GLib.get_home_dir(), '.local', 'bin', name]);
}

function spawn(argv) {
    try {
        new Gio.Subprocess({argv, flags: Gio.SubprocessFlags.NONE}).init(null);
    } catch (e) {
        logError(e, 'macropad-hud: failed to spawn ' + argv.join(' '));
    }
}

class Hud {
    constructor() {
        this._fontDelta = DEFAULT_FONT_DELTA;
        this._data = null;

        this.actor = new St.BoxLayout({
            style_class: 'macropad-hud',
            orientation: Clutter.Orientation.HORIZONTAL,
            reactive: true,
            track_hover: true,
        });

        // ---- left: profile name + keycaps ----
        const left = new St.BoxLayout({
            style_class: 'macropad-left',
            orientation: Clutter.Orientation.VERTICAL,
        });
        this._title = new St.Label({style_class: 'macropad-title', text: '—'});
        left.add_child(this._title);

        const keys = new St.BoxLayout({
            style_class: 'macropad-keys',
            orientation: Clutter.Orientation.HORIZONTAL,
        });
        this._keyText = {};
        this._capText = {};
        for (const slot of BUTTONS) keys.add_child(this._makeKey(slot, false));
        keys.add_child(this._makeKey('knob', true));
        left.add_child(keys);
        this.actor.add_child(left);

        this.actor.add_child(new St.Widget({style_class: 'macropad-divider'}));

        // ---- right: profile list + gear ----
        const right = new St.BoxLayout({
            style_class: 'macropad-right',
            orientation: Clutter.Orientation.VERTICAL,
        });
        const header = new St.BoxLayout({style_class: 'macropad-header'});
        this._heading = new St.Label({
            style_class: 'macropad-heading',
            text: 'PROFILES',
            y_align: Clutter.ActorAlign.CENTER,
        });
        header.add_child(this._heading);
        const gear = new St.Button({
            style_class: 'macropad-gear',
            child: new St.Icon({icon_name: 'emblem-system-symbolic', icon_size: 12}),
            x_align: Clutter.ActorAlign.END,
            x_expand: true,
        });
        gear.connect('clicked', () => spawn([commandPath('macropad-manager')]));
        header.add_child(gear);
        right.add_child(header);

        this._list = new St.BoxLayout({
            style_class: 'macropad-list',
            orientation: Clutter.Orientation.VERTICAL,
        });
        right.add_child(this._list);
        this.actor.add_child(right);

        this._applyFonts();
    }

    /** Friendly label above the cap; the raw binding sits inside it. */
    _makeKey(slot, isKnob) {
        const box = new St.BoxLayout({
            style_class: 'macropad-key',
            orientation: Clutter.Orientation.VERTICAL,
        });
        this._keyText[slot] = new St.Label({
            style_class: 'macropad-keylabel',
            text: '—',
            x_align: Clutter.ActorAlign.CENTER,
        });
        box.add_child(this._keyText[slot]);

        if (isKnob) {
            box.add_child(new St.Widget({style_class: 'macropad-knobcap'}));
        } else {
            this._capText[slot] = new St.Label({
                style_class: 'macropad-keycap',
                text: '',
                x_align: Clutter.ActorAlign.CENTER,
            });
            box.add_child(this._capText[slot]);
        }
        return box;
    }

    setFontDelta(delta) {
        if (delta === this._fontDelta) return;
        this._fontDelta = delta;
        this._applyFonts();
        if (this._data) this.update(this._data);
    }

    _font(base) {
        return `font-size: ${Math.max(1, base + this._fontDelta)}px;`;
    }

    _applyFonts() {
        this._title.set_style(this._font(FONT_BASE.title));
        this._heading.set_style(this._font(FONT_BASE.heading));
        for (const label of Object.values(this._keyText))
            label.set_style(this._font(FONT_BASE.key));
        for (const label of Object.values(this._capText))
            label.set_style(this._font(FONT_BASE.cap));
    }

    update(data) {
        this._data = data;
        const profiles = data.profiles ?? [];
        const active = profiles[data.active_index];

        this._title.text = active ? active.name.toUpperCase() : 'NO PROFILES';
        const bindings = active?.bindings ?? {};
        const labels = active?.labels ?? {};

        for (const slot of BUTTONS) {
            const label = labels[slot] ?? '';
            const binding = bindings[slot] ?? '';
            this._keyText[slot].text = label || binding || '—';
            // Avoid printing the binding twice when there is no label.
            this._capText[slot].text = label ? binding : '';
        }
        const knobLabel = KNOB_SLOTS.map(s => labels[s] ?? '').find(v => v) ?? '';
        this._keyText.knob.text = knobLabel || bindings.knob_cw || '—';

        this._list.destroy_all_children();
        profiles.forEach((profile, index) => {
            const isActive = index === data.active_index;
            const row = new St.Button({style_class: 'macropad-item'});
            const box = new St.BoxLayout();
            const name = new St.Label({
                style_class: isActive ? 'macropad-item-active' : 'macropad-item-name',
                text: profile.name,
                y_align: Clutter.ActorAlign.CENTER,
            });
            name.set_style(this._font(FONT_BASE.item));
            box.add_child(name);
            const dot = new St.Label({
                style_class: 'macropad-dot',
                text: isActive ? '●' : '',
                x_expand: true,
                x_align: Clutter.ActorAlign.END,
                y_align: Clutter.ActorAlign.CENTER,
            });
            dot.set_style(this._font(FONT_BASE.item));
            box.add_child(dot);
            row.set_child(box);
            row.connect('clicked', () =>
                spawn([commandPath('macropad-cycle'), '--set', profile.file]));
            this._list.add_child(row);
        });
    }
}

export default class MacropadHudExtension extends Extension {
    enable() {
        log(`macropad-hud: enable() version ${HUD_VERSION}`);
        this._hud = new Hud();
        this._stacking = null;
        this._applyConfig();

        this._sizeId = this._hud.actor.connect('notify::height', () => this._reposition());
        this._monitorsId = Main.layoutManager.connect('monitors-changed',
            () => this._reposition());
        this._workAreasId = global.display.connect('workareas-changed',
            () => this._reposition());
        this._reposition();

        this._monitors = [];
        this._watch(STATE_FILE, false);
        this._watch(PROFILES_DIR, true);
        this._watch(HUD_CONFIG, false);
        this._refresh();
    }

    disable() {
        if (this._sizeId) this._hud?.actor.disconnect(this._sizeId);
        if (this._monitorsId) Main.layoutManager.disconnect(this._monitorsId);
        if (this._workAreasId) global.display.disconnect(this._workAreasId);
        if (this._debounceId) GLib.Source.remove(this._debounceId);
        this._debounceId = null;

        for (const monitor of this._monitors ?? []) monitor.cancel();
        this._monitors = [];

        if (this._stacking === 'top' && this._hud)
            Main.layoutManager.removeChrome(this._hud.actor);
        this._stacking = null;
        this._hud?.actor.destroy();
        this._hud = null;
    }

    _readConfig() {
        try {
            const [ok, bytes] = GLib.file_get_contents(HUD_CONFIG);
            if (ok) {
                const cfg = JSON.parse(new TextDecoder().decode(bytes));
                return {
                    stacking: cfg.stacking === 'desktop' || cfg.stacking === 'top'
                        ? cfg.stacking : DEFAULT_STACKING,
                    fontDelta: Number.isFinite(cfg.font_delta)
                        ? cfg.font_delta : DEFAULT_FONT_DELTA,
                };
            }
        } catch (e) {
            // No config file yet, or unreadable - fall through to defaults.
        }
        return {stacking: DEFAULT_STACKING, fontDelta: DEFAULT_FONT_DELTA};
    }

    _applyConfig() {
        const cfg = this._readConfig();
        this._hud?.setFontDelta(cfg.fontDelta);
        this._applyStacking(cfg.stacking);
    }

    /** Move the HUD between the chrome layer and the desktop layer in place. */
    _applyStacking(mode) {
        if (!this._hud || mode === this._stacking) return;
        const actor = this._hud.actor;

        if (this._stacking === 'top') Main.layoutManager.removeChrome(actor);
        else if (this._stacking) actor.get_parent()?.remove_child(actor);

        if (mode === 'top') {
            Main.layoutManager.addChrome(actor, {trackFullscreen: true});
        } else {
            Main.layoutManager.uiGroup.add_child(actor);
            Main.layoutManager.uiGroup.set_child_below_sibling(actor, global.window_group);
        }
        this._stacking = mode;
        this._reposition();
    }

    _watch(path, isDirectory) {
        try {
            const file = Gio.File.new_for_path(path);
            const monitor = isDirectory
                ? file.monitor_directory(Gio.FileMonitorFlags.NONE, null)
                : file.monitor_file(Gio.FileMonitorFlags.NONE, null);
            monitor.connect('changed', () => this._debouncedRefresh());
            this._monitors.push(monitor);
        } catch (e) {
            logError(e, `macropad-hud: cannot watch ${path}`);
        }
    }

    /** Saving a profile fires several events; coalesce them into one refresh. */
    _debouncedRefresh() {
        if (this._debounceId) GLib.Source.remove(this._debounceId);
        this._debounceId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            this._debounceId = null;
            this._applyConfig();
            this._refresh();
            return GLib.SOURCE_REMOVE;
        });
    }

    /** YAML lives in Python's world; ask macropad-status for parsed JSON. */
    _refresh() {
        let proc;
        try {
            proc = new Gio.Subprocess({
                argv: [commandPath('macropad-status')],
                flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
            });
            proc.init(null);
        } catch (e) {
            logError(e, 'macropad-hud: cannot run macropad-status');
            return;
        }
        proc.communicate_utf8_async(null, null, (source, result) => {
            try {
                const [, stdout] = source.communicate_utf8_finish(result);
                if (this._hud && stdout) {
                    this._hud.update(JSON.parse(stdout));
                    this._reposition();
                }
            } catch (e) {
                logError(e, 'macropad-hud: bad status output');
            }
        });
    }

    _reposition() {
        if (!this._hud) return;
        const index = Main.layoutManager.primaryIndex;
        const area = Main.layoutManager.getWorkAreaForMonitor(index);
        if (!area) return;
        this._hud.actor.set_position(
            area.x + MARGIN,
            area.y + area.height - this._hud.actor.height - MARGIN);
    }
}
