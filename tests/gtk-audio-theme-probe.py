"""Render plain GTK4 audio widgets, without touching any audio devices."""
import json
import sys

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

Gtk.init()
provider = Gtk.CssProvider()
errors = []
provider.connect('parsing-error', lambda p, s, e: errors.append(str(e)))
provider.load_from_path(sys.argv[1])
Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
window = Gtk.Window(default_width=400, default_height=120)
scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
scale.set_value(60)
window.set_child(scale)
loop = GLib.MainLoop()


def finish():
    snapshot = Gtk.Snapshot()
    Gtk.WidgetPaintable.new(window).snapshot(snapshot, window.get_width(), window.get_height())
    node = snapshot.to_node()
    print(json.dumps({'errors': errors, 'render': node.serialize().get_data().decode()}))
    window.destroy()
    loop.quit()
    return False


window.present()
GLib.timeout_add(250, finish)
loop.run()
