"""Real Qt keyboard input in the real power menu, fake shell/no system actions."""
import json
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


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: temporary keyboard power menu')
class PowerKeyboardTest(unittest.TestCase):
    def test_initial_focus_arrows_shortcuts_and_safe_confirmation(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / 'tests/atelier-power-keys.qml', config / 'power-test.qml')
            process = subprocess.Popen([QS, '-p', str(config / 'power-test.qml'), '--no-color'],
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args],
                                            capture_output=True, text=True, timeout=5)
                    return result
                def state():
                    return json.loads(ipc('status').stdout)
                def key(name):
                    self.assertEqual(ipc('key', name).stdout.strip(), 'true')
                    time.sleep(.05)
                    return state()
                def reopen():
                    self.assertEqual(ipc('open').returncode, 0)
                    time.sleep(.1)
                    self.assertEqual(state()['focus'], 'power-lock')
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    response = ipc('status')
                    if process.poll() is not None or (response.returncode == 0 and json.loads(response.stdout)['width'] > 600):
                        break
                    time.sleep(.05)
                self.assertIsNone(process.poll())
                time.sleep(.15)
                self.assertEqual(state()['focus'], 'power-lock', state())
                for direction, focus in [('Right', 'logout'), ('Down', 'shutdown'), ('Left', 'reboot'), ('Up', 'lock'), ('Tab', 'logout')]:
                    self.assertEqual(key(direction)['focus'], 'power-' + focus)
                selected = key('Return')
                self.assertEqual(selected['choice'], 'logout')
                self.assertEqual(selected['focus'], 'power-cancel')
                self.assertEqual(selected['requests'], [])
                cancelled = key('Return')
                self.assertEqual(cancelled['choice'], '')
                self.assertEqual(cancelled['focus'], 'power-logout')
                self.assertEqual(cancelled['requests'], [])
                self.assertEqual(key('Escape')['panel'], '')
                for shortcut, action in [('E', 'logout'), ('R', 'reboot'), ('S', 'shutdown')]:
                    reopen()
                    selected = key(shortcut)
                    self.assertEqual(selected['choice'], action)
                    self.assertEqual(selected['focus'], 'power-cancel')
                    self.assertEqual(selected['requests'], [])
                    self.assertEqual(key('Right')['focus'], 'power-confirm')
                    result = key('Space' if shortcut == 'S' else 'Enter' if shortcut == 'R' else 'Return')
                    self.assertEqual(result['requests'], [{'action': 'power', 'choice': action}])
                    self.assertEqual(result['panel'], '')
                reopen()
                result = key('L')
                self.assertEqual(result['requests'], [{'action': 'power', 'choice': 'lock'}])
                self.assertEqual(result['panel'], '')
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                for issue in ['ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop']:
                    self.assertNotIn(issue, output, output)
