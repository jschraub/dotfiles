"""Real keyboard events over fake clipboard history; never accesses the clipboard."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
QS = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: fake clipboard picker UI')
class ClipboardUiTest(unittest.TestCase):
    def test_search_keyboard_copy_delete_pause_clear_and_dismissal(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            shutil.copytree(ROOT / 'quickshell/.config/quickshell/atelier', config)
            shutil.copyfile(ROOT / 'tests/atelier-clipboard.qml', config / 'test.qml')
            def chunk(kind, data):
                return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
            (config / 'clipboard.png').write_bytes(b'\x89PNG\r\n\x1a\n' +
                chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                chunk(b'IDAT', zlib.compress(b'\x00\x20\x20\x20')) + chunk(b'IEND', b''))
            process = subprocess.Popen([QS, '-p', str(config / 'test.qml'), '--no-color'], stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args], capture_output=True, text=True, timeout=3)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout
                def state(): return json.loads(ipc('status'))
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    response = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'], capture_output=True, text=True)
                    if process.poll() is not None or (response.returncode == 0 and json.loads(response.stdout)['matches'] == 2): break
                    time.sleep(.05)
                self.assertIsNone(process.poll())
                self.assertTrue(state()['plainText'])
                self.assertEqual(state()['index'], 0)
                self.assertEqual(ipc('key', 'Down').strip(), 'true')
                self.assertEqual(state()['index'], 1)
                self.assertEqual(ipc('removeKey').strip(), 'true')
                self.assertEqual(state()['count'], 1)
                self.assertEqual(state()['copies'], [])
                self.assertEqual(ipc('click', 'clipboard-pause').strip(), 'true')
                self.assertTrue(state()['paused'])
                ipc('search', 'no-match'); time.sleep(.12)
                self.assertEqual(state()['matches'], 0)
                ipc('search', 'first'); time.sleep(.12)
                self.assertEqual(state()['matches'], 1)
                self.assertEqual(ipc('key', 'Return').strip(), 'true')
                self.assertEqual(state()['copies'], ['first'])
                self.assertEqual(state()['panel'], '')
                ipc('open')
                self.assertEqual(ipc('click', 'clipboard-clear').strip(), 'true')
                self.assertEqual(state()['count'], 0)
                self.assertEqual(state()['copies'], [])
                self.assertEqual(ipc('key', 'Escape').strip(), 'true')
                self.assertEqual(state()['panel'], '')
            finally:
                process.terminate(); process.wait(timeout=8)
                log.seek(0)
                output = log.read()
                for issue in ('ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop'):
                    self.assertNotIn(issue, output, output)
