"""Hardware-independent fingerprint availability and suspend cancellation policy."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'quickshell/.config/quickshell/atelier'))
from fingerprint_environment import lid_closed, policy
from fingerprint_state import availability
try:
    import fingerprint_monitor
except ImportError:
    fingerprint_monitor = None
sys.path.pop(0)


class FingerprintPolicyTest(unittest.TestCase):
    def state(self, **changes):
        values = dict(mode='auto', closed=False, sleeping=False, resuming=False,
                      inhibited=True, reader=True, seen_reader=True)
        values.update(changes)
        return availability(**values)

    def test_only_an_awake_open_lid_reader_with_sleep_coordination_can_scan(self):
        self.assertTrue(self.state().allowed)
        for changes in ({'mode': 'off'}, {'mode': 'invalid'}, {'closed': True}, {'sleeping': True},
                        {'resuming': True}, {'inhibited': False}, {'reader': False}):
            with self.subTest(changes=changes):
                self.assertFalse(self.state(**changes).allowed)

    def test_readerless_machine_has_no_fingerprint_advertisement(self):
        state = self.state(reader=False, seen_reader=False)
        self.assertFalse(state.allowed)
        self.assertEqual(state.message, '')

    def test_real_lid_state_and_desktop_without_lid(self):
        with tempfile.TemporaryDirectory() as directory:
            lid = Path(directory)
            self.assertFalse(lid_closed(lid), 'A desktop without a lid is not assumed docked')
            device = lid / 'LID0'
            device.mkdir()
            state = device / 'state'
            state.write_text('state: open\n')
            self.assertFalse(lid_closed(lid))
            state.write_text('state: closed\n')
            self.assertTrue(lid_closed(lid))
            with patch.object(Path, 'read_text', side_effect=PermissionError):
                self.assertTrue(lid_closed(lid), 'Unreadable lid state cannot enable scanning')

    def test_shared_policy_overrides_and_password_test(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            self.assertEqual(policy({}, home), 'auto')
            target = home / '.config/dotfiles'
            target.mkdir(parents=True)
            (target / 'hyprlock-fingerprint').write_text('off\n')
            self.assertEqual(policy({}, home), 'off')
            self.assertEqual(policy({'HYPRLOCK_FINGERPRINT': 'on'}, home), 'on')
            self.assertEqual(policy({'HYPRLOCK_FINGERPRINT': 'unexpected'}, home), 'off')
            self.assertEqual(policy({'ATELIER_FINGERPRINT': '0', 'HYPRLOCK_FINGERPRINT': 'on'}, home), 'off')


@unittest.skipIf(fingerprint_monitor is None, 'requires python-gobject, no hardware is used')
class FingerprintLifecycleTest(unittest.TestCase):
    def monitor(self):
        # Construct only the state machine; never attach to the real system bus.
        monitor = object.__new__(fingerprint_monitor.FingerprintMonitor)
        monitor.bus = Mock()
        monitor.greeter = False
        monitor.sleeping = False
        monitor.resume_until = 0
        monitor.inhibitor = 123
        monitor.release_source = None
        monitor.sleep_generation = 0
        monitor.awaiting_generation = 0
        monitor.input_buffer = b''
        monitor.reader = True
        monitor.present = True
        monitor.ready = True
        monitor.seen_reader = True
        monitor.querying = False
        monitor.next_probe = 0
        monitor.last = None
        return monitor

    def test_sleep_disables_scanning_before_releasing_delay_inhibitor(self):
        monitor = self.monitor()
        output = io.StringIO()
        with patch.object(fingerprint_monitor, 'policy', return_value='auto'), \
                patch.object(fingerprint_monitor, 'lid_closed', return_value=False), \
                patch.object(fingerprint_monitor.os, 'close') as close, \
                patch.object(fingerprint_monitor.GLib, 'timeout_add', return_value=42) as timer, \
                redirect_stdout(output):
            monitor.prepare(None, None, None, None, None, fingerprint_monitor.GLib.Variant('(b)', (True,)))
            self.assertFalse(json.loads(output.getvalue())['allowed'])
            close.assert_not_called()
            self.assertEqual(monitor.inhibitor, 123)
            self.assertEqual(timer.call_args.args[0], fingerprint_monitor.CANCELLATION_TIMEOUT_MS)
            self.assertEqual(json.loads(output.getvalue())['sleepGeneration'], 1)
            self.assertTrue(json.loads(output.getvalue())['sleeping'])
            timer.call_args.args[1]()
            close.assert_called_once_with(123)
            self.assertIsNone(monitor.inhibitor)
            self.assertEqual(monitor.awaiting_generation, 0)

    def test_current_acknowledgement_releases_inhibitor_and_cancels_timeout(self):
        monitor = self.monitor()
        monitor.sleeping = True
        monitor.awaiting_generation = 2
        monitor.release_source = 42
        with patch.object(fingerprint_monitor.os, 'close') as close, \
                patch.object(fingerprint_monitor.GLib, 'source_remove') as remove:
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 2})
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 2})
        close.assert_called_once_with(123)
        remove.assert_called_once_with(42)
        self.assertEqual(monitor.awaiting_generation, 0)

    def test_stale_malformed_and_wrong_generation_acknowledgements_do_not_release(self):
        monitor = self.monitor()
        monitor.sleeping = True
        monitor.awaiting_generation = 2
        for value in (None, [], {}, {'type': 'fingerprint-stopped', 'generation': 1},
                      {'type': 'fingerprint-stopped', 'generation': True},
                      {'type': 'fingerprint-stopped', 'generation': '2'},
                      {'type': 'anything', 'generation': 2}):
            with self.subTest(value=value), patch.object(fingerprint_monitor.os, 'close') as close:
                monitor.acknowledge(value)
                close.assert_not_called()
        self.assertEqual(monitor.inhibitor, 123)

    def test_late_sleep_acknowledgement_cannot_release_new_awake_inhibitor(self):
        monitor = self.monitor()
        monitor.awaiting_generation = 2
        with patch.object(fingerprint_monitor.os, 'close') as close:
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 2})
        close.assert_not_called()

    def test_previous_sleep_acknowledgement_cannot_release_next_sleep_inhibitor(self):
        monitor = self.monitor()
        with patch.object(monitor, 'publish'), \
                patch.object(fingerprint_monitor.GLib, 'timeout_add', return_value=42), \
                patch.object(fingerprint_monitor.GLib, 'source_remove'), \
                patch.object(fingerprint_monitor.os, 'close') as close:
            monitor.prepare(None, None, None, None, None, fingerprint_monitor.GLib.Variant('(b)', (True,)))
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 1})
            self.assertEqual(close.call_count, 1)
            monitor.prepare(None, None, None, None, None, fingerprint_monitor.GLib.Variant('(b)', (False,)))
            monitor.inhibitor = 456
            monitor.prepare(None, None, None, None, None, fingerprint_monitor.GLib.Variant('(b)', (True,)))
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 1})
            self.assertEqual(close.call_count, 1)
            self.assertEqual(monitor.awaiting_generation, 2)
            monitor.acknowledge({'type': 'fingerprint-stopped', 'generation': 2})
            self.assertEqual(close.call_args.args, (456,))

    def test_private_ack_input_handles_partial_lines_and_ignores_invalid_json(self):
        monitor = self.monitor()
        with patch.object(fingerprint_monitor.os, 'read', side_effect=[
                b'not-json\n{"type":"fingerprint-', b'stopped","generation":1}\n']), \
                patch.object(monitor, 'acknowledge') as ack:
            monitor.read_ack(None, None)
            ack.assert_not_called()
            monitor.read_ack(None, None)
        ack.assert_called_once_with({'type': 'fingerprint-stopped', 'generation': 1})

    def test_disconnected_ack_pipe_leaves_timeout_in_place(self):
        monitor = self.monitor()
        monitor.release_source = 42
        with patch.object(fingerprint_monitor.os, 'read', return_value=b''), \
                patch.object(fingerprint_monitor.os, 'close') as close:
            self.assertEqual(monitor.read_ack(None, None), fingerprint_monitor.GLib.SOURCE_REMOVE)
        close.assert_not_called()
        self.assertEqual(monitor.release_source, 42)

    def test_wake_waits_for_hardware_before_reprobing(self):
        monitor = self.monitor()
        monitor.inhibitor = None
        with patch.object(monitor, 'publish'), patch.object(monitor, 'inhibit', return_value=True), \
                patch.object(fingerprint_monitor, 'policy', return_value='auto'), \
                patch.object(fingerprint_monitor, 'lid_closed', return_value=False), \
                patch.object(fingerprint_monitor.time, 'monotonic', return_value=100):
            monitor.prepare(None, None, None, None, None, fingerprint_monitor.GLib.Variant('(b)', (False,)))
            monitor.tick()
            monitor.bus.call.assert_not_called()
            self.assertEqual(monitor.resume_until, 101.5)
            with patch.object(fingerprint_monitor.time, 'monotonic', return_value=102):
                monitor.tick()
            monitor.bus.call.assert_called_once()

    def test_old_device_reply_cannot_enable_scanning_during_sleep(self):
        monitor = self.monitor()
        monitor.sleeping = True
        monitor.reader = False
        monitor.bus.call_finish.return_value = fingerprint_monitor.GLib.Variant('(ao)', (['/net/reactivated/Fprint/Device/0'],))
        with patch.object(monitor, 'publish'):
            monitor.probed(monitor.bus, Mock())
        self.assertFalse(monitor.reader)
