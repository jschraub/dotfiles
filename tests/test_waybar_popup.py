"""Popup models/controllers: no graphical session or audio changes needed."""
from datetime import date
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('waybar_popup', ROOT / 'waybar/.local/bin/waybar-popup.py')
popup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(popup)


class CalendarTest(unittest.TestCase):
    def test_month_navigation_crosses_year_boundaries(self):
        self.assertEqual(popup.month_shift(2026, 1, -1), (2025, 12))
        self.assertEqual(popup.month_shift(2026, 12, 1), (2027, 1))
        self.assertEqual(popup.month_shift(1, 1, -1), (1, 1))
        self.assertEqual(popup.month_shift(9999, 12, 1), (9999, 12))

    def test_six_monday_first_rows_and_leap_day(self):
        days = popup.month_days(2024, 2)
        self.assertEqual(len(days), 42)
        self.assertEqual(days[0].weekday(), 0)
        self.assertIn(date(2024, 2, 29), days)
        self.assertLess(days[0].month, 2)
        self.assertGreater(days[-1].month, 2)

    def test_extreme_month_does_not_overflow(self):
        self.assertEqual(len(popup.month_days(9999, 12)), 42)

    def test_clicks_inside_card_are_not_outside_clicks(self):
        card = Mock()
        child = Mock()
        child.get_parent.return_value = card
        outside = Mock()
        outside.get_parent.return_value = None
        self.assertTrue(popup.inside_card(child, card))
        self.assertTrue(popup.inside_card(card, card))
        self.assertFalse(popup.inside_card(outside, card))
        self.assertFalse(popup.inside_card(None, card))


class AudioTest(unittest.TestCase):
    def test_reads_normal_muted_and_amplified_volume(self):
        audio = popup.Audio()
        for response, expected in [('Volume: 0.42', (42, False)),
                                   ('Volume: 0.42 [MUTED]', (42, True)),
                                   ('Volume: 1.20', (120, False))]:
            with self.subTest(response=response), patch.object(audio, 'command', return_value=response):
                self.assertEqual(audio.read(), expected)

    def test_invalid_volume_is_reported(self):
        audio = popup.Audio()
        with patch.object(audio, 'command', return_value='no default sink'):
            with self.assertRaises(popup.AudioError):
                audio.read()

    def test_slider_is_limited_and_uses_default_output(self):
        audio = popup.Audio()
        with patch.object(audio, 'command') as command:
            audio.set_volume(42)
            command.assert_called_with('set-volume', '-l', '1.0', popup.SINK, '0.420')
            audio.set_volume(200)
            command.assert_called_with('set-volume', '-l', '1.0', popup.SINK, '1.000')
            audio.set_volume(-10)
            command.assert_called_with('set-volume', '-l', '1.0', popup.SINK, '0.000')
            audio.toggle_mute()
            command.assert_called_with('set-mute', popup.SINK, 'toggle')

    def test_missing_tool_or_timeout_is_user_facing_error(self):
        audio = popup.Audio()
        for failure in [FileNotFoundError(), subprocess.TimeoutExpired('wpctl', 0.5)]:
            with self.subTest(failure=failure), patch.object(popup.subprocess, 'run', side_effect=failure):
                with self.assertRaises(popup.AudioError):
                    audio.read()


class PlacementTest(unittest.TestCase):
    def test_missing_compositor_ipc_has_fallback(self):
        with patch.object(popup.subprocess, 'run', side_effect=FileNotFoundError()):
            self.assertIsNone(popup.cursor_position())

    def test_uses_pointer_monitor_not_focused_monitor(self):
        monitors = [dict(x=0, y=0, width=1920, height=1080, focused=True, reserved=[0, 80, 0, 0]),
                    dict(x=1920, y=0, width=1920, height=1080, focused=False, reserved=[0, 50, 0, 0])]
        results = [subprocess.CompletedProcess([], 0, json.dumps(dict(x=2000, y=100))),
                   subprocess.CompletedProcess([], 0, json.dumps(monitors))]
        with patch.object(popup.subprocess, 'run', side_effect=results):
            self.assertEqual(popup.cursor_position(), (2000, 100, 60))


@unittest.skipUnless(os.environ.get('DOTFILES_GUI_TESTS') == '1',
                     'set DOTFILES_GUI_TESTS=1 for brief, non-audio-writing graphical tests')
class GraphicalPopupTest(unittest.TestCase):
    def test_inside_click_and_both_dismissal_paths(self):
        script = ROOT / 'waybar/.local/bin/waybar-popup.py'
        for kind in ['calendar', 'audio']:
            for dismissal in ['escape', 'outside']:
                with self.subTest(kind=kind, dismissal=dismissal):
                    result = subprocess.run([str(script), kind, '--smoke-test', dismissal],
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_singleton_switch_and_toggle(self):
        import gi
        gi.require_version('Gio', '2.0')
        from gi.repository import Gio, GLib
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

        def running():
            return bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                                 'org.freedesktop.DBus', 'NameHasOwner',
                                 GLib.Variant('(s)', ('io.github.jschraub.WaybarPopup',)),
                                 GLib.VariantType('(b)'), Gio.DBusCallFlags.NONE, 1000, None).unpack()[0]

        if running():
            self.skipTest('An existing user popup is open; leaving it untouched')
        script = ROOT / 'waybar/.local/bin/waybar-popup.py'
        process = subprocess.Popen([str(script), 'calendar'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 3
            while not running() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(running(), 'Popup did not acquire its singleton application ID')
            for _ in range(2):
                result = subprocess.run([str(script), 'audio'], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                if _ == 0:
                    self.assertIsNone(process.poll(), 'Switching panels unexpectedly quit the app')
            stdout, stderr = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, stderr.decode())
            self.assertFalse(running(), 'Popup still owns the application ID after toggling closed')
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=3)
