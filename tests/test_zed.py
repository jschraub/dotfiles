"""Zed theme, migration and editor dispatch without real editors or package installs."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f'scripts/{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


theme = load('apply_theme')
with patch.dict(sys.modules, apply_theme=theme):
    installer = load('setup_zed')


class ZedTest(unittest.TestCase):
    def test_theme_has_matching_chrome_syntax_and_terminal(self):
        family = json.loads((ROOT / 'zed/.config/zed/themes/atelier-amber.json').read_text())
        c = json.loads((ROOT / 'theme/palette.json').read_text())
        self.assertEqual(family['themes'][0]['name'], 'Atelier Amber')
        self.assertEqual(family['themes'][0]['appearance'], 'dark')
        style = family['themes'][0]['style']
        self.assertEqual(style['editor.background'], c['colors']['background'])
        self.assertEqual(style['text.accent'], c['colors']['accent'])
        self.assertEqual(style['panel.background'], c['colors']['panel'])
        self.assertEqual(style['syntax']['keyword']['color'], c['colors']['orange'])
        names = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white']
        for i, name in enumerate(names):
            self.assertEqual(style['terminal.ansi.' + name], c['ansi'][i])
            self.assertEqual(style['terminal.ansi.bright_' + name], c['ansi'][i+8])
        self.assertEqual(style['players'][0]['cursor'], c['colors']['accent'])

    def test_existing_settings_and_vscode_are_preserved_with_one_backup(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            home = Path(directory)
            path = home / '.config/zed/settings.json'
            path.parent.mkdir(parents=True)
            before = '{// keep comment\n"buffer_font_family":"My Font", "buffer_font_size":15, "theme":"One Dark", "agent_servers":{"local":{"command":"local-agent"}},}\n'
            path.write_text(before)
            code = home / '.config/Code/User/settings.json'
            code.parent.mkdir(parents=True)
            code.write_text('{"workbench.colorTheme":"keep"}')
            installer.install(home)
            values = theme.parse_jsonc(path.read_text())
            self.assertEqual(values['theme'], theme.ZED_THEME)
            self.assertEqual(values['buffer_font_family'], 'My Font')
            self.assertEqual(values['buffer_font_size'], 15)
            self.assertEqual(values['agent_servers'], {'local': {'command': 'local-agent'}})
            self.assertIn('// keep comment', path.read_text())
            backups = list(path.parent.glob('settings.json.pre-atelier.*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), before)
            self.assertEqual(code.read_text(), '{"workbench.colorTheme":"keep"}')
            files = set(home.rglob('*'))
            installer.install(home)
            self.assertEqual(files, set(home.rglob('*')))

    def test_fresh_install_and_alternate_config_home(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            home = Path(directory)
            config = home / 'custom-config'
            installer.install(home, config=config)
            values = theme.parse_jsonc((config / 'zed/settings.json').read_text())
            self.assertEqual(values['theme'], theme.ZED_THEME)
            self.assertEqual(values['buffer_font_family'], 'CaskaydiaCove Nerd Font')
            self.assertTrue((config / 'zed/themes/atelier-amber.json').is_file())
            self.assertTrue((home / '.local/bin/desktop-editor').is_file())
            self.assertFalse((home / '.config/zed').exists())

    def test_editor_prefers_zed_and_forwards_paths_and_wait_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            bin_dir = Path(directory)
            (bin_dir / 'bash').symlink_to('/usr/bin/bash')
            for name in ['code', 'zed', 'zeditor']:
                path = bin_dir / name
                path.write_text('#!/usr/bin/python3\nimport json,sys\nprint(json.dumps(sys.argv))\n')
                path.chmod(0o755)
            for expected in ['zeditor', 'zed', 'code']:
                result = subprocess.run([str(ROOT / 'editor/.local/bin/desktop-editor'), '--wait', 'a b.py', 'x;touch unwanted'],
                                        env=dict(os.environ, PATH=str(bin_dir)), text=True, capture_output=True, check=True)
                argv = json.loads(result.stdout)
                self.assertEqual(Path(argv[0]).name, expected)
                self.assertEqual(argv[1:], ['--wait', 'a b.py', 'x;touch unwanted'])
                (bin_dir / expected).unlink()
            missing = subprocess.run([str(ROOT / 'editor/.local/bin/desktop-editor')],
                                     env=dict(os.environ, PATH=str(bin_dir)), text=True, capture_output=True)
            self.assertEqual(missing.returncode, 127)

    def test_setup_includes_zed_without_uninstalling_vscode(self):
        result = subprocess.run(['bash', '-c', 'source ./setup.sh; default_items; echo "${PKGS[zed]}"'],
                                cwd=ROOT, text=True, capture_output=True, check=True)
        self.assertIn('zed', result.stdout.splitlines())
        self.assertIn('zed python', result.stdout)
        script = (ROOT / 'setup-zed.sh').read_text()
        self.assertNotIn('pacman -R', script)
        common = (ROOT / 'hyprland-common/.config/hypr/common.lua').read_text()
        self.assertIn('local editor      = "~/.local/bin/desktop-editor"', common)


if __name__ == '__main__':
    unittest.main()
