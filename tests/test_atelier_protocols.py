"""Native MPRIS/tray/DBusMenu on a private bus; no real player or app actions."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
QS = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: private-bus media/tray integration')
class NativeProtocolsTest(unittest.TestCase):
    def test_native_player_and_nested_tray_menu(self):
        bus = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
        env = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),
                   ATELIER_PRIVATE_BUS_FIXTURE='1', QT_NO_XDG_DESKTOP_PORTAL='1')
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            shutil.copytree(ROOT / 'quickshell/.config/quickshell/atelier', config)
            shutil.copyfile(ROOT / 'tests/atelier-native-media-tray.qml', config / 'test.qml')
            qs = subprocess.Popen([QS, '-p', str(config / 'test.qml'), '--no-color'], env=env, stdout=log, stderr=subprocess.STDOUT)
            fixture = subprocess.Popen(['python3', '-B', str(ROOT / 'tests/desktop-dbus-fixture.py')], env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, 'ipc', '--pid', str(qs.pid), 'call', 'test', *args], env=env, capture_output=True, text=True, timeout=3)
                    return result
                def state(): return json.loads(ipc('status').stdout)
                def wait_for(predicate):
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        result = ipc('status')
                        if result.returncode == 0 and predicate(json.loads(result.stdout)): return
                        if qs.poll() is not None or fixture.poll() is not None: break
                        time.sleep(.05)
                    self.fail('Private-bus protocol state did not settle: ' + result.stdout)
                wait_for(lambda s: s['players'] == 1 and s['tray'] == 1 and s['canToggle'])
                self.assertEqual(ipc('click', 'media-toggle').stdout.strip(), 'true')
                wait_for(lambda s: s['playing'])
                self.assertEqual(ipc('page', 'tray').returncode, 0)
                self.assertEqual(ipc('click', 'tray-menu-atelier-fixture').stdout.strip(), 'true')
                wait_for(lambda s: s['menuCount'] == 2)
                self.assertEqual(ipc('click', 'tray-entry-1').stdout.strip(), 'true')
                wait_for(lambda s: s['menuCount'] == 1)
                self.assertEqual(ipc('click', 'tray-entry-0').stdout.strip(), 'true')
                time.sleep(.1)
                result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.example.AtelierFixture', '--object-path', '/Test',
                                         '--method', 'org.example.AtelierFixture.Status'], env=env, capture_output=True, text=True, check=True)
                self.assertIn('"events": [3]', result.stdout)
                self.assertTrue(state()['playing'])
            finally:
                for process in [fixture, qs, bus]:
                    process.terminate(); process.wait(timeout=10)
                bus.stdout.close()
                log.seek(0)
                output = log.read()
                for issue in ['ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop', 'Traceback']:
                    self.assertNotIn(issue, output, output)
