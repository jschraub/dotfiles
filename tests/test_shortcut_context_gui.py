"""Opt-in shortcut tab UI, fake data only. No authentication or app actions."""
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


@unittest.skipUnless(os.environ.get('ATELIER_GUI_TESTS') == '1', 'opt-in: temporary shortcut reference UI')
class ShortcutGuiTest(unittest.TestCase):
    def test_workspace_tabs_tool_selection_search_and_empty_profiles(self):
        for scale in ('1', '2'):
            with self.subTest(scale=scale), tempfile.TemporaryDirectory() as directory, \
                    tempfile.TemporaryFile(mode='w+') as log:
                target = Path(directory) / 'atelier'
                shutil.copytree(CONFIG, target)
                shutil.copyfile(ROOT / 'tests/atelier-bindings.qml', target / 'test.qml')
                process = subprocess.Popen([QS, '-p', str(target / 'test.qml'), '--no-color'],
                                           env=dict(os.environ, QT_SCALE_FACTOR=scale),
                                           stdout=log, stderr=subprocess.STDOUT)
                try:
                    def ipc(*args):
                        result = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', *args],
                                                capture_output=True, text=True, timeout=3)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        return result.stdout
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        ready = subprocess.run([QS, 'ipc', '--pid', str(process.pid), 'call', 'test', 'status'],
                                               capture_output=True, text=True, timeout=3)
                        if ready.returncode == 0 or process.poll() is not None:
                            break
                        time.sleep(.05)
                    self.assertIsNone(process.poll())
                    state = lambda: json.loads(ipc('status'))
                    self.assertEqual(state()['selected'], 'app:ghostty')
                    self.assertNotIn('tmux', state()['tools'])
                    hints = state()['hints']
                    self.assertIn('Alt+D', [h['text'] for h in hints])
                    self.assertIn('Alt+W', [h['text'] for h in hints])
                    for hint in hints:
                        self.assertEqual(hint['color'], state()['green'])
                        self.assertGreaterEqual(hint['width'] + .01, hint['needed'])
                        self.assertGreaterEqual(hint['gap'], 9)
                    self.assertEqual(len(state()['rows']), 2)
                    ipc('key', 'Alt+D')
                    self.assertEqual(state()['selected'], 'desktop')
                    ipc('key', 'Ctrl+Tab')
                    self.assertEqual(state()['selected'], 'app:ghostty')
                    ipc('key', 'Ctrl+Shift+Tab')
                    self.assertEqual(state()['selected'], 'desktop')
                    ipc('key', 'Alt+2')
                    self.assertEqual(state()['selected'], 'app:ghostty')
                    ipc('key', 'Alt+Shift+3')
                    self.assertIn('Manually selected OpenCode', state()['note'])
                    ipc('key', 'Alt+A')
                    self.assertEqual(state()['scope'], 'installed')
                    ipc('key', 'Alt+D')
                    self.assertEqual(state()['selected'], 'desktop')
                    ipc('key', 'Alt+W')
                    self.assertEqual(state()['selected'], 'app:ghostty')
                    ipc('key', 'Alt+S')
                    self.assertTrue(state()['searchFocused'])
                    ipc('key', 'X')
                    self.assertEqual(state()['query'].lower(), 'x', 'Ordinary typing must stay in search')
                    ipc('query', '')
                    ipc('key', 'Alt+R')
                    self.assertEqual(state()['refreshes'], 1)
                    ipc('tool', 'opencode')
                    self.assertEqual(state()['rows'][-1]['description'], 'New session')
                    self.assertIn('Manually selected OpenCode', state()['note'])
                    ipc('query', 'global override')
                    self.assertEqual(len(state()['rows']), 1)
                    ipc('query', '')
                    ipc('category', 'OpenCode')
                    ipc('select', 'desktop')
                    self.assertEqual(state()['categories'], ['All shortcuts', 'Desktop'])
                    self.assertEqual(len(state()['rows']), 1)
                    ipc('cycle', '-1')
                    self.assertEqual(state()['selected'], 'app:unknown')
                    self.assertEqual(state()['rows'], [])
                    ipc('cycle', '1')
                    self.assertEqual(state()['selected'], 'desktop')
                    ipc('scope', 'installed')
                    self.assertEqual(state()['selected'], 'installed')
                    self.assertIn('tmux', state()['tabs'])
                    ipc('query', 'tmux')
                    self.assertEqual(state()['rows'][0]['description'], 'Create window')
                    ipc('query', '')
                    ipc('scope', 'workspace')
                    self.assertEqual(state()['selected'], 'app:ghostty')
                    self.assertNotIn('tmux', state()['tools'])
                finally:
                    process.terminate()
                    process.wait(timeout=5)
                    log.seek(0)
                    output = log.read()
                    for error in ('ERROR', 'ReferenceError', 'TypeError', 'Unable to assign', 'Binding loop', 'Required property'):
                        self.assertNotIn(error, output, output)
