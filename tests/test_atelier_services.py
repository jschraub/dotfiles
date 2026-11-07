"""Fake-device QML regression: no real audio/Bluetooth/media/authentication writes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import struct
import tempfile
import time
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'quickshell/.config/quickshell/atelier'
QS = os.environ.get('ATELIER_QS_BINARY', shutil.which('qs') or 'qs')


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: temporary fake-device panels')
class DesktopServicesTest(unittest.TestCase):
    def test_device_media_tray_osd_and_auth_controls(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode='w+') as log:
            config = Path(directory) / 'atelier'
            shutil.copytree(CONFIG, config)
            shutil.copyfile(ROOT / 'tests/atelier-desktop-services.qml', config / 'services-test.qml')
            def chunk(kind, data):
                return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
            (config / 'wallpaper.png').write_bytes(b'\x89PNG\r\n\x1a\n' +
                chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)) +
                chunk(b'IDAT', zlib.compress(b'\x00\x20\x20\x20')) + chunk(b'IEND', b''))
            process = subprocess.Popen([QS, '-p', str(config / 'services-test.qml'), '--no-color'],
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                def ipc(*args):
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args],
                                            capture_output=True, text=True, timeout=5)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    return result.stdout
                def state():
                    return json.loads(ipc('status'))
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'], capture_output=True, text=True)
                    if process.poll() is not None or (result.returncode == 0 and json.loads(result.stdout)['width'] > 0):
                        break
                    time.sleep(.05)
                self.assertIsNone(process.poll())
                ipc('click', 'audio-device-2')
                self.assertEqual(state()['output'], 2)
                ipc('click', 'microphone-mute')
                self.assertEqual(state()['microphone'], 'mic-mute')
                ipc('page', 'bluetooth')
                ipc('click', 'bluetooth-device-00:11:22:33:44:55')
                self.assertFalse(state()['connected'])
                ipc('click', 'bluetooth-scan')
                self.assertTrue(state()['scanning'])
                ipc('page', 'media')
                self.assertFalse(state()['scanning'], 'Leaving Bluetooth must stop only its owned scan')
                ipc('click', 'media-toggle')
                self.assertTrue(state()['playing'])
                ipc('page', 'tray')
                ipc('click', 'tray-activate-test-app')
                self.assertTrue(state()['tray'])
                ipc('page', 'auth')
                self.assertTrue(state()['masked'])
                ipc('answer')
                self.assertGreater(state()['responseLength'], 0)
                ipc('click', 'auth-submit')
                self.assertTrue(state()['submitted'])
                self.assertEqual(state()['responseLength'], 0)
                ipc('click', 'auth-cancel')
                self.assertTrue(state()['cancelled'])
                ipc('showOsd')
                self.assertEqual(state()['osd'], 'brightness')
                self.assertEqual(state()['osdPercent'], 57)
                time.sleep(1.6)
                self.assertEqual(state()['osd'], '')
                self.assertTrue(state()['wallpaperReady'])
            finally:
                process.terminate()
                process.wait(timeout=10)
                log.seek(0)
                output = log.read()
                for issue in ['ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop', 'fixture-only-secret']:
                    self.assertNotIn(issue, output, output)
