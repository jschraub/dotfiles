"""Version/channel migration tests: package commands are mocked, never installed."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WaybarInstallTest(unittest.TestCase):
    def run_case(self, installed='', available='0.16.0', git=False, stable_only=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / 'commands'
            script = root / 'pacman'
            script.write_text('''#!/bin/bash
if [[ $1 == -Q && $2 == waybar ]]; then
    if [[ -f "$TEST_ROOT/upgraded" ]]; then echo 'waybar 0.16.0'; exit 0; fi
    [[ -n "$INSTALLED" ]] || exit 1
    echo "waybar $INSTALLED"; exit 0
elif [[ $1 == -Q && $2 == waybar-git ]]; then
    [[ "$GIT_INSTALLED" == 1 && ! -f "$TEST_ROOT/upgraded" ]]; exit
elif [[ $1 == -Si ]]; then
    echo "Version : $AVAILABLE"; exit 0
elif [[ $1 == -S ]]; then
    echo "$*" >> "$TEST_ROOT/commands"
    touch "$TEST_ROOT/upgraded"; exit 0
fi
exit 99
''')
            script.chmod(0o755)
            sudo = root / 'sudo'
            sudo.write_text('#!/bin/sh\nexec "$@"\n')
            sudo.chmod(0o755)
            aur = root / 'paru'
            aur.write_text('#!/bin/sh\nprintf "aur %s\\n" "$*" >> "$TEST_ROOT/commands"\n')
            aur.chmod(0o755)
            result = subprocess.run(['bash', '-c', '''
                source ./setup-waybar.sh
                AUR_HELPER=paru
                stable_only="$STABLE_ONLY"
                install_waybar
            '''], cwd=ROOT, env=dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}',
                                    TEST_ROOT=str(root), INSTALLED=installed, AVAILABLE=available,
                                    GIT_INSTALLED=str(int(git)), STABLE_ONLY=str(int(stable_only))),
                                    capture_output=True, text=True)
            return result, log.read_text() if log.exists() else ''

    def test_git_to_stable_is_single_install_transaction(self):
        result, commands = self.run_case(git=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands.strip(), '-S --needed waybar>=0.16.0')
        self.assertNotIn('-R', commands)

    def test_old_stable_is_upgraded_not_skipped(self):
        result, commands = self.run_case(installed='0.15.0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('waybar>=0.16.0', commands)

    def test_current_stable_requires_no_transaction(self):
        result, commands = self.run_case(installed='0.16.0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, '')

    def test_old_repository_keeps_working_git(self):
        result, commands = self.run_case(available='0.15.0', git=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands, '')

    def test_stable_only_refuses_old_repository_without_removing_git(self):
        result, commands = self.run_case(available='0.15.0', git=True, stable_only=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(commands, '')

    def test_fresh_install_falls_back_to_git_if_repo_is_old(self):
        result, commands = self.run_case(available='0.15.0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(commands.strip(), 'aur -S --needed waybar-git')
