"""Real libadwaita tab/toast widgets, without launching or modifying Ghostty."""
import json
from pathlib import Path
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, GLib, Gtk

ROOT = Path(__file__).resolve().parents[1]
Adw.init()
provider = Gtk.CssProvider()
errors = []
provider.connect('parsing-error', lambda p, s, e: errors.append(str(e)))
provider.load_from_path(sys.argv[1])
Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
window = Adw.Window(default_width=600, default_height=240)
window.add_css_class('window')  # GhosttyWindow's real class from its bundled UI.
view = Adw.TabView()
for title in ['First', 'Second']:
    page = view.append(Gtk.Label(label='Theme probe'))
    page.set_title(title)
bar = Adw.TabBar(view=view, autohide=False)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
box.append(bar)
box.append(view)
overlay = Adw.ToastOverlay(child=box)
window.set_content(overlay)
toast = Adw.Toast(title='Theme probe', button_label='Undo', timeout=0)
overlay.add_toast(toast)
loop = GLib.MainLoop()


def walk(widget):
    yield widget
    child = widget.get_first_child()
    while child:
        yield from walk(child)
        child = child.get_next_sibling()


def finish():
    widgets = list(walk(window))
    def hex_color(widget):
        color = widget.get_color()
        return '#%02x%02x%02x' % tuple(round(v * 255) for v in [color.red, color.green, color.blue])
    tabs = [w for w in widgets if w.get_css_name() == 'tab']
    selected = [w for w in tabs if w.get_state_flags() & Gtk.StateFlags.SELECTED]
    buttons = [w for w in widgets if isinstance(w, Gtk.Button) and w.get_label() == 'Undo']
    print(json.dumps({'errors': errors, 'selected': [hex_color(w) for w in selected],
                      'tabLabels': [hex_color(w) for tab in selected for w in walk(tab) if isinstance(w, Gtk.Label)],
                      'toastAction': [hex_color(w) for w in buttons],
                      'toastLabels': [hex_color(w) for b in buttons for w in walk(b) if isinstance(w, Gtk.Label)]}))
    window.destroy()
    loop.quit()
    return False


window.present()
GLib.timeout_add(350, finish)
loop.run()
