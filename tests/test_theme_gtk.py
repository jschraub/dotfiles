"""Opt-in real GTK widgets, no real terminal state changed."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('ATELIER_GTK_TESTS') == '1', 'opt-in: real libadwaita test window')
class GhosttyGtkTest(unittest.TestCase):
    def test_selected_tab_and_toast_action_have_amber_text(self):
        css = ROOT / 'ghostty/.config/ghostty/atelier.css'
        if not css.exists():
            css = ROOT / 'gtk-4.0/.config/gtk-4.0/gtk.css'
        result = subprocess.run(['python3', '-B', str(ROOT / 'tests/gtk-ghostty-theme-probe.py'), str(css)],
                                capture_output=True, text=True, timeout=15, check=True)
        state = json.loads(result.stdout)
        colors = json.loads((ROOT / 'theme/palette.json').read_text())['colors']
        accent = colors['accent']
        self.assertEqual(state['errors'], [])
        self.assertEqual(state['selected'], [accent], state)
        self.assertTrue(state['tabLabels'], state)
        self.assertEqual(set(state['tabLabels']), {accent}, state)
        self.assertEqual(state['toastAction'], [accent], state)
        self.assertEqual(state['toastLabels'], [accent], state)
