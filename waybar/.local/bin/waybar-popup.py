#!/usr/bin/env python3
"""Click-open Waybar calendar/audio panels; Escape or outside-click dismisses.

Requires GTK3, PyGObject, gtk-layer-shell, and wpctl (WirePlumber).
No GUI/dependency imports occur until main, so model tests work headlessly.
"""
import argparse
import calendar
from datetime import date
import json
import locale
import os
from pathlib import Path
import re
import subprocess
import sys


SINK = '@DEFAULT_AUDIO_SINK@'
WIDTH = 360


def month_shift(year, month, delta):
    index = max(12, min(9999 * 12 + 11, year * 12 + month - 1 + delta))
    year, month = divmod(index, 12)
    return year, month + 1


def month_days(year, month):
    """Six stable calendar rows, including neighboring months."""
    first = date(year, month, 1)
    start = first.toordinal() - first.weekday()
    return [date.fromordinal(start + i) if 1 <= start + i <= date.max.toordinal() else None
            for i in range(42)]


def inside_card(widget, card):
    while widget:
        if widget == card:
            return True
        widget = widget.get_parent()
    return False


class AudioError(Exception):
    pass


class Audio:
    def command(self, *arguments):
        try:
            return subprocess.run(['wpctl', *arguments], check=True, capture_output=True,
                                  text=True, timeout=0.5).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise AudioError('Audio unavailable. Check PipeWire/WirePlumber.') from exc

    def read(self):
        match = re.fullmatch(r'Volume:\s+(\d+(?:\.\d+)?)\s*(\[MUTED\])?', self.command('get-volume', SINK))
        if not match:
            raise AudioError('Could not read the default output volume.')
        return float(match[1]) * 100, bool(match[2])

    def set_volume(self, percent):
        value = max(0, min(100, percent)) / 100
        self.command('set-volume', '-l', '1.0', SINK, f'{value:.3f}')

    def toggle_mute(self):
        self.command('set-mute', SINK, 'toggle')


def cursor_position():
    """Use the clicked Hyprland output, not a hard-coded primary monitor."""
    try:
        def query(name):
            return json.loads(subprocess.run(['hyprctl', '-j', name], check=True,
                                            capture_output=True, text=True, timeout=0.5).stdout)
        cursor = query('cursorpos')
        monitors = query('monitors')
        def contains(monitor):
            width, height = monitor['width'], monitor['height']
            if monitor.get('transform', 0) % 2:
                width, height = height, width
            scale = monitor.get('scale', 1)
            return (monitor['x'] <= cursor['x'] < monitor['x'] + width / scale and
                    monitor['y'] <= cursor['y'] < monitor['y'] + height / scale)

        top = next((m.get('reserved', [0, 40, 0, 0])[1] for m in monitors if contains(m)), 40)
        return int(cursor['x']), int(cursor['y']), max(40, int(top)) + 10
    except (OSError, ValueError, KeyError, IndexError, TypeError, subprocess.SubprocessError):
        return None


def run_popup(kind, smoke_test=None):
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Gdk', '3.0')
    gi.require_version('GtkLayerShell', '0.1')
    from gi.repository import Gdk, Gio, GLib, Gtk, GtkLayerShell

    ready, _ = Gtk.init_check([])
    if not ready:
        raise RuntimeError('No graphical display is available.')
    if not GtkLayerShell.is_supported():
        raise RuntimeError('Waybar popups require a Wayland compositor with layer-shell support.')

    def style(widget, name):
        widget.get_style_context().add_class(name)
        return widget

    def label(text, name=None):
        widget = Gtk.Label(label=text, xalign=0)
        return style(widget, name) if name else widget

    def configure_layer(window, keyboard):
        window.set_name('waybar-popup')
        window.set_decorated(False)
        window.set_app_paintable(True)
        visual = window.get_screen().get_rgba_visual()
        if visual:
            window.set_visual(visual)
        GtkLayerShell.init_for_window(window)
        GtkLayerShell.set_namespace(window, 'waybar-popup')
        GtkLayerShell.set_layer(window, GtkLayerShell.Layer.OVERLAY)
        GtkLayerShell.set_keyboard_mode(window, keyboard)
        GtkLayerShell.set_exclusive_zone(window, 0)
        for edge in [GtkLayerShell.Edge.TOP, GtkLayerShell.Edge.BOTTOM,
                     GtkLayerShell.Edge.LEFT, GtkLayerShell.Edge.RIGHT]:
            GtkLayerShell.set_anchor(window, edge, True)

    class Panel(Gtk.ApplicationWindow):
        def __init__(self, app, kind):
            super().__init__(application=app)
            self.kind = kind
            self.sources = set()
            self.backdrops = []
            self.set_title('Waybar ' + kind)
            configure_layer(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)

            display = self.get_display()
            position = cursor_position()
            if position:
                x, y, top = position
            else:
                _, x, y = display.get_default_seat().get_pointer().get_position()
                top = 50
            monitor = display.get_monitor_at_point(x, y) or display.get_primary_monitor() or display.get_monitor(0)
            GtkLayerShell.set_monitor(self, monitor)
            geometry = monitor.get_geometry()
            left = max(12, min(x - geometry.x - WIDTH // 2, geometry.width - WIDTH - 12))

            # The transparent full-output backdrop owns outside clicks. A real
            # EventBox around the card ensures blank areas inside it stay open.
            backdrop = Gtk.EventBox()
            backdrop.set_visible_window(False)
            self.add(backdrop)
            self.card = Gtk.EventBox()
            self.card.set_name('popup-panel')
            self.card.set_halign(Gtk.Align.START)
            self.card.set_valign(Gtk.Align.START)
            self.card.set_margin_start(left)
            self.card.set_margin_top(top)
            self.card.set_size_request(WIDTH, -1)
            backdrop.add(self.card)
            body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
            body.set_name('popup-body')
            self.card.add(body)
            self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
            self.connect('button-press-event', self.outside_click)
            self.connect('key-press-event', self.key_press)
            self.connect('destroy', self.cleanup)
            # A transparent dismiss surface on other outputs makes clicking
            # away work across monitors too, without stealing keyboard focus.
            for index in range(display.get_n_monitors()):
                other = display.get_monitor(index)
                if other == monitor:
                    continue
                curtain = Gtk.ApplicationWindow(application=app)
                configure_layer(curtain, GtkLayerShell.KeyboardMode.NONE)
                GtkLayerShell.set_monitor(curtain, other)
                dismiss_area = Gtk.EventBox()
                dismiss_area.set_visible_window(False)
                curtain.add(dismiss_area)
                curtain.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
                curtain.connect('button-press-event', lambda *_: self.destroy() or True)
                curtain.show_all()
                self.backdrops.append(curtain)
            if kind == 'calendar':
                self.calendar(body)
            else:
                self.audio(body)
            body.pack_start(label('Esc or click outside to close', 'popup-hint'), False, False, 0)

        def key_press(self, widget, event):
            if event.keyval == Gdk.KEY_Escape:
                self.destroy()
                return True
            return False

        def outside_click(self, widget, event):
            if inside_card(Gtk.get_event_widget(event), self.card):
                return False
            self.destroy()
            return True

        def cleanup(self, *_):
            for backdrop in self.backdrops:
                backdrop.destroy()
            self.backdrops.clear()
            for source in self.sources:
                GLib.source_remove(source)
            self.sources.clear()

        def later(self, delay, callback, repeat=False):
            source = None

            def run():
                if not repeat:
                    self.sources.discard(source)
                callback()
                return repeat

            source = GLib.timeout_add(delay, run)
            self.sources.add(source)
            return source

        def cancel(self, source):
            if source in self.sources:
                GLib.source_remove(source)
                self.sources.remove(source)

        def calendar(self, body):
            today = date.today()
            selected = today
            year, month = today.year, today.month
            body.pack_start(label(today.strftime('%A, %B %-d'), 'popup-subtitle'), False, False, 0)
            header = Gtk.Box(spacing=8)
            heading = label('', 'popup-title')
            previous = Gtk.Button(label='‹')
            previous.set_tooltip_text('Previous month')
            following = Gtk.Button(label='›')
            following.set_tooltip_text('Next month')
            header.pack_start(heading, True, True, 0)
            header.pack_start(previous, False, False, 0)
            header.pack_start(following, False, False, 0)
            body.pack_start(header, False, False, 0)
            grid = Gtk.Grid(column_spacing=4, row_spacing=4, column_homogeneous=True)
            body.pack_start(grid, False, False, 0)
            footer = Gtk.Box(spacing=8)
            selection = label('', 'popup-subtitle')
            reset = Gtk.Button(label='Today')
            footer.pack_start(selection, True, True, 0)
            footer.pack_end(reset, False, False, 0)
            body.pack_start(footer, False, False, 0)

            def pick(button, day):
                nonlocal selected
                selected = day
                render()

            def render():
                for child in grid.get_children():
                    child.destroy()
                heading.set_text(date(year, month, 1).strftime('%B %Y'))
                selection.set_text(selected.strftime('%b %-d, %Y'))
                for col, day in enumerate(calendar.day_abbr):
                    grid.attach(style(Gtk.Label(label=day[:2]), 'calendar-weekday'), col, 0, 1, 1)
                for index, day in enumerate(month_days(year, month)):
                    button = style(Gtk.Button(label=str(day.day) if day else ''), 'calendar-day')
                    if day is None:
                        button.set_sensitive(False)
                        grid.attach(button, index % 7, index // 7 + 1, 1, 1)
                        continue
                    button.set_tooltip_text(day.strftime('%A, %B %-d, %Y'))
                    for enabled, name in [(day.month != month, 'other-month'),
                                          (day == today, 'today'), (day == selected, 'selected')]:
                        if enabled:
                            style(button, name)
                    button.connect('clicked', pick, day)
                    grid.attach(button, index % 7, index // 7 + 1, 1, 1)
                grid.show_all()

            def move(button, delta):
                nonlocal year, month
                year, month = month_shift(year, month, delta)
                render()

            def reset_today(button):
                nonlocal selected, year, month
                selected = date.today()
                year, month = selected.year, selected.month
                render()

            previous.connect('clicked', move, -1)
            following.connect('clicked', move, 1)
            reset.connect('clicked', reset_today)
            render()

        def audio(self, body):
            audio = Audio()
            self.pending_volume = None
            self.syncing = False
            self.dragging = False
            header = Gtk.Box(spacing=12)
            header.pack_start(label('Volume', 'popup-title'), True, True, 0)
            value = style(Gtk.Label(label='—'), 'volume-value')
            header.pack_end(value, False, False, 0)
            body.pack_start(header, False, False, 0)
            body.pack_start(label('Default output · 0–100%', 'popup-subtitle'), False, False, 0)
            slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
            slider.set_draw_value(False)
            slider.set_can_focus(True)
            slider.get_accessible().set_name('Output volume')
            body.pack_start(slider, False, False, 0)
            error = label('', 'popup-error')
            error.set_line_wrap(True)
            error.set_no_show_all(True)
            body.pack_start(error, False, False, 0)
            buttons = Gtk.Box(spacing=8, homogeneous=True)
            mute = Gtk.Button(label='Mute')
            settings = Gtk.Button(label='Audio settings…')
            settings.set_tooltip_text('Open pavucontrol for devices, inputs, and per-app volume')
            buttons.pack_start(mute, True, True, 0)
            buttons.pack_start(settings, True, True, 0)
            body.pack_start(buttons, False, False, 0)

            def refresh():
                if self.pending_volume is not None or self.dragging:
                    return
                try:
                    percent, muted = audio.read()
                    self.syncing = True
                    slider.set_value(min(100, percent))
                    self.syncing = False
                    value.set_text('Muted' if muted else f'{percent:.0f}%')
                    mute.set_label('Unmute' if muted else 'Mute')
                    slider.set_sensitive(True)
                    mute.set_sensitive(True)
                    error.hide()
                except AudioError as exc:
                    error.set_text(str(exc))
                    error.show()
                    slider.set_sensitive(False)
                    mute.set_sensitive(False)

            def apply_volume():
                self.pending_volume = None
                try:
                    audio.set_volume(slider.get_value())
                except AudioError as exc:
                    error.set_text(str(exc))
                    error.show()

            def changed(scale):
                if not self.syncing:
                    value.set_text(f'{scale.get_value():.0f}%')
                    self.cancel(self.pending_volume)
                    self.pending_volume = self.later(100, apply_volume)

            def dragging(widget, event, active):
                self.dragging = active
                return False

            def toggle(button):
                try:
                    audio.toggle_mute()
                    refresh()
                except AudioError as exc:
                    error.set_text(str(exc))
                    error.show()

            def open_settings(button):
                try:
                    subprocess.Popen(['pavucontrol'], start_new_session=True,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.destroy()
                except OSError:
                    error.set_text('pavucontrol is not installed.')
                    error.show()

            slider.connect('value-changed', changed)
            slider.connect('button-press-event', dragging, True)
            slider.connect('button-release-event', dragging, False)
            mute.connect('clicked', toggle)
            settings.connect('clicked', open_settings)
            refresh()
            self.later(700, refresh, repeat=True)

    suffix = f'.SmokeP{os.getpid()}' if smoke_test else ''
    app = Gtk.Application(application_id='io.github.jschraub.WaybarPopup' + suffix,
                          flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
    current = None
    smoke_failures = []

    def command_line(app, command):
        nonlocal current
        requested = command.get_arguments()[1]
        if current is not None and current.kind == requested:
            current.destroy()
            current = None
            return 0
        old = current
        current = Panel(app, requested)
        if old:
            old.destroy()
        current.show_all()
        current.present()
        if smoke_test:
            def dismiss():
                # Exercise real GDK event ancestry: clicking the card must not
                # dismiss; Escape or the transparent backdrop must dismiss ALL
                # windows and cancel the audio timer. No audio writes occur.
                event = Gdk.Event.new(Gdk.EventType.BUTTON_PRESS)
                event.window = current.card.get_window()
                current.emit('button-press-event', event)
                if not current.get_visible():
                    smoke_failures.append('Clicking inside the card closed it')
                if smoke_test == 'outside':
                    event.window = current.get_window()
                    current.emit('button-press-event', event)
                else:
                    event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
                    event.keyval = Gdk.KEY_Escape
                    current.emit('key-press-event', event)
                if app.get_windows() or current.sources:
                    smoke_failures.append('Dismissal did not clean up windows/timers')
                    for window in app.get_windows():
                        window.destroy()
                return False
            GLib.timeout_add(300, dismiss)
        return 0

    css = Gtk.CssProvider()
    try:
        css.load_from_path(str(Path.home() / '.config/waybar/popup.css'))
    except GLib.Error as exc:
        raise RuntimeError('Cannot load popup.css; restow the waybar package first.') from exc
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    app.connect('command-line', command_line)
    result = app.run([sys.argv[0], kind])
    if smoke_failures:
        raise RuntimeError('; '.join(smoke_failures))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['calendar', 'audio'])
    parser.add_argument('--smoke-test', nargs='?', const='escape', choices=['escape', 'outside'],
                        help='briefly test inside-click and dismissal in an isolated app instance')
    args = parser.parse_args()
    try:
        locale.setlocale(locale.LC_TIME, '')
        return run_popup(args.kind, args.smoke_test)
    except (ImportError, ValueError, RuntimeError) as exc:
        print(f'Waybar popup: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
