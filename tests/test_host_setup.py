"""Hardware-optional defaults and lock configuration; no real locks or sudo."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class HostSetupTest(unittest.TestCase):
    def test_default_selection_excludes_matrix(self):
        result = subprocess.run(['bash', '-c', 'source ./setup.sh; default_items'], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        self.assertNotIn('matrix', result.stdout.splitlines())
        self.assertIn('hyprland', result.stdout.splitlines())

    def test_waybar_requires_released_lua_support(self):
        result = subprocess.run(['bash', '-c', 'source ./setup.sh; echo "${PKGS[waybar]}"'], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        self.assertEqual(result.stdout.split()[0], 'waybar>=0.16.0')

    def test_greeter_never_makes_configuration_greeter_owned(self):
        script = (ROOT / 'install-greetd-regreet.sh').read_text()
        self.assertFalse('sudo chown -R greeter:greeter "$GREETD_DEST"' in script)
        self.assertIn('sudo install -d -o root -g root -m 755 "$GREETD_DEST"', script)

    def test_lock_auto_falls_back_without_reader_and_enables_native_with_reader(self):
        cases = [('auto', False, False, False), ('auto', True, False, True),
                 ('off', True, False, False), ('auto', True, True, False),
                 ('on', True, False, True)]
        for policy, reader, service_failed, expected in cases:
            with self.subTest(policy=policy, reader=reader, failed=service_failed), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                bin_dir = root / 'bin'
                bin_dir.mkdir()
                home = root / 'home'
                (home / '.config/hypr').mkdir(parents=True)
                (home / '.config/hypr/hyprlock.conf').write_text('# base\n')
                runtime = root / 'runtime'
                runtime.mkdir(mode=0o700)
                capture = root / 'captured.conf'
                commands = {
                    'pgrep': '#!/bin/sh\nexit 1\n',
                    'busctl': '#!/bin/sh\n[ "$FPRINT_FAIL" = 0 ] || exit 1\nprintf "%s\\n" "$FPRINT_DEVICES"\n',
                    'hyprlock': '#!/bin/sh\ncp "$2" "$LOCK_CAPTURE"\n',
                }
                for name, text in commands.items():
                    path = bin_dir / name
                    path.write_text(text)
                    path.chmod(0o755)
                env = dict(os.environ, HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
                           XDG_CONFIG_HOME=str(home / '.config'), LOCK_CAPTURE=str(capture),
                           HYPRLOCK_FINGERPRINT=policy, FPRINT_FAIL=str(int(service_failed)),
                           FPRINT_DEVICES='ao 1 "/net/reactivated/Fprint/Device/0"' if reader else 'ao 0',
                           PATH=f'{bin_dir}:{os.environ["PATH"]}')
                result = subprocess.run(['bash', str(ROOT / 'hyprland-common/.config/hypr/scripts/lock.sh')],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                text = capture.read_text()
                self.assertIn(f'fingerprint:enabled = {str(expected).lower()}', text)
                self.assertIn('pam:enabled = true', text)
                self.assertEqual(list(runtime.glob('hyprlock.*.conf')), [])

    def test_legacy_matrix_plugin_is_not_stowed_into_v2(self):
        self.assertFalse((ROOT / 'opencode/.config/opencode/plugin/matrix.ts').exists())
        self.assertTrue((ROOT / 'matrix-setup/legacy-opencode/matrix.ts').is_file())

    def test_only_owned_legacy_matrix_links_are_retired(self):
        for owned in [False, True]:
            with self.subTest(owned=owned), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                link = home / '.config/opencode/plugin/matrix.ts'
                link.parent.mkdir(parents=True)
                link.symlink_to(ROOT / 'opencode/.config/opencode/plugin/matrix.ts' if owned else home / 'custom.ts')
                subprocess.run(['bash', '-c', 'source ./setup.sh; retire_legacy_matrix_link'], cwd=ROOT,
                               env=dict(os.environ, HOME=str(home)), capture_output=True, check=True)
                self.assertEqual(link.is_symlink(), not owned)
