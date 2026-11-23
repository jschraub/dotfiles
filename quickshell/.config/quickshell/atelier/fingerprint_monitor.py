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

CANCELLATION_TIMEOUT_MS = 1500


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
        self.sleep_generation = 0
        self.awaiting_generation = 0
        self.input_buffer = b''
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
                 'present': self.present, 'ready': self.ready,
                 'sleeping': self.sleeping,
                 'sleepGeneration': self.awaiting_generation}
        if value != self.last:
            print(json.dumps(value), flush=True)
            self.last = value

    def release(self):
        if self.release_source is not None:
            GLib.source_remove(self.release_source)
            self.release_source = None
        self.awaiting_generation = 0
        if self.inhibitor is not None:
            os.close(self.inhibitor)
            self.inhibitor = None
        self.release_source = None
        return GLib.SOURCE_REMOVE

    def cancellation_timeout(self):
        self.release_source = None
        return self.release()

    def acknowledge(self, value):
        # Only a private, current-generation cancellation acknowledgement can
        # shorten the wait. It cannot authenticate, enable scanning or unlock.
        if (isinstance(value, dict) and value.get('type') == 'fingerprint-stopped'
                and type(value.get('generation')) is int and self.sleeping
                and self.awaiting_generation != 0
                and value['generation'] == self.awaiting_generation):
            self.release()

    def read_ack(self, source, condition):
        try:
            chunk = os.read(sys.stdin.fileno(), 4096)
        except OSError:
            return GLib.SOURCE_REMOVE
        if not chunk:
            return GLib.SOURCE_REMOVE
        self.input_buffer += chunk
        if len(self.input_buffer) > 4096:
            return GLib.SOURCE_REMOVE  # Malformed input never removes the timeout.
        while b'\n' in self.input_buffer:
            line, self.input_buffer = self.input_buffer.split(b'\n', 1)
            try:
                self.acknowledge(json.loads(line))
            except (ValueError, UnicodeError):
                pass
        return GLib.SOURCE_CONTINUE

    def prepare(self, connection, sender, path, interface, member, parameters):
        self.sleeping = parameters.unpack()[0]
        self.reader = False
        if self.release_source is not None:
            GLib.source_remove(self.release_source)
            self.release_source = None
        if self.sleeping:
            # Publish a fresh token before waiting. Supported authentication
            # APIs acknowledge cancellation; unresponsive/unsupported ones use
            # the bounded timeout. Password entry stays intact.
            self.sleep_generation += 1
            self.awaiting_generation = self.sleep_generation
            self.release_source = GLib.timeout_add(CANCELLATION_TIMEOUT_MS, self.cancellation_timeout)
            self.publish()
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
    GLib.io_add_watch(sys.stdin, GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, monitor.read_ack)
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
