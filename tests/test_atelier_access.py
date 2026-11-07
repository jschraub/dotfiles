"""Fake PAM/greetd only: never locks the real session or submits credentials."""
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


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: fake access/authentication UI')
class AccessUiTest(unittest.TestCase):
    def test_secure_lock_gate_secret_clearing_and_greetd_launch_gate(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            config.mkdir()
            # Exercise the minimal root-installed bundle, not user-home imports.
            registry = ROOT / 'auth-setup/qmldir'
            names = {line.split()[-1] for line in registry.read_text().splitlines() if line.strip()}
            names |= {'lock.qml', 'greeter.qml', 'access_identity.py'}
            for name in names:
                shutil.copyfile(ROOT / 'quickshell/.config/quickshell/atelier' / name, config / name)
            shutil.copyfile(registry, config / 'qmldir')
            shutil.copyfile(ROOT / 'tests/atelier-access.qml', config / 'test.qml')
            process = subprocess.Popen([QS, '-p', str(config / 'test.qml'), '--no-color'], stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args], capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout
                def state(): return json.loads(ipc('status'))
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    ready = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'], capture_output=True, text=True)
                    if ready.returncode == 0 or process.poll() is not None: break
                    time.sleep(.05)
                self.assertIsNone(process.poll())
                self.assertTrue(state()['entrypointsReady'])
                self.assertEqual(state()['starts'], 0, 'No authentication before compositor secure acknowledgement')
                ipc('result', 'true')
                self.assertEqual(state()['unlocks'], 0)
                ipc('secure')
                self.assertEqual(state()['starts'], 1)
                self.assertTrue(state()['masked'])
                ipc('passwordPrompt')
                self.assertEqual(state()['placeholder'], 'Password')
                self.assertFalse(state()['messageShown'])
                ipc('codePrompt')
                self.assertTrue(state()['messageShown'], 'Non-password challenges must remain visible')
                ipc('passwordPrompt')
                ipc('answer'); ipc('submit')
                ipc('submit')
                self.assertEqual(state()['responses'], 1)
                self.assertEqual(state()['responseLength'], 0)
                ipc('result', 'false')
                self.assertEqual(state()['unlocks'], 0)
                self.assertTrue(state()['error'])
                ipc('retry'); ipc('answer'); ipc('fingerprint')
                self.assertEqual(state()['unlocks'], 1)
                self.assertEqual(state()['responseLength'], 0)
                ipc('result', 'true')
                self.assertEqual(state()['unlocks'], 1, 'Success is handled only once')
                ipc('select', 'fixture')
                self.assertEqual(state()['creates'], [])
                ipc('beginLogin'); ipc('select', 'other'); ipc('launch', 'false')
                self.assertEqual(state()['creates'], ['fixture'], 'Cannot switch an active authentication identity')
                self.assertEqual(state()['launches'], [])
                ipc('prompt'); ipc('respond'); ipc('respond')
                self.assertEqual(state()['loginResponses'], 1)
                ipc('failure')
                self.assertFalse(state()['needsResponse'])
                ipc('select', 'other')
                ipc('beginLogin')
                self.assertEqual(state()['creates'], ['fixture', 'other'])
                ipc('launch', 'true')
                self.assertEqual(state()['launches'], [['/usr/bin/start-hyprland']])
            finally:
                process.terminate(); process.wait(timeout=8)
                log.seek(0)
                output = log.read()
                for issue in ('ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop', 'fixture-only-access-secret'):
                    self.assertNotIn(issue, output, output)
