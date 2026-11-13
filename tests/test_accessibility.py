"""Keyboard/focus/scale tests use fake panels, never authenticate or change devices."""
import json
from datetime import date, timedelta
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'quickshell/.config/quickshell/atelier'
QS = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')


def contrast(a, b):
    def luminance(value):
        channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        channels = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in channels]
        return sum(x * w for x, w in zip(channels, [.2126, .7152, .0722]))
    high, low = sorted([luminance(a), luminance(b)], reverse=True)
    return (high + .05) / (low + .05)


class ContrastTest(unittest.TestCase):
    def test_reduced_motion_gates_both_decorative_animations(self):
        for name in ('ActionButton.qml', 'ScrollHandle.qml'):
            self.assertIn('enabled: !Theme.reducedMotion', (CONFIG / name).read_text())

    def test_small_text_roles_have_aa_contrast_on_every_button_surface(self):
        colors = json.loads((ROOT / 'theme/palette.json').read_text())['colors']
        for role in ('text', 'muted', 'accent', 'good'):
            for surface in ('background', 'panel', 'raised', 'hover'):
                with self.subTest(role=role, surface=surface):
                    self.assertGreaterEqual(contrast(colors[role], colors[surface]), 4.5)


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: fake accessibility panels')
class AccessibilityUiTest(unittest.TestCase):
    def test_keyboard_focus_scroll_scaling_names_and_reduced_motion(self):
        ratios = []
        for scale, reduced in [('1', '0'), ('1.5', '1'), ('2', '1')]:
            with self.subTest(scale=scale, reduced=reduced), tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
                config = Path(directory) / 'atelier'
                shutil.copytree(CONFIG, config)
                shutil.copyfile(ROOT / 'tests/atelier-accessibility.qml', config / 'test.qml')
                env = dict(os.environ, QT_SCALE_FACTOR=scale, ATELIER_REDUCED_MOTION=reduced, QT_QPA_PLATFORM='wayland')
                process = subprocess.Popen([QS, '-p', str(config / 'test.qml'), '--no-color'], env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    def ipc(*args):
                        result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args],
                                                capture_output=True, text=True, timeout=3)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        return result.stdout.strip()
                    def state(): return json.loads(ipc('status'))
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'], capture_output=True, text=True)
                        if process.poll() is not None or (result.returncode == 0 and json.loads(result.stdout)['active'] != 'none'):
                            break
                        time.sleep(.05)
                    self.assertIsNone(process.poll())
                    self.assertEqual(state()['active'], 'volume-slider')
                    self.assertTrue(state()['sliderRing'])
                    ratios.append(state()['devicePixelRatio'])
                    self.assertEqual(state()['reducedMotion'], reduced == '1')
                    self.assertEqual(state()['names'][0:2], ['Keep awake', 'Session and power'])
                    self.assertTrue(state()['names'][-1].startswith('Calendar,'))
                    for surface in state()['surfaces']:
                        self.assertGreaterEqual(contrast(state()['danger'], surface), 4.5)
                    # Focused descriptions are discoverable without a mouse.
                    self.assertEqual(ipc('focus', 'probe', 'true'), 'true')
                    time.sleep(.7)
                    self.assertTrue(state()['visualFocus'])
                    self.assertTrue(state()['tooltip'])
                    self.assertGreater(state()['border'], 0)
                    ipc('focus', 'volume-slider', 'false')
                    ipc('focus', 'probe', 'false')
                    self.assertFalse(state()['visualFocus'])
                    self.assertEqual(state()['border'], 0)
                    ipc('key', 'Return', 'false')
                    self.assertEqual(state()['activations'], 1)
                    # The shared focus cycle stays inside a small, scrollable panel.
                    ipc('open', 'audioDevices', '280'); time.sleep(.15)
                    self.assertGreater(state()['contentHeight'], state()['viewportHeight'])
                    for _ in range(48):
                        ipc('key', 'Tab', 'false'); time.sleep(.01)
                        self.assertIn(state()['active'], state()['focusNames'])
                        self.assertTrue(state()['visible'], state())
                    previous = state()
                    index = previous['focusNames'].index(previous['active'])
                    ipc('key', 'Tab', 'true')
                    self.assertEqual(state()['active'], previous['focusNames'][(index - 1) % len(previous['focusNames'])])
                    # Arrow navigation reaches virtualized rows rather than just
                    # cycling the delegates that happened to exist initially.
                    ipc('open', 'network', '650'); time.sleep(.15)
                    self.assertEqual(ipc('focus', 'network-0', 'true'), 'true')
                    for _ in range(25):
                        ipc('key', 'Down', 'false'); time.sleep(.01)
                    self.assertEqual(state()['active'], 'network-25')
                    self.assertTrue(state()['visible'])
                    ipc('open', 'calendar', '430'); time.sleep(.15)
                    day = next(name for name in state()['focusNames'] if name.startswith('calendar-date-'))
                    ipc('focus', day, 'true')
                    ipc('key', 'Down', 'false'); time.sleep(.1)
                    expected = date.fromisoformat(day.removeprefix('calendar-date-')) + timedelta(days=7)
                    self.assertEqual(state()['active'], 'calendar-date-' + expected.isoformat())
                    ipc('key', 'Escape', 'false')
                    self.assertEqual(state()['panel'], '')
                finally:
                    process.terminate(); process.wait(timeout=8)
                    log.seek(0); output = log.read()
                    for issue in ('ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop'):
                        self.assertNotIn(issue, output, output)
        self.assertGreater(ratios[1], ratios[0], 'The enlarged-rendering run must actually change Qt scale')
        self.assertGreater(ratios[2], ratios[1])
