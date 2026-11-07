"""PRIVATE-bus MPRIS + StatusNotifier + DBusMenu fixture. Never use the real bus."""
import json
import os
import gi
gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib

assert os.environ.get('ATELIER_PRIVATE_BUS_FIXTURE') == '1'
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
V = GLib.Variant
state = {'playing': False, 'events': [], 'activated': 0}
properties = {
    'org.mpris.MediaPlayer2': {'Identity': V('s', 'Atelier fixture'), 'CanQuit': V('b', False), 'CanRaise': V('b', False), 'HasTrackList': V('b', False)},
    'org.mpris.MediaPlayer2.Player': {
        'PlaybackStatus': V('s', 'Paused'), 'Metadata': V('a{sv}', {'xesam:title': V('s', 'Fixture track'), 'xesam:artist': V('as', ['Fixture artist'])}),
        'CanControl': V('b', True), 'CanPlay': V('b', True), 'CanPause': V('b', True), 'CanSeek': V('b', False),
        'CanGoNext': V('b', False), 'CanGoPrevious': V('b', False), 'Position': V('x', 0),
        'Volume': V('d', 1.0), 'Rate': V('d', 1.0), 'MinimumRate': V('d', 1.0), 'MaximumRate': V('d', 1.0),
        'LoopStatus': V('s', 'None'), 'Shuffle': V('b', False),
    },
    'org.kde.StatusNotifierItem': {
        'Id': V('s', 'atelier-fixture'), 'Title': V('s', 'Fixture tray'), 'Category': V('s', 'ApplicationStatus'),
        'Status': V('s', 'Active'), 'IconName': V('s', 'applications-multimedia'),
        'IconPixmap': V('a(iiay)', []), 'AttentionIconName': V('s', ''), 'AttentionIconPixmap': V('a(iiay)', []),
        'OverlayIconName': V('s', ''), 'OverlayIconPixmap': V('a(iiay)', []),
        'ItemIsMenu': V('b', False), 'Menu': V('o', '/Menu'),
        'ToolTip': V('(sa(iiay)ss)', ('applications-multimedia', [], 'Fixture tray', 'Private-bus fixture')),
    },
    'com.canonical.dbusmenu': {'Version': V('u', 4), 'TextDirection': V('s', 'ltr'), 'Status': V('s', 'normal'), 'IconThemePath': V('as', [])},
}


def menu(parent):
    leaf = (3, {'label': V('s', 'Child action'), 'enabled': V('b', True)}, [])
    submenu = (2, {'label': V('s', 'Submenu'), 'enabled': V('b', True), 'children-display': V('s', 'submenu')}, [V('(ia{sv}av)', leaf)])
    root = (0, {}, [V('(ia{sv}av)', (1, {'label': V('s', 'Action'), 'enabled': V('b', True)}, [])), V('(ia{sv}av)', submenu)])
    return {0: root, 1: root[2][0].unpack(), 2: submenu, 3: leaf}.get(parent, root)


def method(connection, sender, path, interface, name, params, call):
    args = params.unpack()
    if interface == 'org.example.AtelierFixture':
        call.return_value(V('(s)', (json.dumps(state),)))
        return
    if name in ('PlayPause', 'Play', 'Pause'):
        state['playing'] = not state['playing'] if name == 'PlayPause' else name == 'Play'
        properties[interface]['PlaybackStatus'] = V('s', 'Playing' if state['playing'] else 'Paused')
        bus.emit_signal(None, path, 'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                        V('(sa{sv}as)', (interface, {'PlaybackStatus': properties[interface]['PlaybackStatus']}, [])))
    elif name == 'Activate':
        state['activated'] += 1
    elif name == 'GetLayout':
        call.return_value(V('(u(ia{sv}av))', (1, menu(args[0])))); return
    elif name == 'GetGroupProperties':
        call.return_value(V('(a(ia{sv}))', ([(i, menu(i)[1]) for i in args[0]],))); return
    elif name == 'AboutToShow':
        call.return_value(V('(b)', (False,))); return
    elif name == 'Event':
        if args[1] == 'clicked': state['events'].append(args[0])
    elif name == 'EventGroup':
        call.return_value(V('(ai)', ([],))); return
    call.return_value(None)


methods = {
    'org.mpris.MediaPlayer2': '<method name="Raise"/><method name="Quit"/>',
    'org.mpris.MediaPlayer2.Player': '<method name="PlayPause"/><method name="Play"/><method name="Pause"/><method name="Next"/><method name="Previous"/>',
    'org.kde.StatusNotifierItem': '<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>',
    'com.canonical.dbusmenu': '''
      <method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/><arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
      <method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/><arg type="a(ia{sv})" direction="out"/></method>
      <method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
      <method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="in"/><arg type="u" direction="in"/></method>
      <method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>''',
}
for interface, props in properties.items():
    declarations = ''.join(f'<property name="{key}" type="{value.get_type_string()}" access="read"/>' for key, value in props.items())
    info = Gio.DBusNodeInfo.new_for_xml(f'<node><interface name="{interface}">{declarations}{methods[interface]}</interface></node>')
    path = '/org/mpris/MediaPlayer2' if interface.startswith('org.mpris') else '/Menu' if interface == 'com.canonical.dbusmenu' else '/StatusNotifierItem'
    bus.register_object(path, info.interfaces[0], method, lambda c, s, p, i, prop: properties[i][prop], None)
control = Gio.DBusNodeInfo.new_for_xml('<node><interface name="org.example.AtelierFixture"><method name="Status"><arg type="s" direction="out"/></method></interface></node>')
bus.register_object('/Test', control.interfaces[0], method, None, None)
for name in ['org.mpris.MediaPlayer2.atelier_fixture', 'org.example.AtelierFixture']:
    Gio.bus_own_name_on_connection(bus, name, Gio.BusNameOwnerFlags.NONE, None, None)
registered = False
pending = False


def register():
    global pending
    if registered: return False
    if pending: return True
    pending = True
    def complete(connection, result):
        global registered, pending
        try: connection.call_finish(result); registered = True
        except GLib.Error: pass
        pending = False
    bus.call('org.kde.StatusNotifierWatcher', '/StatusNotifierWatcher', 'org.kde.StatusNotifierWatcher',
             'RegisterStatusNotifierItem', V('(s)', ('/StatusNotifierItem',)), None, Gio.DBusCallFlags.NONE, 1000, None, complete)
    return True


GLib.timeout_add(100, register)
GLib.MainLoop().run()
