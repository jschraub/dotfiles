"""Report lock-screen reader policy; release scanning before logind completes sleep."""
import json
import os
import signal
import sys
import time

import gi
gi.require_version('Gio', '2.0')
gi.require_version('GLibUnix', '2.0')
from gi.repository import Gio, GLib, GLibUnix

from fingerprint_state import availability
from fingerprint_environment import lid_closed, policy


class FingerprintMonitor:
    def __init__(self, greeter=False):
        self.greeter = greeter
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.manager = Gio.DBusProxy.new_sync(self.bus, Gio.DBusProxyFlags.NONE, None,
                                              'org.freedesktop.login1', '/org/freedesktop/login1',
                                              'org.freedesktop.login1.Manager', None)
        preparing = self.manager.get_cached_property('PreparingForSleep')
        self.sleeping = preparing is None or preparing.unpack()
        self.resume_until = 0
        self.inhibitor = None
        self.release_source = None
        self.reader = False
        self.present = False
        self.ready = False
        self.seen_reader = False
        self.querying = False
        self.next_probe = 0
        self.last = None
        self.bus.signal_subscribe('org.freedesktop.login1', 'org.freedesktop.login1.Manager',
                                  'PrepareForSleep', '/org/freedesktop/login1', None,
                                  Gio.DBusSignalFlags.NONE, self.prepare)

    def mode(self):
        return 'auto' if self.greeter else policy()

    def publish(self):
        state = availability(mode=self.mode(), closed=lid_closed(), sleeping=self.sleeping,
                             resuming=time.monotonic() < self.resume_until,
                             inhibited=self.inhibitor is not None, reader=self.reader,
                             seen_reader=self.seen_reader)
        value = {'allowed': state.allowed, 'message': state.message,
                 'present': self.present, 'ready': self.ready}
        if value != self.last:
            print(json.dumps(value), flush=True)
            self.last = value

    def release(self):
        if self.inhibitor is not None:
            os.close(self.inhibitor)
            self.inhibitor = None
        self.release_source = None
        return GLib.SOURCE_REMOVE

    def prepare(self, connection, sender, path, interface, member, parameters):
        self.sleeping = parameters.unpack()[0]
        self.reader = False
        if self.release_source is not None:
            GLib.source_remove(self.release_source)
            self.release_source = None
        if self.sleeping:
            # Publish first: the UI aborts only fingerprint PAM. Its password
            # conversation and typed text stay intact. Give device release time
            # under a delay inhibitor, rather than starting fprintd during sleep.
            self.publish()
            self.release_source = GLib.timeout_add(750, self.release)
        else:
            self.release()
            self.resume_until = time.monotonic() + 1.5
            self.next_probe = self.resume_until
            self.publish()

    def inhibit(self):
        if self.inhibitor is not None:
            return True
        try:
            result, descriptors = self.bus.call_with_unix_fd_list_sync(
                'org.freedesktop.login1', '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager', 'Inhibit',
                GLib.Variant('(ssss)', ('sleep', 'Atelier fingerprint', 'Release fingerprint verification', 'delay')),
                GLib.VariantType.new('(h)'), Gio.DBusCallFlags.NONE, 1500, None, None)
            self.inhibitor = descriptors.get(result.unpack()[0])
            os.set_inheritable(self.inhibitor, False)
            return True
        except GLib.Error:
            # logind can already be preparing sleep. Do not start fprintd then.
            return False

    def probed(self, connection, result):
        self.querying = False
        try:
            readers = connection.call_finish(result).unpack()[0]
            self.present = bool(readers)
            # A query begun before PrepareForSleep must not re-enable scanning.
            if not self.sleeping and time.monotonic() >= self.resume_until:
                self.reader = bool(readers)
                self.seen_reader = self.seen_reader or self.reader
        except GLib.Error:
            self.reader = False
            self.present = False
        self.ready = True
        self.publish()

    def tick(self):
        now = time.monotonic()
        permitted = self.mode() != 'off' and not self.sleeping and now >= self.resume_until
        if not permitted:
            self.reader = False
            self.ready = True
            if not self.sleeping:
                self.release()
        elif now >= self.next_probe and not self.querying:
            self.next_probe = now + 3
            if self.inhibit():
                self.querying = True
                self.bus.call('net.reactivated.Fprint', '/net/reactivated/Fprint/Manager',
                              'net.reactivated.Fprint.Manager', 'GetDevices', None,
                              GLib.VariantType.new('(ao)'), Gio.DBusCallFlags.NONE,
                              1500, None, self.probed)
            else:
                self.ready = True
        self.publish()
        return GLib.SOURCE_CONTINUE


def main():
    loop = GLib.MainLoop()
    monitor = FingerprintMonitor(greeter=sys.argv[1:] == ['--greeter'])
    monitor.tick()
    GLib.timeout_add(500, monitor.tick)
    for number in (signal.SIGTERM, signal.SIGINT):
        GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, number, lambda: (loop.quit(), GLib.SOURCE_REMOVE)[1])
    try:
        loop.run()
    finally:
        monitor.release()


if __name__ == '__main__':
    try:
        main()
    except (GLib.Error, OSError):
        print(json.dumps({'allowed': False, 'present': False, 'ready': True,
                          'message': 'Fingerprint unavailable — enter your password'}), flush=True)
