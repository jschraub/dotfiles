"""Greeter installer regression tests; no sudo, services, or /etc writes.

Run: python -m unittest discover -s tests -p test_greetd_setup.py -v
"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GreetdSetupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / 'source'
        shutil.copytree(ROOT / 'greetd-setup/etc/greetd', self.src)
        self.dest = self.root / 'installed'
        self.dest.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        # sudo only executes commands against fixture paths. Hyprland's parser
        # failure is simulated to test installer control flow, not Lua syntax.
        for name, text in {
            'sudo': '''#!/usr/bin/env python3
import os, subprocess, sys
args = sys.argv[1:]
with open(os.environ['FIXTURE'] + '/sudo.log', 'a') as log:
    log.write(' '.join(args) + '\\n')
if args[0] == 'install':
    filtered = [args[0]]
    index = 1
    while index < len(args):
        if args[index] in ['-o', '-g']:
            index += 2
        else:
            filtered.append(args[index])
            index += 1
    args = filtered
sys.exit(subprocess.run(args).returncode)
''',
            'Hyprland': '#!/bin/sh\n! grep -q INVALID "$3"\n',
            'stat': '#!/bin/sh\nif [ "$2" = "%u:%g:%a" ]; then echo 0:0:755; else exec /usr/bin/stat "$@"; fi\n',
        }.items():
            file = self.bin / name
            file.write_text(text)
            file.chmod(0o755)

    def run_installer(self, body):
        return subprocess.run(['bash', '-c', '''
            set -euo pipefail
            source "$INSTALLER"
            GREETD_SRC="$FIXTURE/source"
            GREETD_DEST="$FIXTURE/installed"
            PAM_DEST="$FIXTURE/pam"
            touch "$PAM_DEST"
            BG_SRC="$FIXTURE/no-background"
            BG_DEST="$FIXTURE/background"
            AVATAR_SRC="$FIXTURE/no-avatar"
            AVATAR_DEST="$FIXTURE/avatar"
        ''' + body], env=dict(os.environ, FIXTURE=str(self.root),
                             INSTALLER=str(ROOT / 'install-greetd-regreet.sh'),
                             PATH=f'{self.bin}:{os.environ["PATH"]}'),
                              text=True, capture_output=True)

    def test_migrates_legacy_config_and_preserves_backup(self):
        old = '[default_session]\ncommand = "Hyprland -c /etc/greetd/hyprland.conf"\n'
        (self.dest / 'config.toml').write_text(old)
        (self.dest / 'hyprland.conf').write_text('# old hyprlang config\n')
        result = self.run_installer('validate_source_config; install_configs; verify_config; install_configs')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.dest / 'config.toml').read_text(), (self.src / 'config.toml').read_text())
        self.assertEqual((self.dest / 'hyprland.lua').read_text(), (self.src / 'hyprland.lua').read_text())
        backups = list(self.dest.glob('config.toml.pre-lua.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), old)
        self.assertTrue((self.dest / 'hyprland.conf').exists())
        calls = (self.root / 'sudo.log').read_text()
        self.assertIn('install -d -o root -g root -m 755', calls)
        self.assertIn('install -o root -g root -m 640', calls)
        self.assertNotIn('chown -R greeter', calls)

    def test_invalid_source_does_not_overwrite_installed_config(self):
        for filename in ['config.toml', 'hyprland.lua']:
            with self.subTest(filename=filename):
                source = self.src / filename
                original = source.read_text()
                source.write_text('INVALID\n')
                (self.dest / 'config.toml').write_text('existing config\n')
                result = self.run_installer('validate_source_config; install_configs')
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((self.dest / 'config.toml').read_text(), 'existing config\n')
                self.assertFalse((self.dest / 'hyprland.lua').exists())
                source.write_text(original)

    def test_installed_legacy_command_fails_verification(self):
        shutil.copy(self.src / 'hyprland.lua', self.dest)
        (self.dest / 'config.toml').write_text('command = "Hyprland -c /etc/greetd/hyprland.conf"\n')
        result = self.run_installer('verify_config; touch "$FIXTURE/enabled"')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'enabled').exists())

    def test_installed_invalid_lua_fails_verification(self):
        shutil.copy(self.src / 'config.toml', self.dest)
        (self.dest / 'hyprland.lua').write_text('INVALID\n')
        result = self.run_installer('verify_config; touch "$FIXTURE/enabled"')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'enabled').exists())
